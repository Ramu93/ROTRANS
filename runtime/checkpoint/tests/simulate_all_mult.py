import logging
import os
from copy import deepcopy, copy
from decimal import Decimal
from random import randint

from abccore.DAG import Wallet, Genesis
from abcnet import settings, nettesthelpers, transcriber
from abcnet.netstats import LogEvent, MsgEvent
from abcnet.services import BaseApp
from abcnet.simenv import configure_mocked_network_env, Simulation
from abcnet.structures import MsgType, PeerContactInfo, Message

from abccore.DAG import Transaction

from abccore.agent import outputs_helper

from abccore.prefix_tree import Tree, TreeLeaf
from abcckpt.pre_checkpoint import AgentService, PreCheckpoint
from abcckpt import ckpttesthelpers
from abcckpt import ckpt_constants
from tests.testUtil import TestUtility

configure_mocked_network_env()
ckpttesthelpers.inject_ckpt_items_into_oracle()

settings.configure_logging("log_conf/test_setting.yaml")

ckpt_constants.CKPT_PRIORITY_RCV_TIMEOUT = 30.0
ckpt_constants.PROPOSAL_HASH_RCV_TIME = 15.0

logger = logging.getLogger(__name__)

def event_ser_filter(event: LogEvent):
    if not isinstance(event, MsgEvent):
        return False
    event: MsgEvent
    m = Message(event.msg_parts)
    m_type = MsgType(transcriber.parse_message_type(m))
    return m_type in [
        MsgType.items_content,
        MsgType.items_checklist,
        MsgType.items_request,
        MsgType.items_notfound
    ]

settings.NetStatSettings.msg_serialization_filter = event_ser_filter

class Validator:

    def __init__(self, ba: BaseApp, agent: AgentService, pc: PreCheckpoint, index: int):
        self.ba = ba
        self.agent = agent
        self.pc = pc
        self.index = index


class Generator:
    def __init__(self):
        self.wallets = []

    def gen_genesis(self):
        """Generates a genesis with up to 20 wallets of different owners"""
        self.wallets.clear()
        size = randint(1, 20)
        for i in range(size):
            genesis = os.urandom(32)
            val = Decimal(100)
            new_wallet = Wallet(int.to_bytes(i, 32, "big"), val, genesis, i)
            self.wallets.append(deepcopy(new_wallet))

        return Genesis(copy(self.wallets))

    def gen_transaction(self):
        """Picks a random number from 1 to 5 of existing wallets at random and creates a new transaction with it,
        transfering a random percentage of the value to a new wallet
        """
        number_wallets = randint(1, min(5, len(self.wallets)))
        inputs = []
        in_sum = Decimal(0)
        for number in range(0, number_wallets):
            i = randint(0, len(self.wallets) - 1)
            inputs.append(self.wallets.pop(i))
            in_sum += inputs[len(inputs) - 1].get_value()

        out_sum = in_sum * randint(1, 99) / 100

        outputs = outputs_helper(
            inputs, [Wallet(int.to_bytes(randint(0, 100), 32, "big"), Decimal(out_sum))]
        )

        for wallet in outputs:
            self.wallets.append(wallet)

        new_trans = Transaction(inputs, outputs, None)
        return new_trans

    def get_root(self, tree: Tree, trans: Transaction):
        """Recursion to check if the current :param trans has genesis as parent or if the parents of trans have genesis as
        parent.
        """
        for parent in trans.get_parents():
            node = tree.search(parent)
            if isinstance(node, TreeLeaf):
                dag_node = node.get_node()
                if isinstance(dag_node, Genesis):
                    return True

                return self.get_root(tree, dag_node)
            elif node is not None:
                raise Exception("Unexpected Behaviour")

        return False

def gen_dag():
    tree = Tree()
    generator = Generator()
    inputs = []
    transactions = []
    in_sum = 0
    gen = generator.gen_genesis()
    tree.add(gen.get_identifier(), gen)
    for i in range(5):
        trans = generator.gen_transaction()
        transactions.append(trans)
        for entry in trans.get_outputs():
            inputs.append(entry)
        in_sum += trans.get_value()
        tree.add(trans.get_identifier(), trans)

    return tree

def create_gw():
    ba = nettesthelpers.net_app(nettesthelpers.pseudo_peer(f"Gateway"))
    return ba

def create_valid_app(index: int, gateway_contact: PeerContactInfo, dag: Tree):
    ba = nettesthelpers.net_app(nettesthelpers.pseudo_peer(f"Peer-{index}"), [gateway_contact])
    agent = ckpttesthelpers.AgentSerivceMock([ckpttesthelpers.CheckpointCase1.private_keys[index]],
                                             dag)
    pc = ckpttesthelpers.pseudo_pc()
    ckpttesthelpers.ckpt_protocol_app(ba, ckpttesthelpers.CheckpointCase1, agent, pc)
    return ba, agent, pc

def main():
    gw = create_gw()
    # dag = gen_dag()
    validators = []
    dag = TestUtility().get_manual_tree()
    for index in range(ckpttesthelpers.CheckpointCase1.validator_count):
        ba, agent, pc = create_valid_app(index, gw.cs.contact, dag)
        validator = Validator(ba, agent, pc , index)
        validators.append(validator)

    logger.info("Created all validators.")
    sim = Simulation([va.ba for va in validators], 0.1)
    sim += gw
    try:
        sim.next_round(1000)
    finally:
        sim.close()

def test_ckpt_proposal():
    gw = create_gw()
    # dag = gen_dag()
    dag= TestUtility().get_manual_tree()
    ba, agent, pc = create_valid_app(1, gw.cs.contact, dag)
    validator = Validator(ba, agent, pc, 1)

    from abcckpt.proposal_cr_handler import ProposalCrHandler
    prop_cr: ProposalCrHandler =validator.ba.app("proposal_creator")

    from abcckpt.proposal_cr_handler import CheckpointContentCreator
    proposal = CheckpointContentCreator.create_ckpt(validator.pc.state, dag, b'dummypbkey', ckpttesthelpers.CheckpointCase1)

    assert proposal is not None


if __name__ == "__main__":
    # test_ckpt_proposal()
    main()