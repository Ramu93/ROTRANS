from typing import List

from abccore.agent import Agent, Ed25519PrivateKey, Tree, Checkpoint


class AgentService:
    """
    Agent service resolves the dependency to agent specific functionalities.
    It is mainly used by the checkpoint system to communicate with the agent in an indirect way.
    """

    def __init__(self, agent: Agent):
        """
        Initializes the service by the
        """
        self.agent: Agent = agent

    def get_keypairs(self) -> List[Ed25519PrivateKey]:
        """
        Returns the set of private keys owned by the agent.
        """
        return self.agent.get_keys()

    def get_DAG(self) -> Tree:
        """
        Returns the current dag.
        """
        return self.agent.a_data.tree

    def add_txn_to_fetch_list(self, item_id):
        """
        Adds the checkpoint id to the agent checklist.
        param item_id(bytes): id of the transaction.
        """
        return self.agent.add_txn_to_fetch_list(item_id)

    def inject_checkpoint(self, ckpt: Checkpoint):
        """
        Injects a newly available checkpoint.
        """
        self.agent.inject_checkpoint(ckpt)
