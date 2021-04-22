import unittest
from typing import Union, List
from unittest.mock import MagicMock, create_autospec

from abcnet import settings
from abcnet.nettesthelpers import pseudo_peer, net_app, MockMsgSender, RecordMsgReceiver
from abcnet.simenv import configure_mocked_network_env
from abcnet.structures import MsgType

from abcckpt.ckptItems import CkptItemType, ValidatorVote, MajorityVotes
from abcckpt.ckpt_creation_state import CkptCreationState
from abcckpt.pre_checkpoint import PreCkptItemProcessor
from abcckpt import ckpttesthelpers
from abcckpt.ckpttesthelpers import CheckpointCase1

configure_mocked_network_env()
ckpttesthelpers.inject_ckpt_items_into_oracle()

settings.configure_logging("log_conf/test_setting.yaml")


def create_process_handler_mock() -> MagicMock:
    process_handler = create_autospec(PreCkptItemProcessor)
    return process_handler


@ckpttesthelpers.ckptitems_matcher(MsgType.items_request, CkptItemType.VALVOTE)
def vote_request_matcher(requested_votes: List[str]) -> Union[List[str], bool]:
    return requested_votes

@ckpttesthelpers.ckptitems_matcher(MsgType.items_checklist, CkptItemType.VALVOTE)
def vote_checklist_matcher(requested_votes: List[str]) -> Union[List[str], bool]:
    return requested_votes

@ckpttesthelpers.ckptitems_matcher(MsgType.items_content, CkptItemType.VALVOTE)
def vote_content_matcher(votes: List[ValidatorVote]) -> List[ValidatorVote]:
    return votes

@ckpttesthelpers.ckptitems_matcher(MsgType.items_content, CkptItemType.MAJVOTES)
def maj_content_matcher(maj_list: List[MajorityVotes]) -> Union[MajorityVotes, bool]:
    if len(maj_list) == 1:
        return maj_list[0]
    return False


