import logging
from typing import Union, Optional, List, Dict, AnyStr, Any, Set, Tuple

from abccore.DAG import Genesis, Checkpoint
from abccore.agent_service import AgentService
from abcnet.handlers import AbstractItemHandler
from abcnet.services import ChannelService
from abcnet.structures import ItemQualifier, ItemEncodeable, Message
from abcnet.timer import SimpleTimer
from abcnet.transcriber import ItemsParser, Parser

from abcckpt import ckpt_constants
from abcckpt.ckptItems import CkptItemType, CkptData
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import CkptCreationState, PreCkptStatus
from abcckpt.pre_checkpoint import PreCheckpoint

logger = logging.getLogger(__name__)


class CkptSyncItem(ItemQualifier, ItemEncodeable):
    """
    This class handles checkpoint synchronization for new joining nodes.
    """

    def __init__(self, ckpt: Checkpoint):
        self.ckpt = ckpt

    def item_type(self) -> int:
        """
        Returns the item type.
        """
        return CkptItemType.CKPT

    def item_qualifier(self) -> AnyStr:
        return self.ckpt.get_identifier().hex()

    def encode(self, transcriber: "Transcriber"):
        CkptData(CkptCreationState(b''), self.ckpt).encode(transcriber)


class CkptSyncChecklistItem(ItemQualifier):

    def __init__(self, ckpt_id: bytes):
        self.ckpt_id = ckpt_id

    def item_type(self) -> int:
        return CkptItemType.CKPT

    def item_qualifier(self) -> AnyStr:
        return self.ckpt_id.hex()


class CkptSyncParser(ItemsParser):
    """Handles the decoding of the checkpoint item received."""

    def decode_item(self, item_type: int, parser: Parser, delegate=CkptItemsParser()) -> Checkpoint:
        ckpt_data: CkptData = delegate.decode_item(CkptItemType.CKPT_DATA, parser)
        assert ckpt_data is not None
        return ckpt_data.checkpoint_data


