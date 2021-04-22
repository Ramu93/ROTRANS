import logging
import time
from typing import List, Union

from abcnet import transcriber
from abcnet.services import BaseApp
from abcnet.settings import configure_logging, configure_fast_test_network, configure_test_logging
from abcnet.structures import Ping, MsgType, Message, PeerContactInfo
from abcnet import nettesthelpers
from abcnet.nettesthelpers import pseudo_peer, pseude_cs, MockMsgSender, RecordMsgReceiver
from abcnet.transcriber import parse_ping
from abcnet.simenv import configure_mocked_network_env, Simulation

configure_test_logging()
logger = logging.getLogger(__name__)
configure_fast_test_network()
configure_mocked_network_env()


def test_late_sub():
    cs1 = pseude_cs()
    cs2 = pseude_cs()

    cs1.broadcast_channel().ping()

    msg = cs2.poll_msg()
    assert msg is None

    cs2.net_maintainer.enter_contacts(cs2, [cs1.contact])

    msg = cs2.poll_msg()
    assert msg is None

    ping = Ping()
    cs1.broadcast_channel().ping(ping)

    msg = cs2.poll_msg()
    assert msg is not None

    parsed_ping = parse_ping(msg)

    assert parsed_ping == ping

    cs3 = pseude_cs()

    cs1.broadcast_channel().ping(ping)

    cs3.net_maintainer.enter_contacts(cs3, [cs1.contact])
    ping2 = Ping()
    time.sleep(0.05)
    cs1.broadcast_channel().ping(ping2)

    parsed_ping = parse_ping(cs2.poll_msg(1))
    assert parsed_ping == ping
    parsed_ping = parse_ping(cs2.poll_msg(1))
    assert parsed_ping == ping2

    parsed_ping = parse_ping(cs3.poll_msg(1))
    assert parsed_ping == ping2


def scenario_0() -> List[BaseApp]:
    new_peers = [
        pseudo_peer("P0"),
        pseudo_peer("P1"),
        pseudo_peer("P2"),
        pseudo_peer("P3")
    ]
    p0 = new_peers[0]
    apps = list()
    apps.append(nettesthelpers.net_app(p0, new_peers[1:]))
    apps += [nettesthelpers.net_app(p, [p0]) for p in new_peers[1:]]
    return apps


def scenario_1():
    new_peers = [
        pseudo_peer("P0"),
        pseudo_peer("P1"),
        pseudo_peer("P2"),
        pseudo_peer("P3")
    ]
    p0 = new_peers[0]
    apps = list()
    apps.append(nettesthelpers.net_app(p0))
    apps += [nettesthelpers.net_app(p, [p0]) for p in new_peers[1:]]
    return apps


def scenario_2(peer_count=5):
    peers = [
        pseudo_peer(f"P{i}") for i in range(peer_count)
    ]

    apps = []
    for i in range(len(peers)):
        neighbors = []
        if i < len(peers) - 1:
            neighbors = [peers[i + 1]]
        app = nettesthelpers.net_app(peers[i], neighbors)
        apps.append(app)
    return apps

def scenario_3(peer_count=5):
    gateway_peer = pseudo_peer("Gateway")
    peers = [
        pseudo_peer(f"P{i}") for i in range(1, peer_count)
    ]
    apps = []
    for peer in peers:
        neighbors = [gateway_peer]
        app = nettesthelpers.net_app(peer, neighbors)
        apps.append(app)
    apps.append(nettesthelpers.net_app(gateway_peer))
    return apps

def test_contacts_checklist_at_boot():
    apps = scenario_0()
    peer0 = apps[0]

    receiver = RecordMsgReceiver()
    receiver.subscribe(peer0.cs.contact)

    Simulation([peer0]).next_round(10)

    def matcher(msg: Message) -> bool:
        mt = transcriber.parse_message_type(msg)
        return mt == MsgType.contacts_checklist

    contact_checklist_msg = receiver.next_matching_msg(matcher)
    assert contact_checklist_msg is not None
    contact_checklist = transcriber.parse_contacts_qualifier(contact_checklist_msg)
    contact_checklist = set(map(lambda c: c.identifier, contact_checklist))
    assert all([lambda p: p.cs.contact.identifier in contact_checklist for p in apps])


def test_contacts_request():
    peers = scenario_0()
    peer0 = peers[0]

    requested_peers = list(map(lambda p: p.cs.contact, peers[1:]))

    sender = MockMsgSender()
    sender.direct_message(peer0.cs.contact).fetch_contacts(requested_peers)

    receiver = RecordMsgReceiver()
    receiver.subscribe(peer0.cs.contact)
    peer0.handle_remaining_messages()
    peer0.cs.net_maintainer.perform_maintenance(peer0.cs, force_maintenance=True)
    peer0.close()

    def contacts_message_matcher(msg: Message) -> Union[bool, list[PeerContactInfo]]:
        if transcriber.parse_message_type(msg) != MsgType.contacts_content:
            return False
        contacts = transcriber.parse_contacts(msg)
        own_contact_msg = [peer0.cs.contact] == contacts
        if not own_contact_msg:
            return contacts
        else:
            return False


    contacts_msg = receiver.next_matching_msg(contacts_message_matcher)
    assert contacts_msg is not None
    parsed_contacts: list[PeerContactInfo] = contacts_msg
    assert parsed_contacts == requested_peers

@nettesthelpers.long_test
def test_clique_scenario_list():
    apps = scenario_2(peer_count=20)
    run_clique_is_formed_test(apps)


@nettesthelpers.long_test
def test_clique_scenario_gateway():
    apps = scenario_3(peer_count=100)
    run_clique_is_formed_test(apps)

# @nettesthelpers.long_test
def test_clique_scenario_1():
    apps = scenario_1()
    run_clique_is_formed_test(apps)

# @nettesthelpers.long_test
def test_clique_scenario_0():
    apps = scenario_0()
    run_clique_is_formed_test(apps)


def run_clique_is_formed_test(apps):
    clique_found, rounds = nettesthelpers.simulate_till_clique_is_formed(apps, 100000)
    if clique_found:
        logger.info("Clique of %d many peers formed in %d many rounds.", len(apps), rounds)
    assert clique_found
    logger.info("Closing apps..")
    for a in apps:
        a.close()
