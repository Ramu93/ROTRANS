import logging
from flask import jsonify
from decimal import *
from services.agent_util import AgentUtil

# from fixtures.agent import agent_fixture
# from fixtures.ProcessedDAG import processed_dag
# from fixtures.DAG import dag


logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)
fileHandle = logging.FileHandler("out.log")
logger.addHandler(fileHandle)
formatter = logging.Formatter(
    "%(asctime)s - %(filename)s - %(levelname)s - %(message)s"
)
fileHandle.setFormatter(formatter)


class AgentService:
    def __init__(self, zmq_client):
        self.zmq_client = zmq_client
        self.agent_util = AgentUtil()

    def get_agent(self, port):
        """get_agent function requests for the agent object through the local communication channel.
        Preprocessing of agent is handled by AgentUtil."""

        logger.info("fetching agent")
        response = self.zmq_client.get_agent(port)
        self.agent_util.process_agent(response["agent"])
        return {
            "agent": self.agent_util.get_agent(),
            "transaction_fee": response["transaction_fee"],
        }

    def generate_key_pair(self, port):
        """generate_key_pair function triggers the agent through the local communication channel to generate a new public-private key pair.
        This function is asynchronous.
        :returns: a string response from the ZMQ Server"""
        logger.info("generate key pair")
        response = self.zmq_client.generate_key_pair(port)
        self.agent_util.process_agent(response["agent"])
        return self.agent_util.get_agent()

    def get_dag_from_agent(self, port):
        """get_dag_from_agent function requests for the DAG from the agent (agent's perspective of the DAG) through the local communication channel.
        Preprocessing of the DAG is handled by AgentUtil."""
        logger.info("fetching dag")
        response = self.zmq_client.get_dag(port)
        dag = response["dag"]
        pending_transactions = response["pending_transactions"]
        round_status = response["round_status"]
        self.agent_util.process_dag(dag)
        self.agent_util.process_pending_transactions(pending_transactions)
        self.agent_util.filter_edges()
        return {
            "dag": self.agent_util.get_dag(),
            "round_status": round_status
        }

    def add_key(self, port, key):
        """add_key function triggers the agent to add the given key
        :param key: public key"""
        # return "success"
        return self.zmq_client.add_key(port, key)

    def get_stake_dist(self, port):
        return self.zmq_client.get_stake_dist(port)

    def get_round_status(self, port):
        return self.zmq_client.get_round_status(port)
