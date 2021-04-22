from typing import Any, Dict, Set, Tuple, List
import random
import base64

from abcnet import transcriber
from abcnet.settings import NetStatSettings
from abcnet.services import ChannelService
from abcnet.handlers import MessageHandler, AbstractItemHandler
from abcnet.structures import ItemQualifier, ItemEncodeable, Message

from struct import pack
from enum import IntEnum
import hashlib

from abcnet.transcriber import ItemsParser, Parser

from abcnet.timer import SimpleTimer


def gen_book_id(book) -> str:
    m = hashlib.sha1()
    m.update(bytes(book.name, 'utf-8'))
    m.update(pack('i', book.year))
    m.update(pack('i', book.rating))
    hash_val: bytes = m.digest()
    hash_val_b64: str = base64.urlsafe_b64encode(hash_val).rstrip(b"=").decode("utf-8")
    return f"book-{hash_val_b64}"


def gen_catalogue_id(catalogue) -> str:
    m = hashlib.sha1()
    for b in catalogue.books:
        m.update(bytes(b.id, 'utf-8'))
    hash_val = m.hexdigest()
    return f"catalogue-{hash_val}"


class Book(ItemQualifier, ItemEncodeable):

    def __init__(self, name, year, rating, id=None):
        self.name = name
        self.year = year
        self.rating = rating
        self.id = id

        if self.id is None:
            # Generate the matching book id.
            self.id = gen_book_id(self)
        else:
            # Check the id if it was already defined
            self.check_id()

    def check_id(self):
        if self.id:
            calculated_id = gen_book_id(self)
            if calculated_id != self.id:
                raise ValueError(f"ID check doesn't match the book content: "
                                 f"Given id: {self.id},"
                                 f"Calculated id: {calculated_id}")

    def item_qualifier(self):
        return self.id

    def item_type(self):
        return LibraryItemType.BOOK

    def encode(self, transcriber):
        transcriber.write_text(self.id)
        transcriber.write_text(self.name)
        transcriber.integer(self.rating)
        transcriber.integer(self.year)


class Catalogue(ItemQualifier, ItemEncodeable):

    def __init__(self, books, id=None):
        self.books = books
        self.id = id

        if self.id is None:
            # Generate the matching book id.
            self.id = gen_catalogue_id(self)
        else:
            # Check the id if it was already defined
            self.check_id()

    def check_id(self):
        if self.id:
            calculated_id = gen_catalogue_id(self)
            if calculated_id != self.id:
                raise ValueError(f"ID check doesn't match the catalogue content: "
                                 f"Given id: {self.id},"
                                 f"Calculated id: {calculated_id}")

    def item_qualifier(self):
        return self.id

    def item_type(self):
        return LibraryItemType.CAT

    def encode(self, transcriber):
        transcriber.write_text(self.id)
        transcriber.integer(len(self.books))
        for b in self.books:
            b.encode(transcriber)


class LibraryItemType(IntEnum):
    BOOK = 0xeee001
    CAT = 0xeee002


class LibraryItemsParser(ItemsParser):

    def decode_item(self, item_type: int, parser: Parser) -> Any:
        if item_type == LibraryItemType.BOOK:
            _id = parser.consume_nested_text()
            name = parser.consume_nested_text()
            rating = parser.consume_int()
            year = parser.consume_int()
            return Book(name, year, rating, _id)
        elif item_type == LibraryItemType.CAT:
            _id = parser.consume_nested_text()
            book_count = parser.consume_int()
            books = []
            for i in range(book_count):
                self.decode_item(LibraryItemType.BOOK, parser)
            return Catalogue(books, _id)
        else:
            return None


