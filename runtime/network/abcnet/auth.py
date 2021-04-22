from typing import Union, Optional
import logging

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from abcnet import structures
from abcnet.handlers import MessageHandler
from abcnet.networking import ContactBook
from abcnet.outch import MessageAuthenticator
from abcnet.structures import Message, NetPrivKey, PeerContactInfo, PeerContactQualifier
from abcnet.transcriber import Transcriber, Parser

logger = logging.getLogger(__name__)


class NoMessageAuthenticator(MessageAuthenticator):
    """
    Performs no authentication by appending an empty string.
    """

    def authenticate(self, msg: Message):
        pass


class MessageIdentification(MessageAuthenticator):
    """
    Performs message identification by putting the sender as the third message part.
    """

    def __init__(self, contact_info: PeerContactInfo):
        if contact_info is None:
            raise ValueError()
        self.contact_info: PeerContactInfo = contact_info

    def authenticate(self, msg: Message):
        if len(msg.parts) > 2:
            raise ValueError("The identification part already exists in message.")
        transcriber = Transcriber()
        transcriber.contact_qualifier(self.contact_info)
        msg.add_part(transcriber.content)
        msg.sender = self.contact_info

    @staticmethod
    def get_msg_sender_identifier(msg: Message) -> Optional[PeerContactQualifier]:
        if len(msg.parts) <= 2:
            return None
        id_bytes = msg.parts[2]
        if id_bytes is None or len(id_bytes) == 0:
            return None
        try:
            sender_id = Parser(id_bytes).parse_nested().consume_contact_qualifier()
            return sender_id
        except Exception as ex:
            logger.warning("Error trying to parse identity part of message:\n%s", id_bytes, exc_info=ex,
                           stack_info=True)
            return None


class MessageAuthenticatorImpl(MessageIdentification):
    """
    Signs the message based on the given key.
    Inherits message identification because authentication implies identification.
    """

    def __init__(self, contact_info: PeerContactInfo, private_key: NetPrivKey):
        if private_key is None:
            raise ValueError()
        MessageIdentification.__init__(self, contact_info)
        self.private_key: NetPrivKey = private_key
        if contact_info.public_key is None:
            raise ValueError("The contact info doesn't specify a pub key.")
        if contact_info.public_key != private_key.public_key_bytes:
            raise ValueError("The contact public key doesn't match its private key.")

    @staticmethod
    def calc_msg_hash(msg: Message) -> bytes:
        digest = hashes.Hash(hashes.SHA256())
        for p in msg.parts:
            digest.update(p)
        msg_hash = digest.finalize()
        return msg_hash

    def authenticate(self, msg: Message):
        if False and not msg.final:
            logger.warning("Calculating the signature of a non-final message. Caller:\n %s", structures.get_caller())
        MessageIdentification.authenticate(self, msg)
        msg_hash = self.calc_msg_hash(msg)
        sign = self.private_key.private_key.sign(msg_hash)
        msg.signature = sign


class AuthenticationHandler(MessageHandler):
    """
    Handles the extraction of identification and authentication of incoming messages.
    """

    def __init__(self, cb: ContactBook):
        self.__cb = cb

    def accept(self, cs: "ChannelService", msg: Message):
        self.set_sender_id(msg)
        self.verify_sign(msg)

    def set_sender_id(self, msg: Message) -> Optional[PeerContactQualifier]:
        sender_id = MessageIdentification.get_msg_sender_identifier(msg)
        if sender_id is None:
            return None
        try:
            if self.__cb.is_self_contact(sender_id):
                msg.sender = self.__cb.self_contact
            elif sender_id in self.__cb:
                peer = self.__cb.get_peer(sender_id)
                msg.sender = peer.peer_contact
            return msg.sender
        except Exception:
            return None

    @staticmethod
    def verify_sign(msg: Message):
        if msg.signature is None or len(msg.signature) == 0:
            logger.debug("Message from has no signature")
            return
        if msg.sender is None:
            return
        elif not isinstance(msg.sender, PeerContactInfo):
            logger.warning("We cannot check the authenticity of a message from %s "
                           "as we do not have the full contact information.", msg.sender.identifier)
            return
        elif msg.sender.public_key is None or not msg.sender.public_key:
            logger.warning("The public key of the sender %s contact info is empty. "
                           "We cannot verify the signature of the message.", msg.sender.identifier)
            return
        pub_k = NetPrivKey.pub_key_from_bytes(msg.sender.public_key)
        AuthenticationHandler.verify_and_set_msg_authenticated(msg, pub_k)

    @staticmethod
    def verify_and_set_msg_authenticated(msg: Message, pub_k: Ed25519PublicKey):
        try:
            msg_hash = MessageAuthenticatorImpl.calc_msg_hash(msg)
            pub_k.verify(msg.signature, msg_hash)
            msg._Message__set_authenticated()
        except Exception as e:
            logger.debug("Error trying to verify message. ", exc_info=e, stack_info=True)
            return