class CkptSync(AbstractItemHandler):
    """
    Checkpoint synchronize handler for the checkpoint.
    """

    pc: "PreCheckpoint"

    def __init__(self, pc: PreCheckpoint, agent_service: AgentService):
        super(CkptSync, self).__init__([CkptItemType.CKPT], CkptSyncParser())
        self.agent_service = agent_service
        self.pc = pc
        self.maintenance_methods = [
            (self.pm_dag_check, SimpleTimer(ckpt_constants.CKPT_SYNC_DAG_CHECK)),
            (self.pm_checklist, SimpleTimer(ckpt_constants.CKPT_SYNC_CHECKLIST)),
            (self.pm_fetch, SimpleTimer(ckpt_constants.CKPT_SYNC_FETCH)),
            (self.pm_response, SimpleTimer(ckpt_constants.CKPT_SYNC_RESPONSE))
        ]
        self.latest_ckpt_id: Optional[bytes] = None
        self.ckpt_list: List[bytes] = list()
        self.ckpt_orphan: Dict[bytes, Checkpoint] = dict()

        self.requested_ckpts: Set[bytes] = set()
        self.missing_ckpts: Set[bytes] = set()

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        for method, timer in self.maintenance_methods:
            if timer():
                method(cs)

    def add_orphan(self, ckpt: Checkpoint):
        if ckpt.get_origin() not in self.ckpt_orphan:
            self.ckpt_orphan[ckpt.get_origin()] = ckpt

    def add_latest_ckpt(self, ckpt: Union[Genesis, Checkpoint]):
        if isinstance(ckpt, Checkpoint) and self.latest_ckpt_id != ckpt.get_origin():
            raise ValueError("Received checkpoint that doesn't match the chain.")
        last_hex = ""
        if self.latest_ckpt_id:
            last_hex = self.latest_ckpt_id.hex()

        logger.info("Updated the latest checkpoint from %s to %s.",
                    last_hex,
                    ckpt.get_identifier().hex())
        self.latest_ckpt_id = ckpt.get_identifier()
        if isinstance(ckpt, Checkpoint):
            self.ckpt_list.append(ckpt.get_identifier())

    def process_new_ckpt(self, ckpt: Checkpoint):
        logger.info("New external checkpoint is injected into the agent.")
        self.agent_service.inject_checkpoint(ckpt)

        # Transition to next state
        new_state = CkptCreationState(last_common_string=ckpt.id)
        self.pc.state_transition(new_state, [])
        logger.info("Performed state transition to next checkpoint round because new checkpoint %s was received.",
                    ckpt.get_identifier().hex())

        if ckpt.get_identifier() in self.ckpt_orphan:
            logger.info("Injecting the checkpoint freed another checkpoint: %s", ckpt.get_identifier().hex())
            next_ckpt = self.ckpt_orphan[ckpt.get_origin()]
            del self.ckpt_orphan[ckpt.get_origin()]
            self.update_ckpt(next_ckpt)

    def update_ckpt(self, ckpt: Union[Genesis, Checkpoint], external=False):
        if self.latest_ckpt_id == ckpt.get_identifier():
            return False
        if ckpt.get_identifier() in self.ckpt_list:
            return False
        if isinstance(ckpt, Genesis) and not isinstance(ckpt, Checkpoint):
            if self.latest_ckpt_id is not None:
                logger.error("Received the genesis", exc_info=True)
                return False
            logger.info("Found genesis")
            self.add_latest_ckpt(ckpt)
            return True
        ckpt: Checkpoint
        prev_ckpt = ckpt.get_origin()
        if prev_ckpt != self.latest_ckpt_id and prev_ckpt not in self.ckpt_list:
            logger.warning("Received an orphaned checkpoint.")
            self.add_orphan(ckpt)
            return False
        elif prev_ckpt != self.latest_ckpt_id and prev_ckpt != self.ckpt_list[-1]:
            raise ValueError("The received checkpoint has a prev ckpt in the ckpt list but its no the latest one.")
        else:
            self.add_latest_ckpt(ckpt)
            if external:
                self.process_new_ckpt(ckpt)
            return True

    def ckpt_chain(self) -> Tuple[Genesis, List[Checkpoint]]:
        chain: List[Checkpoint] = list()
        cursor = self.agent_service.get_DAG().get_latest_checkpoint()
        if cursor is None:
            return None, list()

        while cursor is not None:
            if isinstance(cursor, Genesis) and not isinstance(cursor, Checkpoint):
                # Found genesis. Not adding genesis to the chain.
                chain.reverse()
                return cursor, chain

            assert isinstance(cursor, Checkpoint)
            # Adding the prev checkpoint at the end of the list. The list will be reversed anyway.
            chain.append(cursor)

            prev_ckpt = self.agent_service.get_DAG().search(cursor.get_origin())
            if prev_ckpt is None:
                raise ValueError("Couldn't find the previous checkpoint in the dag: " + cursor.get_origin().hex())
            cursor = prev_ckpt.get_node()
        raise ValueError("Genesis not found in the DAG..")

    def pm_dag_check(self, cs: ChannelService):
        ckpt = self.agent_service.get_DAG().get_latest_checkpoint()
        if ckpt is None:
            logger.error("Last ckpt in dag was None..")
            return

        updated = self.update_ckpt(ckpt)
        if not updated:
            return
        if ckpt.get_identifier() == self.latest_ckpt_id:
            logger.info("Found the latest checkpoint in the DAG.")
            return
        logger.warning("The DAG contained a jump in ckpt.")
        gen, chain = self.ckpt_chain()
        if not gen:
            logger.error("Dag empty..")
            return
        self.update_ckpt(gen)
        for ckpt in chain:
            self.update_ckpt(ckpt)

    def pm_checklist(self, cs: ChannelService):
        if self.ckpt_list:
            cs.broadcast_channel().checklist(
                list(map(self.to_item_id_wrap, self.ckpt_list))
            )

    def pm_fetch(self, cs: ChannelService):
        if self.missing_ckpts:
            cs.broadcast_channel().fetch_items(
                list(map(self.to_item_tuple, self.missing_ckpts))
            )

    def pm_response(self, cs: ChannelService):
        response_items = list(filter(self.has_ckpt_id, self.requested_ckpts))
        if not response_items:
            return
        logger.info("Responding to checkpoints requested by the network: \n%s",
                    list(map(self.to_item_tuple, self.requested_ckpts)))
        gen, chain = self.ckpt_chain()
        chain = list(filter(lambda ckpt: ckpt.get_identifier() in self.requested_ckpts, chain))
        cs.broadcast_channel().items(
            list(map(self.to_item_wrap, chain))
        )
        self.requested_ckpts.clear()

    def has_ckpt_id(self, ckpt_id: bytes) -> bool:
        return ckpt_id in self.ckpt_list

    @staticmethod
    def to_item_tuple(ckpt_id: bytes):
        return CkptItemType.CKPT, ckpt_id.hex()

    @staticmethod
    def to_item_id_wrap(ckpt_id: bytes):
        return CkptSyncChecklistItem(ckpt_id)

    @staticmethod
    def to_item_wrap(ckpt: Checkpoint):
        return CkptSyncItem(ckpt)

    def handle_item_content(self, cs: "ChannelService", msg: Message, item_type: int, ckpt: Checkpoint):
        self.update_ckpt(ckpt, external=True)

    def handle_item_request(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        ckpt_id = bytes.fromhex(item_qualifier)
        self.requested_ckpts.add(ckpt_id)

    def handle_item_checklist(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        ckpt_id = bytes.fromhex(item_qualifier)
        if ckpt_id not in self.ckpt_list:
            self.missing_ckpts.add(ckpt_id)
