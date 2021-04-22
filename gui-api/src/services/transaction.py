import logging
from services.agent import AgentUtil

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)
fileHandle = logging.FileHandler("out.log")
logger.addHandler(fileHandle)
formatter = logging.Formatter(
    "%(asctime)s - %(filename)s - %(levelname)s - %(message)s"
)
fileHandle.setFormatter(formatter)


class TransactionService:
    def __init__(self, zmq_client):
        self.zmq_client = zmq_client
        self.agent_util = AgentUtil()

    def make_transfer(self, port, recipient, value, mode, validator):
        """make_transfer function triggers the agent to create a new transaction.
        This function is asynchronous.
        :return: a string response from the ZMQ Server."""
        logger.info("Transfer to: " + recipient)
        logger.info("Transfer value: " + str(value))
        logger.info("Transfer mode: " + mode)
        logger.info("Transfer mode: " + validator)

        type = "Delegation"
        if mode == "recipient":
            type = "Transaction"

        # this call returns back the agent object
        response = self.zmq_client.post_transaction(
            port, recipient, str(value), type, validator
        )
        self.agent_util.process_agent(response["agent"])
        return {"agent": self.agent_util.get_agent()}

    def get_transaction_info(self, port, txn_id):
        """get_transaction_info method gets the transaction information from the agent. The purpose of this service call is to fetch the information about the transaction that is in the pending state and yet to be confirmed."""
        transaction_info = self.zmq_client.get_transaction_info(port, txn_id)
        if not transaction_info:
            return {}
        return self.agent_util.process_transaction_info(transaction_info)
