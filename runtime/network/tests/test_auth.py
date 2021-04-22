
import unittest
from abcnet.auth import  AuthenticationHandler, MessageAuthenticatorImpl, MessageIdentification
from abcnet.nettesthelpers import pseudo_peer
from abcnet.networking import ContactBook
from abcnet.transcriber import Transcriber, Ping, Message, NetPrivKey
from abcnet import settings, nettesthelpers

settings.configure_test_logging()


class AuthenticationTests(unittest.TestCase):



    def setUp(self) -> None:
        t = Transcriber()
        t.write_text("Hello")
        t.next_msg()
        t.ping(Ping())

        self.m = t.msg
        self.p1 = pseudo_peer("P1")
        self.priv_key = NetPrivKey.from_seed(1)
        self.p1.public_key = self.priv_key.public_key_bytes

    def test_msg_identification(self):
        mi = MessageIdentification(self.p1)
        mi.authenticate(self.m)
        # ----
        # Assert that the idenitifier was added as the third part of the message
        # and that the identifier can be extracted.
        assert len(self.m.parts) == 3
        assert MessageIdentification.get_msg_sender_identifier(self.m).identifier == self.p1.identifier

    def test_msg_signature(self):
        ma = MessageAuthenticatorImpl(self.p1, self.priv_key)

        assert self.m.signature is None
        ma.authenticate(self.m)

        # ----
        # Assert that the message authentication implementation correctly sets its id to the end of the message.
        assert len(self.m.parts) == 3
        assert MessageIdentification.get_msg_sender_identifier(self.m).identifier == self.p1.identifier

        # ----
        # Assert that the message authentication impl also adds a signature to the message and this signature is legal.
        assert self.m.signature is not None
        msg_hash = MessageAuthenticatorImpl.calc_msg_hash(self.m)
        assert msg_hash is not None and len(msg_hash) > 0
        self.priv_key.private_key.public_key().verify(self.m.signature, msg_hash)


    def test_authentication_handler(self):
        cb = ContactBook(pseudo_peer(), [self.p1])
        auth_handler = AuthenticationHandler(cb)

        auth_handler.set_sender_id(self.m)
        assert self.m.sender is None
        auth_handler.verify_sign(self.m)
        assert not self.m.is_authenticated

        self.m.sender = self.p1
        auth_handler.verify_sign(self.m)
        assert not self.m.is_authenticated

        ma = MessageAuthenticatorImpl(self.p1, self.priv_key)
        ma.authenticate(self.m)

        # Create a copy of the message with only the content
        m2 = nettesthelpers.send_and_receive_msg(msg=self.m)

        auth_handler.set_sender_id(m2)
        assert m2.sender.identifier == self.p1.identifier
        auth_handler.verify_sign(m2)
        assert m2.is_authenticated
        assert m2.sender == self.p1
