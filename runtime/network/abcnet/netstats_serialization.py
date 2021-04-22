import math
import time
from typing import List, Dict, Tuple, Any, Callable, Union
from abcnet import transcriber
from abcnet.structures import Message, MsgType, Ping, Pong, PeerContactQualifier, PeerContactInfo
from abcnet.settings import NetStatSettings


def format_time(timestamp: float):
    milli_seconds = f"{timestamp - math.floor(timestamp):0.4f}"[2:]
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)) + "." + milli_seconds


def pack_ping(p: Ping) -> Dict:
    return {
        'original_peer': p.original_peer.identifier,
        'ping_id': p.ping_id,
        'send_time': format_time(p.send_time.start_time)
    }


def pack_pong(p: Pong) -> Dict:
    return {
        'ping': pack_ping(p.ping),
        'replier_peer': p.replier.identifier,
        'reply_time': format_time(p.reply_time.start_time),
    }


def pack_contacts_qualifiers(contacts: List[PeerContactQualifier]) -> Dict:
    return {
        'size' : len(contacts),
        'qualifiers' : [
            c.identifier for c in contacts
        ]
    }


def pack_contact_info(c: PeerContactInfo) -> Dict:
    return {
        'id' : c.identifier,
        'pub_addr': c.publish_addr,
        'rec_addr': c.receive_addr,
    }


def pack_contacts(contacts: List[PeerContactInfo]) -> Dict:
    return {
        'size': len(contacts),
        'infos': [
            pack_contact_info(c) for c in contacts
        ]
    }


def pack_item_id_list(item_ids: List[Tuple[int, str]]) -> List:

    return [
        {'item_type':
             NetStatSettings.item_type_oracle().get(i[0], i[0]),
         'item_id': i[1]
         }
        for i in item_ids
    ]


def pack_item_content(item_type: int, item_content: bytes) -> Any:
    packer = NetStatSettings.item_packer_oracle().get(item_type)
    if packer is None:
        return item_content.hex()
    else:
        return packer(item_content)

def pack_item_content_list(item_ids: List[Tuple[int, bytes]]) -> List:
    return [
        {'item_type':
             NetStatSettings.item_type_oracle().get(i[0], i[0]),
         'item_content': pack_item_content(i[0], i[1])
         }
        for i in item_ids
    ]






def default_item_types() -> Dict[int, str]:
    from abcnet.structures import ItemType
    return {
        ItemType.TXN: 'TXN',
        ItemType.ACK: 'ACK',
        ItemType.CHP: 'CHP',
        0xeee001: 'BOOK',
        0xeee002: 'CAT',
    }


def default_msg_packers() -> Dict[int,
                                  Callable[[Message], Union[Dict, List, int, str]]]:
    contacts_ids_packer = lambda m: pack_contacts_qualifiers(transcriber.parse_contacts_qualifier(m))
    item_ids_packer = lambda m: pack_item_id_list(transcriber.parse_item_qualifier(m))
    return {
        MsgType.ping: lambda m: pack_ping(transcriber.parse_ping(m)),
        MsgType.pong: lambda m: pack_pong(transcriber.parse_pong(m)),
        MsgType.contacts_checklist: contacts_ids_packer,
        MsgType.contacts_request: contacts_ids_packer,
        MsgType.contacts_content: lambda  m: pack_contacts(transcriber.parse_contacts(m)),
        MsgType.items_checklist: item_ids_packer,
        MsgType.items_notfound: item_ids_packer,
        MsgType.items_request: item_ids_packer,
        MsgType.items_content: lambda m: pack_item_content_list(transcriber.parse_item_contents(m))
    }


def default_item_packer():
    return {

    }
