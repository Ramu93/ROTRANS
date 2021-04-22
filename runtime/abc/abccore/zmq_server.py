import zmq
from abccore.prefix_tree import *
from abccore.agent import *

from abccore.agent_interface import AgentInterface
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from abccore.constants import TRANSACTION_FEE

# this port is overritten by initializer
PORT = 5001

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)
fileHandle = logging.FileHandler("zmq_server.log")
logger.addHandler(fileHandle)
formatter = logging.Formatter(
    "%(asctime)s - %(filename)s - %(levelname)s - %(message)s"
)
fileHandle.setFormatter(formatter)


class NodeType:
    TXN = "txn"
    ACK = "ack"
    CHKPT = "chkpt"


def json_wallet(wallet):
    return {
        "value": str(wallet.get_value()),
        "public_key": str(wallet.get_pk().hex()),
        "origin": str(wallet.get_origin().hex()),
    }


class AgentUtil:
    def __init__(self):
        self.__agent = {}
        self.__transactions = []

    def get_agent(self):
        return self.__agent

    def get_transactions(self):
        return self.__transactions

    def clear_transactions(self):
        self.__transactions = []

    def process_agent(self, agent: "Agent"):
        """process_agent function converts the keyset and balance to a list of dicts """
        keyset = agent.a_data.keyset
        balance_outputs = agent.a_data.balance
        agent_formatted = dict()
        agent_formatted["keys"] = []
        agent_formatted["balance"] = []
        agent_formatted["stake"] = str(agent.get_stake())

        for i in range(0, len(keyset)):
            public_key = (
                keyset[i]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
                .hex()
            )
            private_key = (
                keyset[i]
                .private_bytes(
                    encoding=Encoding.Raw,
                    format=PrivateFormat.Raw,
                    encryption_algorithm=NoEncryption(),
                )
                .hex()
            )

            agent_formatted["keys"].append(
                {"public_key": public_key, "secret_key": private_key}
            )

        for output in balance_outputs:
            agent_formatted["balance"].append(json_wallet(output))

        self.__agent = agent_formatted

    def parse_tree_node(self, treenode):
        """parse_tree_node function parses the Tree or TreeNode and extracts its descendants
        :param treenode: TreeNode descendants of Tree or the Tree itself"""
        for ele in treenode.childs:
            if isinstance(ele, TreeLeaf):
                self.__extract_transaction(ele.get_node())
            elif isinstance(ele, TreeNode):
                self.parse_tree_node(ele)

    def __extract_transaction(self, node):
        """extract_transaction function parses the transaction node and extracts the inputs and outputs.
        It accumulates all the transactions as a list of dictionaries
        :param node: TreeNode that is a part of a valid Tree"""
        inputs = []
        outputs = []
        validators = []
        parents = []

        if node.signatures is not None:
            for signature in node.signatures:
                validators.append(signature[0].hex())

        if isinstance(node, Acknowledge):
            self.__transactions.append(
                {
                    "validators": validators,
                    "identifier": node.get_identifier().hex(),
                    "prev_ack": node.prev_ack.hex(),
                    "transaction_id": node.transaction.hex(),
                    "type": NodeType.ACK,
                }
            )

        elif isinstance(node, Checkpoint):
            # this is the actual outputs of the checkpoints
            for input in node.get_utxos():
                inputs.append(json_wallet(input))

            # this gives the total fee rewards split up
            for output in node.get_outputs():
                outputs.append(json_wallet(output))

            # list of wallets corresponding to the fees
            fees = str(node.value)

            self.__transactions.append(
                {
                    "identifier": node.get_identifier().hex(),
                    "inputs": inputs,
                    "origin": node.get_origin().hex(),
                    "height": node.get_height(),
                    "miner": node.get_miner().hex(),
                    "lock_time": str(node.get_locktime()),
                    "ack_length": node.get_acklength(),
                    "total_stake": str(node.total_stake),
                    "nutxo": node.nutxo,
                    "outputs": outputs,
                    "fees": fees,
                    "type": NodeType.CHKPT,
                }
            )

        else:

            for input in node.inputs:
                inputs.append(json_wallet(input))

            for output in node.get_outputs():
                outputs.append(json_wallet(output))

            node_parents = node.get_parents()
            if node_parents is not None:
                for parent in node.get_parents().keys():
                    parents.append(parent.hex())

            self.__transactions.append(
                {
                    "inputs": inputs,
                    "outputs": outputs,
                    "validators": validators,
                    "parents": parents,
                    "identifier": node.get_identifier().hex(),
                    "type": NodeType.TXN,
                }
            )

    def process_transaction_info(self, data):
        """process_transaction_info method extracts the transaction information along with its stake
        :param data: list containing two elements. Transaction object at index 0 and stake (Decimal) at index 1"""
        if not data:
            return []
        stake = str(data[1])
        transaction = data[0]
        inputs = []
        outputs = []
        parents = []

        for input in transaction.inputs:
            inputs.append(json_wallet(input))

        for output in transaction.get_outputs():
            outputs.append(json_wallet(output))

        for parent in transaction.get_parents().keys():
            parents.append(parent.hex())

        return {
            "identifier": transaction.get_identifier().hex(),
            "inputs": inputs,
            "outputs": outputs,
            "parents": parents,
            "stake": stake,
        }

    def process_pending_transactions(self, pending_transactions):
        """process_pending_transactions method parses the list of pending transactions"""
        processed_pending_transactions = []
        for transaction in pending_transactions:
            processed_pending_transactions.append(
                self.process_transaction_info(transaction)
            )
        return processed_pending_transactions


