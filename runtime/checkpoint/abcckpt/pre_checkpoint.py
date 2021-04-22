import logging
from typing import List, Optional

from abccore.DAG import Checkpoint
from abccore.prefix_tree import Tree
from abcnet.timer import SimpleTimer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abcckpt import ckpt_constants
from abcckpt.ckptItems import ValidatorVote
from abcckpt.ckpt_creation_state import CkptCreationState, PreCkptStatus

logger = logging.getLogger(__name__)

class ValidatorData:
    def __init__(self, keypair: List, current_stake, ckpt):
        self.current_stake = current_stake
        self.ckpt = ckpt
        self.__keypair = keypair

    def get_keypairs(self):
        return self.__keypair


class AgentService:
    """
    Base class for agent service used in tests.
    """
    def get_keypairs(self) -> List[Ed25519PrivateKey]:
        pass

    def get_DAG(self) -> Tree:
        pass

    def add_txn_to_fetch_list(self, item_id):
        """
        Adds the checkpoint id to the agent checklist.
        param item_id(bytes): id of the transaction.
        """
        pass

    def inject_checkpoint(self, ckpt: Checkpoint):
        pass


class StateTransition:
    """
    Class to represent state transition details in checkpoint creation.
    """
    def __init__(self, prev_state: CkptCreationState, new_state: CkptCreationState, votes: List[ValidatorVote]):
        self.prev_state: CkptCreationState = prev_state
        self.new_state: CkptCreationState = new_state
        self.votes: List[ValidatorVote] = votes


class PreCheckpoint:
    """
    Class for representing the common attributes required in item processor handlers and item creation handlers. state
    field holds the current state and state_trans field holds the transition details of each checkpoint step.
    """
    def __init__(self, state: CkptCreationState):
        self.state = state
        self.state_trans: [StateTransition] = []
        self.cr_prio_flag = True

        self.ack_length = 0
        self.ckpt_creation_timer: SimpleTimer = SimpleTimer(ckpt_constants.CKPT_CREATION_TIME_TH)
        self.state_transition(state, [])

    def state_transition(self, new_state: CkptCreationState, votes: List[ValidatorVote]):
        self.state_trans.append(StateTransition(self.state, new_state, votes))
        logger.info("Current state: %s", self.state)
        logger.info("New state: %s", new_state)
        self.state = new_state
        if new_state.round == 0 and new_state.step_status == PreCkptStatus.AGREE_VALIDATOR:
            self.ckpt_creation_timer.reset()


class PreCkptItemProcessor:
    """
    Base class for item processor in checkpoint creation.
    """

    def transition(self, votes: List[ValidatorVote], voted_item: Optional[str]):
        """
        Performs the transition based on the observed majority voted item.
        If voted_item is None then pass was voted and we need to proceed to the next round
        """
        pass

    def check_item_exists(self, item_qualifier: str) -> bool:
        """
        Returns true if the content of the item with the given qualifier exists in the current state.
        If it doesn't exist, the processor will make sure to ask for its content.
        """
        pass
