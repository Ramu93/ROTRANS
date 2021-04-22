import itertools
import logging
from decimal import Decimal
from typing import Iterable, Dict, Set, Optional, List, Any

from abccore.checkpoint_service import CheckpointService
from abcnet.handlers import AbstractItemHandler
from abcnet.structures import Message
from abcnet.timer import SimpleTimer

from abcckpt import ckpt_constants, fast_vrf
from abcckpt.ckptItems import CkptItemType, ValidatorVote, MajorityVotes
from abcckpt.ckptParser import CkptItemsParser
from abcckpt.ckpt_creation_state import StateTransitionObserver
from abcnet.services import ChannelService
from abcckpt.pre_checkpoint import PreCheckpoint, PreCkptItemProcessor, AgentService
from abcckpt.ckpt_creation_state import PreCkptStatus
from abcckpt.vote_cr_handler import VoteCrHandler

logger = logging.getLogger(__name__)


class VoteWrap:

    vote_qualifier: str = None
    voter_info: "VoterInfo" = None
    vote: Optional[ValidatorVote] = None

    is_requested = False
    is_processed = False

    def __eq__(self, other: "VoteWrap"):
        if other is None or not isinstance(other, VoteWrap):
            return False
        return self.vote == other.vote

    def __hash__(self):
        return hash(self.vote)


class VoterInfo:

    validator: bytes = None  # public key of the validator that has voted.

    votes: Set[VoteWrap] = None  # the votes that the public key has casted and signed.

    stake: Decimal = None

    def __init__(self, validator_key: bytes):
        self.validator = validator_key
        self.votes = set()


    @property
    def voted_item_qualifier(self) -> Optional[str]:
        if not self.has_voted:
            # No votes has been casted by this validator which is not possible
            raise ValueError("This object cannot exist with an empty vote set.")
        elif len(self.votes) > 1:
            # Multiple votes are interpreted as None
            return None
        else:
            # If we know who has voted we should know what was voted as both information come in the same item content.
            vote: VoteWrap = next(iter(self.votes))
            assert vote is not None
            return vote.vote.voted_item_id

    @property
    def has_voted(self) -> bool:
        return len(self.votes) > 0

    def get_vote(self, voted_item_id) -> Optional[VoteWrap]:
        for v in self.votes:
            if v.vote is not None and v.vote.voted_item_id == voted_item_id:
                return v
        return None

    def mark_vote_requested(self):
        assert self.has_voted
        voted_item = self.voted_item_qualifier
        vote_wrap = self.get_vote(voted_item)
        if vote_wrap is not None:
            vote_wrap.is_requested = True
        else:
            for vote_wrap in self.votes:
                vote_wrap.is_requested = True

    def incompatible_vote(self, vote_identifier: Optional[str]) -> bool:
        if vote_identifier is None:
            return False
        return vote_identifier != self.voted_item_qualifier

    def __eq__(self, other: "VoterInfo"):
        if other is None or not isinstance(other, VoterInfo):
            return False
        return self.validator == other.validator

    def __hash__(self):
        return hash(self.validator)


class VoteRegistry:

    def __init__(self):
        # Voted items:
        self.item_votes: Dict[str, Set[VoterInfo]] = dict()
        # Voters:
        self.voters: Dict[bytes, VoterInfo] = dict()
        # Vote item ids:
        self.votes: Dict[str, VoteWrap] = dict()

        self.majority_votes: Optional[List[ValidatorVote]] = None

    def has_vote(self, vote_qualifier: str) -> bool:
        return vote_qualifier in self.votes

    def get_or_create_vote(self, vote_qualifier: str) -> VoteWrap:
        assert vote_qualifier is not None
        if vote_qualifier not in self.votes:
            viw = VoteWrap()
            viw.vote_qualifier = vote_qualifier
            self.votes[vote_qualifier] = viw
        return self.votes[vote_qualifier]

    def register_to_voter(self, vw: VoteWrap, vote: ValidatorVote, ckpt_service: CheckpointService) -> bool:
        if vw.vote is not None:
            assert vw.vote is vote
            return False
        assert vw is self.votes[vote.item_qualifier()]
        assert vw.vote is None
        vw.vote = vote
        if vw.vote.pub_key not in self.voters:
            voter_info = VoterInfo(vw.vote.pub_key)
            voter_info.stake = ckpt_service.delegated_stake(vw.vote.pub_key)
            self.voters[vw.vote.pub_key] = voter_info
        else:
            voter_info = self.voters[vw.vote.pub_key]
        vw.voter_info = voter_info
        voter_info.votes.add(vw)
        self.redistribute_vote(voter_info)
        return True

    def redistribute_vote(self, voter_info: VoterInfo):
        voted_item = voter_info.voted_item_qualifier
        if voted_item not in self.item_votes:
            self.item_votes[voted_item] = set()

        self.item_votes[voted_item].add(voter_info)

        for vw in voter_info.votes:
            other_vote = vw.vote.voted_item_id
            if other_vote is voted_item:
                continue
            if other_vote in self.item_votes:
                self.item_votes[other_vote].discard(voter_info)

    def is_emtpy(self):
        return len(self.votes) == 0 and len(self.item_votes) == 0 and len(self.voters) == 0

