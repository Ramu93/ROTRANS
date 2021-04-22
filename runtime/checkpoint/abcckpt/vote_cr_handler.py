import logging
from typing import Optional

from abcnet.handlers import AbstractItemHandler

from abcckpt import fast_vrf
from abcckpt.ckptItems import CkptItemType, ValidatorVote
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.pre_checkpoint import PreCheckpoint, AgentService

logger = logging.getLogger(__name__)


class VoteCrHandler(AbstractItemHandler):
    """
    Item creator class for vote in each step of checkpoint creation.
    """
    def __init__(self, pre_ckpt: PreCheckpoint, agent_service: AgentService):
        super(VoteCrHandler, self).__init__([CkptItemType.VALVOTE],
                                            CkptItemsParser())
        # Global Set of Data
        self.pc: PreCheckpoint = pre_ckpt
        self.agent_service = agent_service

        self.prio_sent = False
        self.hash_sent = False
        self.content_sent = False

        self.requested_items = set()
        self.votes = {}

        self.stab_vote_handler: "StabVotingHandler" = None

    def set_handlers(self, stab_vote_handler: "StabVotingHandler"):
        self.stab_vote_handler: "StabVotingHandler" = stab_vote_handler

    def create_vote(self, qualifier: Optional[str], item_type: CkptItemType):
        for skey in self.agent_service.get_keypairs():
            pkb = fast_vrf.encode_pub_key(skey.public_key())

            vote = ValidatorVote.create_and_sign(self.pc.state, qualifier, item_type, skey)
            if self.stab_vote_handler is not None:
                self.stab_vote_handler.process_vote(vote, outside_source=False)
            logger.info("In state:  %s. \nValidator %s created vote for %s.", self.pc.state.step_status, pkb.hex(), qualifier)
            # self.votes[vote.item_qualifier()] = vote