class SimulateVoteHandler(unittest.TestCase):

    def setUp(self):
        self.ba = net_app(pseudo_peer("P1-Votehandler"))
        self.pc = ckpttesthelpers.pseudo_pc()
        self.prio_handler = create_process_handler_mock()
        self.hash_handler = create_process_handler_mock()
        self.content_handler = create_process_handler_mock()
        self.svh_handler = ckpttesthelpers.add_stab_vote_handler_app(self.ba, CheckpointCase1, self.pc,
                                                                     [self.prio_handler, self.hash_handler, self.content_handler]
                                                                     )
        our_contact = self.ba.cs.contact
        self.svh_handler.check_state_transition()
        self.svh_handler = self.svh_handler
        self.our_contact = our_contact

        self.sender = MockMsgSender()
        self.ba.cs.net_maintainer.enter_contacts(self.ba.cs, [self.sender.contact])
        self.receiver = RecordMsgReceiver()
        self.receiver.subscribe(self.our_contact)


    def test_sim_1(self):

        # ---- Initialize votes
        voted_item_priority = "priority_abide_1"
        vote_set = []
        for i in range(CheckpointCase1.validator_count):
            v = ValidatorVote.create_and_sign(self.pc.state, voted_item_priority, CkptItemType.PRIORITY,
                                             CheckpointCase1.private_keys[i])
            vote_set.append(v)

        # ---- First lets send the vote as a checklist and see if the handler requests them:

        # For 10 rounds our handler asks for the content as soon as he sees a checklist:
        for i in range(2):

            self.sender.broadcast_channel().checklist(vote_set)

            self.ba.handle_remaining_messages()
            self.ba.maintain(force_maintenance=True)

            requested_votes = self.receiver.next_matching_msg(vote_request_matcher)

            assert requested_votes is not None
            for v in vote_set:
                assert v.item_qualifier() in requested_votes

            self.receiver.clear_record()

        for vote in vote_set:
            assert vote.item_qualifier() in self.svh_handler.registry.votes

        # If he has requested them he will not request them again, until they are posted as a checklist again.
        self.ba.handle_remaining_messages()
        self.ba.maintain(force_maintenance=True)
        requested_votes = self.receiver.next_matching_msg(vote_request_matcher)
        assert requested_votes is None

        # Check item is not called.
        self.prio_handler.check_item_exists: MagicMock
        self.prio_handler.check_item_exists.assert_not_called()

        # ---- Now we provide a subsets of the votes as content:
        subset_size = int(CheckpointCase1.validator_count * 1/3)
        assert subset_size > 2

        subset_votes = vote_set[:subset_size]
        self.sender.broadcast_channel().items(subset_votes)
        self.ba.handle_remaining_messages()
        self.ba.maintain(True)

        for vote in subset_votes:
            assert self.svh_handler.registry.votes[vote.item_qualifier()].vote == vote

        self.receiver.clear_record()

        self.sender.broadcast_channel().checklist(vote_set)
        self.ba.handle_remaining_messages()
        self.ba.maintain(True)

        requested_votes = self.receiver.matching_msg(vote_request_matcher)
        for vote in vote_set[subset_size+1:]:
            assert vote.item_qualifier() in requested_votes

        checklist_votes = self.receiver.matching_msg(vote_checklist_matcher)
        for vote in subset_votes:
            assert vote.item_qualifier() in checklist_votes

        self.receiver.clear_record()

        self.sender.broadcast_channel().fetch_items([(CkptItemType.VALVOTE, v.item_qualifier()) for  v in vote_set])
        self.ba.handle_remaining_messages()
        self.ba.maintain(True)
        content_votes = self.receiver.matching_msg(vote_content_matcher)
        assert content_votes is not None

        for vote in subset_votes:
            vote: ValidatorVote
            assert vote in content_votes

        self.prio_handler.check_item_exists.assert_called_with(voted_item_priority)
        self.prio_handler.transition.assert_not_called()
        self.prio_handler.check_item_exists.reset_mock()

        # ---- Now we provide the remaining votes. We expect a MAJ vote is sent
        self.receiver.clear_record()
        self.sender.broadcast_channel().items(vote_set)

        self.ba.handle_remaining_messages()
        self.ba.maintain(True)

        for vote in vote_set:
            assert self.svh_handler.registry.votes[vote.item_qualifier()].vote == vote


        for i in range(CheckpointCase1.validator_count):
            validator = CheckpointCase1.pub_keys[i]
            assert validator in self.svh_handler.registry.voters
            valid_info = self.svh_handler.registry.voters[validator]
            assert valid_info.voted_item_qualifier == voted_item_priority

        checklist_votes = self.receiver.matching_msg(vote_checklist_matcher)
        for vote in vote_set:
            assert vote.item_qualifier() in checklist_votes

        assert self.svh_handler.majority is not None
        assert self.svh_handler.majority.voted_item == voted_item_priority
        self.prio_handler.transition.assert_not_called()

        maj_sent = self.receiver.matching_msg(maj_content_matcher)
        assert maj_sent is not None
        maj_sent: MajorityVotes
        for vote in vote_set:
            assert vote.item_qualifier() in maj_sent.votes


        self.prio_handler.check_item_exists.assert_called_with(voted_item_priority)
        self.prio_handler.check_item_exists.reset_mock()

        self.prio_handler.transition.assert_not_called()

        # ---- Send missing pass votes and expect maj vote to be removed.

        pass_vote_set = []
        for i in range(CheckpointCase1.validator_count):
            v = ValidatorVote.create_and_sign(self.pc.state, None, CkptItemType.PRIORITY,
                                             CheckpointCase1.private_keys[i])
            pass_vote_set.append(v)

        self.receiver.clear_record()
        self.sender.broadcast_channel().items(pass_vote_set)

        self.ba.handle_remaining_messages()
        self.ba.maintain(True)

        maj_sent = self.receiver.matching_msg(maj_content_matcher)
        assert maj_sent is not None
        assert maj_sent.voted_item_qualifier is None
        for vote in pass_vote_set:
            assert vote.item_qualifier() in maj_sent.votes

        for i in range(CheckpointCase1.validator_count):
            validator = CheckpointCase1.pub_keys[i]
            assert validator in self.svh_handler.registry.voters
            valid_info = self.svh_handler.registry.voters[validator]
            assert valid_info.voted_item_qualifier is None
            assert len(valid_info.votes) == 2

        self.prio_handler.check_item_exists.assert_not_called()
        self.prio_handler.transition.assert_not_called()

        self.svh_handler.majority.transition_buffer_timer.check = MagicMock(return_value=True)
        self.ba.maintain(True)
        assert self.svh_handler.state_transition_performed
        self.prio_handler.transition: MagicMock
        self.prio_handler.transition.assert_called_once()
        transition_votes, voted_item = self.prio_handler.transition.call_args.args
        assert voted_item is None

        prev_state = self.pc.state
        self.pc.state_transition(CkptCreationState.copy(self.pc.state, next_round=True), transition_votes)

        self.ba.maintain(True)

        assert not self.svh_handler.state_transition_performed

        assert self.svh_handler.registry.is_emtpy()
        assert not self.svh_handler.prev_registry.is_emtpy()
        assert self.svh_handler.prev_registry.majority_votes is not None

        self.sender.broadcast_channel()\
            .items([MajorityVotes(prev_state,
                    [v.item_qualifier() for v in vote_set],
                                  voted_item_priority)])
        self.ba.handle_remaining_messages()

        for pass_vote in pass_vote_set:
            vw = self.svh_handler.prev_registry.votes[pass_vote.item_qualifier()]
            assert vw.is_requested

        self.receiver.clear_record()
        self.ba.maintain(True)
        for pass_vote in pass_vote_set:
            vw = self.svh_handler.prev_registry.votes[pass_vote.item_qualifier()]
            assert not vw.is_requested
        votes_received = self.receiver.matching_msg(vote_content_matcher)

        for pass_vote in pass_vote_set:
            assert pass_vote in votes_received





    def tearDown(self) -> None:
        self.ba.close()
