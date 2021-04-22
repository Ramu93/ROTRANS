import logging
from decimal import *

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)
fileHandle = logging.FileHandler("out.log")
logger.addHandler(fileHandle)
formatter = logging.Formatter(
    "%(asctime)s - %(filename)s - %(levelname)s - %(message)s"
)
fileHandle.setFormatter(formatter)


class NodeType:
    TXN = "txn"
    ACK = "ack"
    CHKPT = "chkpt"


class AgentUtil:
    def __init__(self):
        self.__dag = {"nodes": [], "links": []}

        self.__processed_agent = {}

    def get_dag(self):
        return self.__dag

    def get_agent(self):
        return self.__processed_agent

    def process_dag(self, dag):
        """process_dag method parses the dag received from the ZMQ server.
        It preprocesses the DAG and the list of transactions to a format demanded by the visualization mechanism.
        :param dag: The DAG with list of transactions and acknowledgements"""

        logger.info("processing DAG...")

        nodes = []
        links = []
        acks = set()
        ackInfoDict = {}
        txns = set()
        txnInfoDict = {}

        if not dag:
            return

        for transaction in dag:

            if transaction["type"] == NodeType.ACK:

                # add the id of the ack to the nodes
                acks.add(transaction["identifier"])
                # add the id of the previous to the nodes
                if transaction["prev_ack"] not in txns:
                    acks.add(transaction["prev_ack"])
                # transaction ids are also added to the transaction set here because sometimes the DAG does not contain the transaction but it has the acks for the transaction
                # the transaction might be a pending transaction
                txns.add(transaction["transaction_id"])
                # add the ack information to the dict
                # this info is used to populate information of ack
                ackInfoDict[transaction["identifier"]] = {
                    "prev_ack": transaction["prev_ack"],
                    "txn_id": transaction["transaction_id"],
                    "validator": transaction["validators"],
                }

            elif transaction["type"] == NodeType.CHKPT:
                link_color = "#000000"
                txns.add(transaction["identifier"])

                total_inputs = Decimal(0)
                for input in transaction["inputs"]:
                    total_inputs += Decimal(input["value"])

                total_outputs = Decimal(0)
                for output in transaction["outputs"]:
                    total_outputs += Decimal(output["value"])

                txnInfoDict[transaction["identifier"]] = {
                    "inputs": transaction["inputs"],
                    "outputs": transaction["outputs"],
                    "origin": transaction["origin"],
                    "total_inputs": str(total_inputs),
                    "total_outputs": str(total_outputs),
                    "total_fees": transaction["fees"],
                    "lock_time": transaction["lock_time"],
                    "miner": transaction["miner"],
                    "height": transaction["height"],
                    "ack_length": transaction["ack_length"],
                    "nutxo": transaction["nutxo"],
                    "total_stake": transaction["total_stake"],
                }

                # links.append(
                #     {"source": transaction["identifier"], "target": transaction["origin"], "color": link_color})

            else:
                # if transaction["type"] == NodeType.TXN:
                # add transaction id to the nodes
                txns.add(transaction["identifier"])

                total_inputs = Decimal(0)
                for input in transaction["inputs"]:
                    total_inputs += Decimal(input["value"])
                #     # add edge to the parent of the transaction if the parent exists in the tranactions list
                #     # because the parent will not exist in the Tree if the wallet is spent
                #     # if input["origin"] in txns:
                #     links.append(
                #         {"source": transaction["identifier"], "target": input["origin"], "color": link_color})

                total_outputs = Decimal(0)
                for output in transaction["outputs"]:
                    total_outputs += Decimal(output["value"])

                if total_inputs != 0:
                    total_fees = total_inputs - total_outputs
                else:
                    total_fees = "NA"

                # add transaction info to the dict
                # this info is used to populate information of the transaction
                # this information will be available only for confirmed transactions
                txnInfoDict[transaction["identifier"]] = {
                    "inputs": transaction["inputs"],
                    "outputs": transaction["outputs"],
                    "validator": transaction["validators"],
                    "identifier": transaction["identifier"],
                    "parents": transaction["parents"],
                    "total_inputs": str(total_inputs),
                    "total_outputs": str(total_outputs),
                    "total_fees": str(total_fees),
                }

        for ack in acks:
            if ack in ackInfoDict.keys():
                ackInfo = ackInfoDict[ack]
                graph_node = {
                    "id": ack,
                    "symbolType": "circle",
                    "color": "#6435C9",
                    "label": ack[:6],
                    "meta": {
                        "isTransaction": False,
                        "prev_ack": ackInfo["prev_ack"],
                        "txn_id": ackInfo["txn_id"],
                        "validator": ackInfo["validator"][0],
                        "isCheckpoint": False,
                    },
                }
                nodes.append(graph_node)
                link_color = "#dedede"
                # add edge from ack to previous ack
                if ackInfo["prev_ack"] in txns or (
                    ackInfo["prev_ack"] in acks
                    and ackInfo["prev_ack"] in ackInfoDict.keys()
                ):
                    links.append(
                        {
                            "source": ack,
                            "target": ackInfo["prev_ack"],
                            "color": link_color,
                        }
                    )

                # add edge from ack to the transaction pointed out by the ack
                if ackInfo["txn_id"] in txns:
                    links.append(
                        {
                            "source": ack,
                            "target": ackInfo["txn_id"],
                            "color": link_color,
                        }
                    )

        for txn in txns:
            if txn in txnInfoDict.keys():
                # confirmed transaction
                txnInfo = txnInfoDict[txn]
                isCheckpoint = False
                # node color for a transaction
                color = "#39B814"

                if txnInfo["total_inputs"] == "0":
                    # if inputs is 0, then the node would be a genesis
                    color = "#ff8214"
                elif "parents" not in txnInfo:
                    # if transaction has no parents, then the node is a checkpoint
                    color = "#ff0000"
                    isCheckpoint = True

                if not isCheckpoint:
                    graph_node = {
                        "id": txn,
                        "symbolType": "square",
                        "color": color,
                        "label": txn[:6],
                        "meta": {
                            "isTransaction": True,
                            "origin": txn,
                            "total_inputs": txnInfo["total_inputs"],
                            "total_outputs": txnInfo["total_outputs"],
                            "total_fees": txnInfo["total_fees"],
                            "inputs": txnInfo["inputs"],
                            "outputs": txnInfo["outputs"],
                            "isConfirmed": True,
                            "isCheckpoint": isCheckpoint,
                        },
                    }
                else:
                    graph_node = {
                        "id": txn,
                        "symbolType": "square",
                        "color": color,
                        "label": txn[:6],
                        "meta": {
                            "isTransaction": True,
                            "origin": txn,
                            "total_inputs": txnInfo["total_inputs"],
                            "total_outputs": txnInfo["total_outputs"],
                            "total_fees": txnInfo["total_fees"],
                            "inputs": txnInfo["inputs"],
                            "outputs": txnInfo["outputs"],
                            "isConfirmed": True,
                            "isCheckpoint": isCheckpoint,
                            "lock_time": txnInfo["lock_time"],
                            "ack_length": txnInfo["ack_length"],
                            "miner": txnInfo["miner"],
                            "nutxo": txnInfo["nutxo"],
                            "height": txnInfo["height"],
                            "total_stake": txnInfo["total_stake"],
                        },
                    }

                nodes.append(graph_node)

                link_color = "#000000"
                # for input in txnInfo["inputs"]:
                #     # add edge to the parent of the transaction if the parent exists in the tranactions list
                #     # because the parent will not exist in the Tree if the wallet is spent
                #     # not adding edges for checkpoints as the graph becomes complex
                #     if input["origin"] in txns and not isCheckpoint:
                #         links.append(
                #             {"source": txn, "target": input["origin"], "color": link_color})

                if not isCheckpoint:
                    for parent in txnInfo["parents"]:
                        if parent in txns:
                            links.append(
                                {"source": txn, "target": parent, "color": link_color}
                            )

                if isCheckpoint and txnInfo["origin"] in txns:
                    links.append(
                        {
                            "source": txn,
                            "target": txnInfo["origin"],
                            "color": link_color,
                        }
                    )

        self._txnInfoDict = txnInfoDict
        self.__dag["nodes"] = nodes
        self.__dag["links"] = links
        self._txns = txns
        self._acks = acks
        logger.info("DAG processing complete")

    def process_agent(self, agent):
        """process_agent method determines the balance by accumulating all the unspent outputs, extracts the key pairs for showing it on the UI.
        :param agent: The agent with list of key pairs and list of unspent outputs"""

        logger.info("Processing agent...")

        processed_agent = {}
        balance = 0

        for output in agent["balance"]:
            balance = Decimal(balance) + Decimal(output["value"])

        processed_agent["keys"] = agent["keys"]
        processed_agent["balance"] = str(balance)
        processed_agent["stake"] = agent["stake"]

        self.__processed_agent = processed_agent
        logger.info("Processing agent complete")

    def process_transaction_info(self, transaction_info):
        processed_txn_info = {}
        processed_txn_info["inputs"] = transaction_info["inputs"]
        processed_txn_info["outputs"] = transaction_info["outputs"]
        processed_txn_info["stake"] = transaction_info["stake"]
        processed_txn_info["parents"] = transaction_info["parents"]

        total_inputs = Decimal(0)
        for input in transaction_info["inputs"]:
            total_inputs += Decimal(input["value"])

        total_outputs = Decimal(0)
        for output in transaction_info["outputs"]:
            total_outputs += Decimal(output["value"])

        total_fees = total_inputs - total_outputs

        processed_txn_info["total_inputs"] = str(total_inputs)
        processed_txn_info["total_outputs"] = str(total_outputs)
        processed_txn_info["total_fees"] = str(total_fees)

        return processed_txn_info

    def process_pending_transactions(self, pending_transactions):

        for transaction in pending_transactions:
            # if in case the transaction is confirmed but still is availabe in the pending list then do not make it grey!
            if transaction["identifier"] in self._txnInfoDict.keys():
                continue

            graph_node = {
                "id": transaction["identifier"],
                "symbolType": "square",
                "color": "#C7C6C5",
                "label": transaction["identifier"][:6],
                "meta": {"isTransaction": True, "isConfirmed": False},
            }
            self.__dag["nodes"].append(graph_node)

            for parent in transaction["parents"]:
                if parent in self._txns:
                    self.__dag["links"].append(
                        {
                            "source": transaction["identifier"],
                            "target": parent,
                            "color": "#000000",
                        }
                    )

    def filter_edges(self):
        """
        Filters the edges of the computed DAG that have either src or target missing.
        """
        nodes = self.__dag["nodes"]
        links = self.__dag["links"]

        def has_node(id):
            for n in nodes:
                if n["id"] == id:
                    return True
            return False

        filtered_links = list()
        for l in links:
            source = l["source"]
            target = l["target"]
            if has_node(source) and has_node(target):
                filtered_links.append(l)

        self.__dag["nodes"] = nodes
        self.__dag["links"] = filtered_links