class MessageTypes:
    GET_AGENT = "get_agent"
    GENERATE_KEY_PAIR = "generate_key_pair"
    GET_DAG = "get_dag"
    POST_TRANSACTION = "post_transaction"
    ADD_KEY = "add_key"
    GET_TRANSACTION_INFO = "get_transaction_info"
    GET_STAKE_DIST = "get_stake_distrib_resp"
    GET_ROUND_STATUS = "get_round_status"


class LocalMessageHandler(AgentInterface):
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        try:
            self.socket.bind("tcp://*:%s" % PORT)
        except Exception as e:
            print("Address already in use: tcp://*:%s" % PORT)
            import traceback

            traceback.print_exc()
        logger.info("Socket listening to " + str(PORT))
        self.agent_util = AgentUtil()

    def handle(self, request):
        """handle function triggers the most relevant function based on the type of request.
        It returns the response generated by the callee function either as JSON or String.
        :param request: a dictionary which contains messageType (obligatory) and data (optional) fields"""
        default = "No handler"
        message_type = request["messageType"]
        logger.info("Received request: " + message_type)
        if "data" in request:
            return getattr(self, "case_" + message_type, lambda: default)(
                request["data"]
            )

        return getattr(self, "case_" + message_type, lambda: default)()

    def send_agent(self):
        agent = self.get_agent()
        if agent is not None:
            self.agent_util.process_agent(agent)
            self.socket.send_json(
                {
                    "agent": self.agent_util.get_agent(),
                    "transaction_fee": str(TRANSACTION_FEE),
                }
            )
            logger.info("Response sent...")

    def case_get_agent(self):
        """case_get_agent function gets tree related to the agent - public_key, secret_key, balance/stake.
        It responds to the ZMQ client with the tree as JSON."""
        self.send_agent()

    def case_generate_key_pair(self):
        """case_generate_key_pair function triggers the agent to generate a new key pair.
        It responds/acknowledges to the ZMQ client with a string."""
        self.add_keypair()
        # self.socket.send_unicode("success")
        self.send_agent()
        logger.info("Response sent...")

    def case_get_dag(self):
        """case_get_dag function gets the Tree and makes use of the agent_util object to parse Tree.
        It responds to the ZMQ client with the tree as JSON."""
        agent: Agent = self.get_agent()
        tree = self.get_prefix_tree()
        self.agent_util.clear_transactions()
        self.agent_util.parse_tree_node(tree)
        dag = self.agent_util.get_transactions()
        pending_txn = agent.pending_transactions
        if pending_txn is None:
            pending_txn = dict()
        pending_transactions = self.agent_util.process_pending_transactions(
            pending_txn.values()
        )
        round_status = agent.checkpoint_service.get_pc_state()
        self.socket.send_json(
            {
                "dag": dag,
                "pending_transactions": pending_transactions,
                "round_status": round_status,
            }
        )
        logger.info("Response sent...")

    def case_add_key(self, data):
        """case_add_key function pushes the key to the agent.
        :param data: a dictionary containing - key"""
        agent = self.get_agent()
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(data["key"]))
        agent.add_pregenerated_keypair(key)
        self.socket.send_unicode("success")
        logger.info("Response sent...")

    def case_post_transaction(self, data):
        """case_post_transaction function pushes the transaction to the agent.
        :param data: a dictionary containing - recipient: public_key of the receiver,
        value: total value of the transaction,
        mode: Transaction or Delegation
        The function responds/acknowledges to the ZMQ client with a string.
        @Override"""
        recipient = data["recipient"]  # public of the receiver
        value = data["value"]
        mode = data["mode"]

        if mode == "Transaction":
            val_key = (
                self.a_data.keyset[self.a_data.key_to_use]
                .public_key()
                .public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
            )
        else:  # mode == "Delegation"
            val_key = bytes.fromhex(data["validator"])

        recipient_bytes = bytes.fromhex(recipient)

        self._Agent__send_money(recipient_bytes, value, val_key)
        # self.socket.send_unicode("success")
        # send the agent object as it has the updated balance
        self.send_agent()

    def case_get_stake_distrib_resp(self):
        agent: Agent = self.get_agent()
        owners = agent.checkpoint_service.get_stake_owners()
        key_set = set(agent.get_pub_keys())
        is_owner = lambda pub_k: pub_k in key_set
        stake_distrib = list()

        if owners is not None:
            for owner in owners:
                owner: bytes
                owner_stake = {
                    "public_key": owner.hex(),
                    "stake_t": str(agent.checkpoint_service.delegated_stake(owner)),
                    "stake_p": str(
                        (
                            Decimal(100.0)
                            * (agent.checkpoint_service.delegated_stake(owner))
                            / agent.checkpoint_service.stake_sum()
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    )
                    + " %",
                    "agent_is_owner": is_owner(owner),
                }
                stake_distrib.append(owner_stake)

        self.socket.send_json(stake_distrib)

        logger.info("Response sent for stake distribution information")

    def case_get_transaction_info(self, data):
        """case_get_transaction_info method gets the latest information about a transaction if the transaction is yet to be confirmed.
        :param transaction_id: identifier of the transaction in hex"""
        agent = self.get_agent()
        txn_id = bytes.fromhex(data["txn_id"])
        if txn_id in agent.pending_transactions.keys():
            transaction_info = agent.pending_transactions[txn_id]

        else:
            transaction_info = []
        self.socket.send_json(
            self.agent_util.process_transaction_info(transaction_info)
        )

        logger.info("Response sent for transaction information")

    def case_get_round_status(self):
        agent: Agent = self.get_agent()
        round_status = agent.checkpoint_service.get_pc_state()

        self.socket.send_json({"round_status": round_status})

        logger.info("Response sent for round status information")
