from flask import Flask, jsonify, request
from flask_cors import CORS

from network.client import ZMQClient
from services.agent import AgentService
from services.transaction import TransactionService

app = Flask(__name__)
CORS(app)

zmqClient = ZMQClient()
agent_service = AgentService(zmqClient)
transaction_service = TransactionService(zmqClient)


@app.route("/health")
def health():
    return "success"


@app.route("/agent", methods=["GET"])
def agent():
    port = request.args.get("port")
    return agent_service.get_agent(port)


@app.route("/keys", methods=["POST"])
def key_pair():
    port = request.args.get("port")
    return agent_service.generate_key_pair(port)


@app.route("/transfer", methods=["POST"])
def transfer():
    request_body = request.get_json()
    port = request.args.get("port")
    agent = transaction_service.make_transfer(
        port,
        request_body["recipient"],
        request_body["value"],
        request_body["mode"],
        request_body["validator"],
    )
    return jsonify(agent)


@app.route("/dag")
def dag():
    port = request.args.get("port")
    return jsonify(agent_service.get_dag_from_agent(port))


@app.route("/addKey", methods=["POST"])
def add_key():
    request_body = request.get_json()
    port = request.args.get("port")
    status = agent_service.add_key(port, request_body["key"])
    return jsonify({"status": status})


@app.route("/transaction")
def get_transaction_info():
    port = request.args.get("port")
    txn_id = request.args.get("txn_id")
    txn_info = transaction_service.get_transaction_info(port, txn_id)
    return jsonify(txn_info)


@app.route("/stake_dist")
def get_stake_dist_info():
    port = request.args.get("port")
    stake_dist_info = agent_service.get_stake_dist(port)
    return jsonify(stake_dist_info)

@app.route("/round_status")
def get_round_status():
    port = request.args.get("port")
    return jsonify(agent_service.get_round_status(port))


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=True)
