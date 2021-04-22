from abc import abstractmethod  # library for abstract methods


class AgentInterface:
    """
    Interface for the Agent and the LocalMessageHandler classes.
    """

    @abstractmethod
    def add_keypair(self):
        return None

    @abstractmethod
    def get_agent(self):
        return None

    @abstractmethod
    def get_prefix_tree(self):
        return None

    @abstractmethod
    def __send_money(self, recipient, value, val_key):
        pass