class LibraryContent:
    books: Dict[str, Book]

    cats: Dict[str, Catalogue]

    missing_items: Set[Tuple[LibraryItemType, str]]

    new_items: Set[Tuple[LibraryItemType, str]]

    requested_items: Set[Tuple[LibraryItemType, str]]

    def __init__(self):
        self.books = dict()
        self.cats = dict()
        self.missing_items = set()
        self.new_items = set()
        self.requested_items = set()

    def cat_with_book(self, book_id):
        # Return true if at least one catalogue has a book with the given id.
        for cat in self.cats.values():
            for b2 in cat.books:
                if b2.id == book_id:
                    # The book is already contained.
                    return cat
        return None

    def find_content(self, item_type: int, item_id):
        if item_type == LibraryItemType.BOOK:
            if item_id in self.books:
                return self.books[item_id]
            else:
                cat = self.cat_with_book(item_id)
                for b2 in cat.books:
                    if b2.id == item_id:
                        return b2
        elif item_type == LibraryItemType.CAT:
            return self.cats[item_id]
        return None

    def has_content(self, item_type: int, item_id):
        if item_type == LibraryItemType.BOOK:
            return self.has_book(item_id)

        elif item_type == LibraryItemType.CAT:
            return self.has_cat(item_id)

        else:
            return False

    def has_book(self, book_id):
        # First check if the book is in a catalogue:
        if self.cat_with_book(book_id):
            return True
        # Lets look at loose books
        return book_id in self.books

    def has_cat(self, cat_id):
        return cat_id in self.cats

    def add_content(self, item_type: int, item_content):
        # Returns True if the content was added.
        if item_type == LibraryItemType.BOOK:
            return self.add_book(item_content)
        elif item_type == LibraryItemType.CAT:
            return self.add_catalogue(item_content)
        return False

    def add_book(self, book) -> bool:
        if not self.has_book(book.id):
            self.books[book.id] = book
            # New book added
            return True
        return False

    def add_catalogue(self, cat) -> bool:
        if not self.has_cat(cat.id):
            self.cats[cat.id] = cat
            # New cat added
            return True
        return False

    def mark_missing(self, item_type, item_id):
        self.missing_items.add(item_id)

    def mark_new(self, item_type, item_id):
        self.new_items.add((item_type, item_id))

    def mark_requested(self, item_type, item_id):
        self.requested_items.add((item_type, item_id))


