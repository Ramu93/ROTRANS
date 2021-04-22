from abccore.network_datastructures import NetTransaction
from abcnet.structures import ItemType
from abcnet.transcriber import join_msg_parts
from abcnet.services import ChannelService
from abcnet.handlers import AbstractItemHandler, Message

from abccore.agent_items_parser import AgentItemsParser

from typing import Any, List


class AgentMessageHandler(AbstractItemHandler):
    """
    This class handles messages and requests from the push and pull protocol and adds data from the incoming stream to the specific lists which are handled in the subclass.
    """

    def __init__(self):
        """
        Initializes the lists/sets and sets some additional necessary parameters.
        """
        item_parser = AgentItemsParser()
        interesting_items = [
            ItemType.ACK,
            ItemType.TXN,
            ItemType.UNSPENT_WALLET_COLLECTION,
        ]
        super().__init__(interesting_items, item_parser)
        self.input_queue = dict()
        self.request_queue = set()
        self.checklist_queue = set()
        self.output_queue = list()

    def handle_item_content(
        self, cs: "ChannelService", msg: Message, item_type: int, item_content: Any
    ):
        """
        Handles messages which include an actual content e.g. as in a full transaction and puts it into the inputs_queue.
        :param cs: The given ChannelService (not used in this method but required by the superclass)
        :param msg: The message itself
        :param item_type: The item_type as defined in abcnet.structures
        :param item_content: The content itself, e.g. a NetTransaction
        """
        self.input_queue[item_content.item_qualifier()] = (item_type, item_content)

    def handle_item_request(
        self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str
    ):
        """
        Handles item requests from the network and puts them into the request_queue.
        :param cs: The given ChannelService (not used in this method but required by the superclass)
        :param msg: The message itself (not used in this method but required by the superclass)
        :param item_type: The item_type as defined in abcnet.structures
        :param item_qualifier: The ID of the requested item
        """
        self.request_queue.add((item_type, item_qualifier))

    def handle_item_checklist(
        self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str
    ):
        """
        Handles items which are offered by the network and puts them into the checklist_queue.
        :param cs: The given ChannelService (not used in this method but required by the superclass)
        :param msg: The message itself (not used in this method but required by the superclass)
        :param item_type: The item_type as defined in abcnet.structures
        :param item_qualifier: The ID of the requested item
        """
        self.checklist_queue.add((item_type, item_qualifier))

    def handle_item_notfound(
        self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str
    ):
        raise ModuleNotFoundError("Item could not be found.")
