
import logging

from uuid import uuid4

from abcnet import transcriber
from abcnet.services import BaseApp
from tests.demo.library import *
from abcnet.handlers import ItemExtraction
from abcnet.settings import configure_logging, configure_fast_test_network, configure_test_logging
from abcnet.simenv import configure_mocked_network_env, Simulation
from abcnet.nettesthelpers import pseudo_peer, net_app, RecordMsgReceiver, MockMsgSender

configure_test_logging()
logger = logging.getLogger("abctestnet")

configure_fast_test_network()
configure_mocked_network_env()


def basic_library_peer(name=None) -> BaseApp:
    peer = pseudo_peer(name)
    app = net_app(peer)
    lib = LibraryContent()
    app.register_app_layer("item_extract", ItemExtraction())
    app.register_app_layer("lib", LibraryMessageHandler(lib))
    return app


def get_internal_lib(app: BaseApp) -> LibraryContent:
    return app.app('lib').library_content


def fake_book(name = None) -> Book:
    if name is None:
        name = str(uuid4())
    return Book(name=name,
                year=random.randint(1900, 2021),
                rating=random.randint(0, 5))


def test_library():
    p1 = basic_library_peer('P1')

    books = [fake_book(f"book-{i}") for i in range(10)]

    for b in books:
        get_internal_lib(p1).books[b.id] = b

    receiver = RecordMsgReceiver()
    receiver.subscribe(p1.cs.contact)

    Simulation([p1]).next_round()

    def match_item_checklist(msg: Message) -> bool:
        return transcriber.parse_message_type(msg) == transcriber.MsgType.items_checklist

    book_checklist = receiver.next_matching_msg(match_item_checklist)
    assert book_checklist is not None
    book_checklist_parsed = transcriber.parse_item_qualifier(book_checklist)

    assert all([(LibraryItemType.BOOK, b.id) in book_checklist_parsed for b in books])

    sender = MockMsgSender()
    sender.direct_message(p1.cs.contact).fetch_items([(b.item_type(), b.item_qualifier()) for b in books])

    p1.handle_remaining_messages(0.05)
    p1.maintain(force_maintenance=True)

    # Simulation([p1], msg_timeout=0.5).next_round(4)

    def match_item_content(msg: Message) -> bool:
        return transcriber.parse_message_type(msg) == transcriber.MsgType.items_content

    book_content_msg = receiver.next_matching_msg(match_item_content)
    assert book_content_msg is not None
    item_content_raw = transcriber.parse_item_contents(book_content_msg)
    libparser = LibraryItemsParser()
    book_content_list = list(libparser.decode_item_list_raw(item_content_raw))


    for b in book_content_list:
        book_found = False
        for b2 in books:
            if b[1].id == b2.id:
                book_found = True
                break
        assert book_found
    p1.close()