class LibraryMessageHandler(AbstractItemHandler):

    def __init__(self, lc: LibraryContent):
        # Initialize AbstractItemHandler with the list of interesting item type and a parser.
        super(LibraryMessageHandler, self).__init__([LibraryItemType.BOOK, LibraryItemType.CAT],
                                                    LibraryItemsParser())
        # Global Set of Data
        self.library_content = lc
        # Timers for maintenance:
        self.timeout_timers = [
            (self.send_checklist, SimpleTimer(5.0)),
            (self.send_new, SimpleTimer(0.5)),
            (self.send_request_for_missing, SimpleTimer(0.5)),
            (self.send_content_of_requested, SimpleTimer(0.5)),
            (self.clean_books, SimpleTimer(10.0)),
        ]

    def handle_item_content(self, cs: "ChannelService", msg: Message, item_type: int, item_content: Any):
        is_new = self.library_content.add_content(item_type, item_content)
        if is_new:
            # If it is a new entry, mark it so.
            self.library_content.mark_new(item_type, item_content)
        if item_content.item_qualifier() in self.library_content.missing_items:
            self.library_content.missing_items.remove(item_content.item_qualifier())

    def handle_item_request(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        # Mark that the item is being requested.
        # Broadcast the item at a later point.
        self.library_content.mark_requested(item_type, item_qualifier)

    def handle_item_checklist(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        if not self.library_content.has_content(item_type, item_qualifier):
            # Item from the checklist is missing.
            # Mark that it is missing so it can be requested at a later point.
            self.library_content.mark_missing(item_type, item_qualifier)

    def handle_item_notfound(self, cs: "ChannelService", msg: Message, item_type: int, item_qualifier: str):
        # Ignore Item not found messages.
        pass

    def perform_maintenance(self, cs: "ChannelService", force_maintenance=False):
        for maintenance_method, timer in self.timeout_timers:
            if force_maintenance or timer():
                # Timer of action has reached zero.
                # Perform maintenance action by calling the method that has the action_name.
                maintenance_method(cs)

    @staticmethod
    def select_random_subset(super_set: List, subset_size=1000):
        if len(super_set) <= subset_size:
            return super_set
        random.shuffle(super_set)
        return super_set[:subset_size]

    def send_checklist(self, cs: "ChannelService"):
        checklist = list()
        # Add a subset of loose books:
        checklist += self.select_random_subset(list(self.library_content.books.values()), 990)
        # Add a subset of catalogues:
        checklist += self.select_random_subset(list(self.library_content.cats.values()), 10)

        if checklist:
            # Broadcast checklist:
            cs.broadcast_channel().checklist(checklist)

    def send_content_of_requested(self, cs: ChannelService):
        requested_items = list(self.library_content.requested_items)
        if len(requested_items) == 0:
            return

        # Only consider those items whose content is present:
        def content_of_requested_item_is_present(item_tuple):
            item_type, item_id = item_tuple
            if self.library_content.has_content(item_type, item_id):
                return True
            return False

        requested_items_id = list(filter(content_of_requested_item_is_present, requested_items))
        # Only select 100 random items:
        requested_items_id = self.select_random_subset(requested_items_id, 100)

        # Retrieve the content of the requested items. Currently we only have a list of item ids:
        def find_item_content(item_tuple):
            item_type, item_id = item_tuple
            return self.library_content.find_content(item_type, item_id)

        requested_items_content = list(map(find_item_content, requested_items_id))
        # Broadcast the content to the network:
        cs.broadcast_channel().items(requested_items_content)
        # From the set of requested items, remove those that we have sent now:
        for sent_item in requested_items_id:
            self.library_content.requested_items.remove(sent_item)

    def send_request_for_missing(self, cs: ChannelService):
        # Create a list of missing items:
        missing_item_list = list(self.library_content.missing_items)
        # Limit the amount of items that are sent, by picking a random subset:
        missing_item_list = self.select_random_subset(missing_item_list)
        if missing_item_list:
            # Broadcast the request of the list to the network:
            cs.broadcast_channel().fetch_items(missing_item_list)

    def send_new(self, cs: "ChannelService"):
        new_items = list(self.library_content.new_items)
        new_items = self.select_random_subset(new_items)
        if new_items:
            cs.broadcast_channel().checklist(new_items)
            # remove the mark of the items that we just sent
            for old_item in new_items:
                self.library_content.new_items.remove(old_item)

    def clean_books(self, cs: "ChannelService"):
        # Search all books that are currently loose but are also in a catalogue.
        duplicate_books = list()
        for book_id in self.library_content.books.keys():
            if self.library_content.cat_with_book(book_id):
                duplicate_books.append(book_id)
        # Remove the assembled list of duplicate books:
        for book_id in duplicate_books:
            del self.library_content.books[book_id]


def book_packer(encoded: bytes = None, book: Book = None, parser=LibraryItemsParser()) -> Dict[str, Any]:
    if book is None:
        book: Book = parser.decode_item_bytes(LibraryItemType.BOOK, encoded)
    return {
        'name': book.name,
        'year': book.year,
        'rating': book.rating,
        'id': book.id
    }
NetStatSettings.item_packer_oracle()[LibraryItemType.BOOK] = book_packer

def cat_packer(encoded: bytes, parser=LibraryItemsParser()) -> Dict[str, Any]:
    cat: Catalogue = parser.decode_item_bytes(LibraryItemType.CAT, encoded)
    return {
        'books': [book_packer(book=b) for b in cat.books],
        'id': cat.id
    }
NetStatSettings.item_packer_oracle()[LibraryItemType.CAT] = cat_packer
