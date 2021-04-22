import logging
from enum import IntEnum
from typing import Optional

from abcckpt.fast_vrf import create_hash

logger = logging.getLogger(__name__)


class PreCkptStatus(IntEnum):
    """
    Class representing integer step status in checkpoint creation.
    """
    AGREE_VALIDATOR = 1
    AGREE_HASH = 2
    AGREE_CONTENT = 3


class CkptCreationState:
    """
    Class representing the state of checkpoint rounds with step_status attribute. Data fields chosen_validator and
    content_hash are set when these items are updated when a majority voted value is found in each step. round field is
    used to track updates of current_common_str(used in priority value).
    """
    last_common_string: bytes

    def __init__(self, last_common_string: bytes, round: int = None, step_status: PreCkptStatus = None,
                 chosen_validator: Optional[bytes] = None, content_hash: Optional[bytes] = None):
        if last_common_string is None or not isinstance(last_common_string, bytes):
            raise ValueError("Last common string mis-defined: " + str(last_common_string))
        self.last_common_string: bytes = last_common_string  # common string
        if round is None:
            self.round: int = 0
        else:
            self.round = round

        if step_status is None:
            step_status = PreCkptStatus.AGREE_VALIDATOR
        self.step_status: PreCkptStatus = step_status
        self.chosen_validator: Optional[bytes] = chosen_validator
        self.content_hash: Optional[bytes] = content_hash
        self.current_common_str = self.__calculate_current_common_str()

    @classmethod
    def copy(cls, state: "CkptCreationState", common_str=None, next_round=False, step_status: PreCkptStatus = None):
        round = state.round
        if next_round:
            round += 1
        step = state.step_status
        if step_status is not None:
            step = step_status
        if common_str is None:
            common_str = state.last_common_string
        return CkptCreationState(common_str, round, step, state.chosen_validator,
                                 state.content_hash)

    def __calculate_current_common_str(self) -> bytes:
        common_string = self.last_common_string
        for i in range(self.round + 1):
            common_string = create_hash(common_string)
        return common_string

    def get_current_common_str(self):
        return self.current_common_str

    def voted_chosen_val(self, voted_pb_key: bytes):
        self.chosen_validator = voted_pb_key

    def voted_content_hash(self, voted_content_hash):
        self.content_hash = voted_content_hash

    def __eq__(self, other: "CkptCreationState"):
        if other is None:
            return False
        return self.last_common_string == other.last_common_string \
               and self.round == other.round \
               and self.step_status == other.step_status \
               and self.chosen_validator == other.chosen_validator and self.content_hash == other.content_hash

    def __str__(self) -> str:
        return f"CkptCreationState(last_common_string={self.last_common_string.hex()[:5]}," \
               f" round={self.round}, step_status={str(self.step_status)}," \
               f"chosen_validator={self.chosen_validator}," \
               f" content_hash={self.content_hash}, current_common_str={self.current_common_str.hex()[:5]})"

    def __repr__(self):
        return str(self)

    def is_new_ckpt_round(self):
        return self.round == 0 and self.step_status == PreCkptStatus.AGREE_VALIDATOR


class StateTransitionObserver:
    pc: "PreCheckpoint"
    state: CkptCreationState = None

    @property
    def current_state(self) -> CkptCreationState:
        return self.pc.state

    def check_state_transition(self):
        if self.state == self.pc.state:
            return

        if self.pc.state is None:
            raise Exception("State was set to None")

        prev_state: CkptCreationState = self.state
        current_state: CkptCreationState = self.current_state
        self.state = current_state

        # logger.info("A new state transition occured. From \n\t%s\nto\n\t%s", prev_state, self.state)

        if prev_state is None \
                or prev_state.last_common_string != current_state.last_common_string:
            self.handle_ckpt_transition(current_state)
            return

        if prev_state.round != current_state.round:
            if prev_state.round > current_state.round:
                raise Exception("Round went backwards!")
            else:
                self.handle_round_transition(current_state, current_state.round)
            return

        if prev_state.step_status != current_state.step_status:
            if prev_state.step_status > current_state.step_status:
                raise Exception("Step went backwards!")

            if current_state.step_status >= prev_state.step_status + 2:
                raise Exception("Step was skipped.")

            if current_state.step_status >= PreCkptStatus.AGREE_HASH:
                if current_state.chosen_validator is None:
                    raise Exception("No validator defined in state.")

            if current_state.step_status >= PreCkptStatus.AGREE_CONTENT:
                if current_state.content_hash is None:
                    raise Exception("No content hash defined in state.")

            self.handle_step_transition(current_state, current_state.step_status)
            return

    def handle_state_transition(self, state: CkptCreationState):
        pass

    def handle_ckpt_transition(self, state: CkptCreationState):
        self.handle_state_transition(state)

    def handle_round_transition(self, state: CkptCreationState, round: int):
        self.handle_state_transition(state)

    def handle_step_transition(self, state: CkptCreationState, step_status):
        self.handle_state_transition(state)