class Majority:
    voted_item: Optional[str] = None

    transition_buffer_timer: SimpleTimer

    majority_votes_post_timer: SimpleTimer

    def __init__(self, voted_item: Optional[str]):
        self.voted_item = voted_item
        self.transition_buffer_timer = SimpleTimer(ckpt_constants.TRANSITION_BUFFER_TIME, start=True)
        self.majority_votes_post_timer = SimpleTimer(ckpt_constants.MAJORITY_VOTE_POST_PERIOD)


class StabVotingHandler(AbstractItemHandler, StateTransitionObserver):
    """
    Item processor class for processing votes in each step of checkpoint creation. Majority checks and stalemate checks
    are done after evaluating the vote distribution.
    """
    def __init__(self, pc: PreCheckpoint, ckpt_service: CheckpointService,
                 agent_service: Optional[AgentService]=None):
        super().__init__([CkptItemType.VALVOTE, CkptItemType.MAJVOTES], CkptItemsParser())
        self.pc: PreCheckpoint = pc
        self._processors: Dict[PreCkptStatus, PreCkptItemProcessor] = None
        self.vote_cr_handler: Optional[VoteCrHandler] = None
        self.agent_service: Optional[AgentService] = agent_service
        self.ckpt_service: CheckpointService = ckpt_service
        self.prev_registry: VoteRegistry = VoteRegistry()  # Initialize with an empty registry
        self.registry: VoteRegistry = VoteRegistry()

        self.stake_vote_threshold: Optional[Decimal] = None

        self.new_vote_distrib = False
        self.new_vote_found = False
        self.state_transition_performed = False

        self.stalemate_found = False
        self.is_minority_voter = False
        self.stalemate_vote_switch = False
        self.stalemate_timer = SimpleTimer(ckpt_constants.MISSING_VOTES_REQUEST_TIME)

        self.majority: Optional[Majority] = None
        # Timers for maintenance:
        self.timeout_timers = [
            (self.request_missing_votes, SimpleTimer(ckpt_constants.MISSING_VOTES_REQUEST_TIME)),
            (self.share_vote_checklist, SimpleTimer(ckpt_constants.VOTES_CHECKLIST_TIME)),
            (self.share_requested_voted, SimpleTimer(ckpt_constants.REQUESTED_VOTE_RESPONSE_TIME)),
            (self.eval_current_votes_distribution, SimpleTimer(ckpt_constants.VOTE_DISTRIB_EVAL_TIME)),
            (self.prev_state_transition_maj_vote_broadcast, SimpleTimer(ckpt_constants.PREV_VOTES_CHECKLIST_BROADCAST))
        ]


    def set_handlers(self,
                     prio_handler: PreCkptItemProcessor,
                     hash_handler: PreCkptItemProcessor,
                     content_handler: PreCkptItemProcessor,
                     vote_cr_handler: Optional[VoteCrHandler] = None):
        self._processors = {
            PreCkptStatus.AGREE_VALIDATOR: prio_handler,
            PreCkptStatus.AGREE_HASH: hash_handler,
            PreCkptStatus.AGREE_CONTENT: content_handler,
        }
        self.vote_cr_handler = vote_cr_handler

    @property
    def processors(self) -> Dict[PreCkptStatus, PreCkptItemProcessor]:
        if not self._processors:
            raise Exception("Processors not yet initialized. "
                            "Call set_handlers at initialization.")
        return self._processors

    def get_current_processor(self) -> PreCkptItemProcessor:
        if self.current_state.step_status not in self.processors:
            raise Exception("Current step %s does not have a processor.")
        return self.processors[self.current_state.step_status]

    def process_vote(self, vote: ValidatorVote, outside_source=False):
        if vote.state != self.current_state:
            logger.debug("Received a vote from another round. Ignoring vote.. My state: %s\nThe other state: %s",
                           self.current_state, vote.state)
            return

        if vote.signature is None:
            logger.warning("Received a vote with no signature: %s", vote)
            return

        if vote.voted_item_type != self.get_current_vote_item_type():
            logger.debug("Received a vote with an unexpected voted item type: %s", vote)
            return

        vw = self.registry.get_or_create_vote(vote.item_qualifier())
        if vw.is_requested and outside_source:
            logger.debug("Requested vote has been delivered through network. Marking it unrequested: %s", vote)
            vw.is_requested = False
        if vw.is_processed:
            logger.debug("Already processed vote %s. Skipping", vote)
            return

        if not vote.verify_signature():
            logger.debug("A vote received with invalid signature: %s", vote)
            vw.is_processed = True
            return

        new_vote = self.registry.register_to_voter(vw, vote, self.ckpt_service)
        if new_vote:
            if  vote.voted_item_id is not None:
                self.get_current_processor().check_item_exists(vote.voted_item_id)
            self.new_vote_distrib = True
        vw.is_processed = True

    def get_current_vote_item_type(self):
        if self.current_state.step_status == PreCkptStatus.AGREE_VALIDATOR:
            return CkptItemType.PRIORITY
        if self.current_state.step_status == PreCkptStatus.AGREE_HASH:
            return CkptItemType.CKPT_HASH
        if self.current_state.step_status == PreCkptStatus.AGREE_CONTENT:
            return CkptItemType.CKPT_DATA

    def process_majority_votes(self, maj_votes: MajorityVotes, registry: VoteRegistry):
        vote_set = set(maj_votes.votes)
        if len(vote_set) == 0:
            return

        for vote_qualifier in vote_set:
            if registry.has_vote(vote_qualifier):
                vote_wrap = registry.get_or_create_vote(vote_qualifier)
                if vote_wrap.vote is None:
                    continue
                if vote_wrap.voter_info.incompatible_vote(maj_votes.voted_item_qualifier):
                    logger.warning("A majority vote was posted that has incomplete information: %s",
                                   maj_votes.voted_item_qualifier)
                    vote_wrap.voter_info.mark_vote_requested()

    def handle_item_content(self, cs: "ChannelService", msg: Message, item_type: int, item_content: Any):
        if item_type == CkptItemType.MAJVOTES and item_content is not None and isinstance(item_content, MajorityVotes):
            self.process_majority_votes(item_content, self.registry)
            self.process_majority_votes(item_content, self.prev_registry)
        if item_type == CkptItemType.VALVOTE and item_content is not None and isinstance(item_content, ValidatorVote):
            self.process_vote(item_content, outside_source=True)
        logger.debug("Received unexpected item with type: %d, %s", item_type, item_content)

    def handle_item_request(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        if item_type != CkptItemType.VALVOTE:
            logger.debug("Received unexpected item with type: %d, %s", item_type, item_qualifier)
            return
        if self.prev_registry.has_vote(item_qualifier):
            vote = self.prev_registry.get_or_create_vote(item_qualifier)
            if vote.vote is not None:
                logger.debug("Vote %s is requested by the network but it is in the prev registry. "
                             "We will reply to it later.",
                             item_qualifier)
                vote.is_requested = True

        elif self.registry.has_vote(item_qualifier):
            vote_wrap = self.registry.get_or_create_vote(item_qualifier)
            if vote_wrap.vote is not None:
                vote_wrap.is_requested = True
            elif vote_wrap.is_requested:
                logger.debug("Vote %s was requested by the network so we will not send a request ourselves.",
                             item_qualifier)
                vote_wrap.is_requested = False

    def handle_item_checklist(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        if item_type != CkptItemType.VALVOTE:
            logger.debug("Received unexpected item with type: %d, %s", item_type, item_qualifier)
            return
        vw = self.registry.get_or_create_vote(item_qualifier)
        if vw.vote is None:
            self.new_vote_found = True

    def perform_maintenance(self, cs: ChannelService, force_maintenance=False):
        self.check_state_transition()
        for maintenance_method, timer in self.timeout_timers:
            if force_maintenance or timer():
                # Timer of action has reached zero.
                # Perform maintenance action by calling the method that has the action_name.
                maintenance_method(cs)

    def get_missing_votes(self) -> Iterable[VoteWrap]:
        return filter(lambda vw: vw.vote is None, self.registry.votes.values())

    def request_missing_votes(self, cs: ChannelService):
        if not self.new_vote_found:
            # logger.debug("No votes are missing. Not requesting any vote.")
            return
        cs.broadcast_channel().fetch_items([
            (CkptItemType.VALVOTE, vw.vote_qualifier)
            for vw in self.get_missing_votes()
        ])
        self.new_vote_found = False

    def get_present_votes(self) -> Iterable[VoteWrap]:
        return filter(lambda vw: vw.vote is not None, self.registry.votes.values())

    def share_vote_checklist(self, cs: ChannelService):
        vote_checklist = [vw.vote for vw in self.get_present_votes()]
        if vote_checklist:
            cs.broadcast_channel().checklist(vote_checklist)

    def get_requested_votes(self, registry: VoteRegistry) -> Iterable[VoteWrap]:
        return filter(lambda vw: vw.vote is not None and vw.is_requested, registry.votes.values())

    def get_all_requested_votes(self) -> Iterable[VoteWrap]:
        return itertools.chain(self.get_requested_votes(self.registry),
                              self.get_requested_votes(self.prev_registry))

    def share_requested_voted(self, cs: ChannelService):
        requested_votes = list(self.get_all_requested_votes())
        if requested_votes:
            cs.broadcast_channel().items([
                vw.vote for vw in requested_votes
            ])
        for vw in requested_votes:
            vw.is_requested = False

    def eval_current_votes_distribution(self, cs: ChannelService):
        self.find_new_majority()
        if self.majority:
            if not self.state_transition_performed:
                logger.info("Performing state transition from state %s. Majority votes item: %s", self.state,
                            self.majority.voted_item)
                self.ready_transition(cs)
        elif self.stalemate_found:
            if not self.stalemate_vote_switch:
                if self.is_minority_voter or self.stalemate_timer.check():
                    self.switch_vote_to_pass()
            else:
                logger.warning("Stalemate detected but already switched vote.")

    def get_support_of_vote(self, vote_item_qualifier: Optional[str]) -> Decimal:
        if vote_item_qualifier in self.registry.item_votes:
            return sum(map(lambda voter_info: voter_info.stake, self.registry.item_votes[vote_item_qualifier]))
        return Decimal(0.0)

    def get_self_vote_support(self) -> Decimal:
        if self.agent_service is None:
            return Decimal(0)
        max_vote_support = Decimal(0)
        for key in self.agent_service.get_keypairs():
            pub_key = fast_vrf.encode_pub_key(key.public_key())
            if pub_key not in self.registry.voters:
                continue
            voted_item_id = self.registry.voters[pub_key].voted_item_qualifier
            if voted_item_id not in self.registry.item_votes:
                continue
            summed_voting_stake = self.get_support_of_vote(voted_item_id)
            if summed_voting_stake > max_vote_support:
                max_vote_support = summed_voting_stake
        return max_vote_support

    def find_new_majority(self):
        if not self.new_vote_distrib:
            return
        self.new_vote_distrib = False

        majority_voted_item_id: Optional[str] = None
        majority_found = False
        all_votes_stake_sum = Decimal(0.0)
        for voted_item_id in self.registry.item_votes.keys():
            summed_voting_stake = self.get_support_of_vote(voted_item_id)
            all_votes_stake_sum += summed_voting_stake
            if self.is_majority_threshold_surpassed(summed_voting_stake):
                if majority_found:
                    raise Exception("While counting votes two simultaneous majorities. Current state: %s"
                                    "\nVoted item 1:%s"
                                    "\nVoted item 2: %s",
                                    self.current_state, majority_voted_item_id, voted_item_id)
                majority_found = True
                majority_voted_item_id = voted_item_id
        if majority_found:
            self.set_majority(majority_voted_item_id)
            self.stalemate_found = False
            self.is_minority_voter = False
        else:
            self.unset_majority()
            stalemate_condition = self.is_majority_threshold_surpassed(all_votes_stake_sum)
            if stalemate_condition and not self.stalemate_found:
                self.stalemate_found = True
                self.stalemate_timer.reset()
                remaining_votes = self.ckpt_service.stake_sum() - all_votes_stake_sum
                if self.stalemate_found:
                    self.is_minority_voter = not self.is_majority_threshold_surpassed(remaining_votes +
                                                                              self.get_self_vote_support())

    def is_majority_threshold_surpassed(self, vote_stake: Decimal) -> bool:
        try:
            return self.stake_vote_threshold < vote_stake
        except AttributeError:
            return (self.ckpt_service.stake_sum() * Decimal(2 / 3)) < vote_stake # incase of None

    def set_majority(self, voted_item: Optional[str]):
        if self.majority is not None and self.majority.voted_item != voted_item:
            logger.warning("Majority voted item is switched from %s to %s.", self.majority.voted_item, voted_item)
            self.unset_majority()
        logger.info("Found a new majority for voted item %s in state: %s", voted_item, self.current_state)
        self.majority: Optional[Majority] = Majority(voted_item)

    def unset_majority(self):
        if self.majority is not None:
            logger.warning("Majority of votes was found for item id: %s. Unsetting it.", self.majority.voted_item)
            self.majority: Optional[Majority] = None

    def ready_transition(self, cs: ChannelService):
        if not self.majority.transition_buffer_timer.check():
            logger.debug("Majority of votes for item %s  in state %s has been found. Remaining buffer time: %s",
                         self.majority.voted_item, self.current_state, self.majority.transition_buffer_timer)
            self.post_majority_vote(cs)
            return

        if self.majority.voted_item is not None and \
                not self.get_current_processor().check_item_exists(self.majority.voted_item):
            logger.info("The voted item %s in state %s has not been received yet. Waiting..",
                           self.majority.voted_item, self.current_state)
            return

        logger.info("Majority of voted item, %s, has been found and the buffer time has passed. "
                    "Performing transition from state: %s.", self.majority.voted_item, self.current_state)
        self.get_current_processor().transition(self.get_majority_votes(), self.majority.voted_item)
        self.state_transition_performed = True
        self.registry.majority_votes = self.get_majority_votes()

    def switch_vote_to_pass(self):
        assert not self.stalemate_vote_switch
        self.stalemate_vote_switch = True
        if self.vote_cr_handler is not None:
            logger.warning("Switching to pass vote as %sminority voter.", "" if self.is_minority_voter else "non-")
            self.vote_cr_handler.create_vote(None, {
                PreCkptStatus.AGREE_VALIDATOR: CkptItemType.PRIORITY,
                PreCkptStatus.AGREE_HASH: CkptItemType.CKPT_HASH,
                PreCkptStatus.AGREE_CONTENT: CkptItemType.CKPT_DATA,
            }.get(self.pc.state.step_status))


    def post_majority_vote(self, cs: ChannelService):
        if not self.majority.majority_votes_post_timer():
            return
        assert self.majority is not None
        majority_votes = self.get_majority_votes()
        assert len(majority_votes) > 0
        logger.debug("Broadcasting %d many majority votes.", len(majority_votes))
        maj_votes = MajorityVotes(state=self.current_state,
                                  votes=[v.item_qualifier() for v in majority_votes],
                                  voted_item_qualifier=self.majority.voted_item)
        cs.broadcast_channel().items([maj_votes])

    def get_majority_votes(self) -> List[ValidatorVote]:
        majority_voters = filter(lambda vote_info: vote_info.stake > 0,
                                 self.registry.item_votes[self.majority.voted_item])
        votes = list()
        for voter_info in majority_voters:
            assert voter_info.has_voted
            assert voter_info.voted_item_qualifier == self.majority.voted_item
            vote = None
            for voter_vote in voter_info.votes:
                if voter_vote.vote.voted_item_id == self.majority.voted_item:
                    vote = voter_vote.vote
                    break
            if vote is None:
                logger.warning("No pass vote found for a validator. Only multiple different votes: %s",
                               voter_info.votes)
                votes += list(voter_info.votes)
            else:
                votes.append(vote)
        return votes

    def prev_state_transition_maj_vote_broadcast(self, cs: ChannelService):
        # If there is a prev registry post the votes of the previous majority as a checklist so other peers
        # can fetch them and perform the same transition.
        if self.prev_registry is not None and self.prev_registry.majority_votes is not None:
            cs.broadcast_channel().checklist(self.prev_registry.majority_votes)

    def handle_state_transition(self, state):
        self.clear_state()
        if state.is_new_ckpt_round():
            self.stake_vote_threshold = (self.ckpt_service.stake_sum() * Decimal(2 / 3))

    def clear_state(self):
        logger.debug("Cleared vote registry for new state: %s", self.current_state)
        self.prev_registry = self.registry
        self.registry = VoteRegistry()
        self.new_vote_distrib = False
        self.new_vote_found = False
        self.majority: Optional[Majority] = None
        self.state_transition_performed = False

        self.stalemate_found = False
        self.stalemate_vote_switch = False
        self.is_minority_voter = False
