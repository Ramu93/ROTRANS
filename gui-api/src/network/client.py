import zmq
import logging
from os import getenv

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)
fileHandle = logging.FileHandler("out.log")
logger.addHandler(fileHandle)
formatter = logging.Formatter(
    "%(asctime)s - %(filename)s - %(levelname)s - %(message)s"
)
fileHandle.setFormatter(formatter)


class MessageTypes:
    GET_AGENT = "get_agent"
    GENERATE_KEY_PAIR = "generate_key_pair"
    GET_DAG = "get_dag"
    POST_TRANSACTION = "post_transaction"
    ADD_KEY = "add_key"
    GET_TRANSACTION_INFO = "get_transaction_info"
    GET_STAKE_DIST = "get_stake_distrib_resp"
    GET_ROUND_STATUS = "get_round_status"


class ZMQClient:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        logger.info("Connecting to ZMQ server...")
        # self.connect_socket()

    def connect_socket(self, port):
        self.socket.setsockopt(zmq.RCVTIMEO, 15000)
        zmq_server_ip = getenv("ZMQ_SERVER_SOCKET")
        if zmq_server_ip is not None:
            logging.info("Connecting to ZMQ server socket " + zmq_server_ip)
        self.socket.connect(f"tcp://%s:{port}" % zmq_server_ip)

    def disconnect_socket(self, port):
        zmq_server_ip = getenv("ZMQ_SERVER_SOCKET")
        self.socket.disconnect(f"tcp://%s:{port}" % zmq_server_ip)

    def reset_req_socket(self, port):
        """reset_req_socket function kills the old socket and reassigns with a new socket to prevent ZMQ deadlock and make it fail safe"""
        self.socket = self.context.socket(zmq.REQ)
        logger.info("Killing socket and reconnecting to ZMQ server...")
        self.connect_socket(port)

    def send_message(self, payload, port=5001, type="json"):
        message = None
        self.connect_socket(port)
        try:
            self.socket.send_json(payload)
            if type == "json":
                message = self.socket.recv_json()
            else:
                message = self.socket.recv_unicode()
        except zmq.Again:
            logging.error("ZMQ message TIMEOUT!")
            self.reset_req_socket(port)

        self.disconnect_socket(port)
        return message

    def get_agent(self, port):
        logger.info("Requesting agent...")
        payload = {
            "messageType": MessageTypes.GET_AGENT,
        }
        message = self.send_message(payload, port)
        logger.debug("Received response: " + str(message))
        return message

    def generate_key_pair(self, port):
        logger.info("Requesting key pair generation...")
        payload = {
            "messageType": MessageTypes.GENERATE_KEY_PAIR,
        }
        message = self.send_message(payload, port)
        logger.debug("Received response: " + str(message))
        return message

    def get_dag(self, port):
        logger.info("Requesting DAG...")
        payload = {
            "messageType": MessageTypes.GET_DAG,
        }
        message = self.send_message(payload, port)
        logger.debug("Received DAG")
        return message

    def post_transaction(self, port, recipient, value, mode, validator):
        logger.info("Posting transaction...")
        data = {
            "recipient": recipient,
            "value": value,
            "mode": mode,
            "validator": validator,
        }
        payload = {"messageType": MessageTypes.POST_TRANSACTION, "data": data}
        message = self.send_message(payload, port)
        logger.debug("Received agent after transactions")
        return message

    def add_key(self, port, key):
        logger.info("Adding key...")
        data = {"key": key}
        payload = {"messageType": MessageTypes.ADD_KEY, "data": data}
        message = self.send_message(payload, port, "string")
        logger.debug("Received response: " + str(message))
        return message

    def get_transaction_info(self, port, txn_id):
        logger.info("Requesting transaction information...")
        data = {"txn_id": txn_id}
        payload = {"messageType": MessageTypes.GET_TRANSACTION_INFO, "data": data}
        message = self.send_message(payload, port)
        logger.debug("Received transaction information")
        return message

    def get_stake_dist(self, port):
        logger.info("Requesting stake distribution information...")
        payload = {"messageType": MessageTypes.GET_STAKE_DIST}
        message = self.send_message(payload, port)
        logger.debug("Received stake distribution information")
        return message

    def get_round_status(self, port):
        logger.info("Requesting round status information...")
        payload = {"messageType": MessageTypes.GET_ROUND_STATUS}
        message = self.send_message(payload, port)
        logger.debug("Received round status information")
        return message
