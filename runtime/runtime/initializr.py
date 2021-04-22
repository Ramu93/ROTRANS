import logging
import os
import traceback
from typing import Dict, List, Tuple, Optional, Union

from abcckpt import ckpt_constants
from abcckpt.checkpointservice import CkptService
from abcckpt.ckpt_creation_state import CkptCreationState
from abcckpt.ckpt_syncronizer import CkptSync
from abcckpt.ckpttesthelpers import inject_ckpt_items_into_oracle
from abcckpt.content_handler import ContentHandler
from abcckpt.hash_handler import HashHandler
from abcckpt.pre_checkpoint import PreCheckpoint
from abcckpt.prio_cr_handler import PriorityCrHandler
from abcckpt.prio_handler import PriorityHandler
from abcckpt.proposal_cr_handler import ProposalCrHandler
from abcckpt.stab_abc_consens import StabVotingHandler
from abcckpt.vote_cr_handler import VoteCrHandler
from abccore.agent import Agent, Genesis, Checkpoint
from abccore.agent_service import AgentService
from abcnet import auth, netstats, handlers, networking
from abcnet.auth import MessageAuthenticatorImpl, MessageIdentification
from abcnet.gateway import GatewayRebroadcast
from abcnet.networking import ContactBook
from abcnet.services import BaseApp, ChannelService
from abcnet.structures import PeerContactInfo, SocketBinding, NetPrivKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from runtime import txnstats, txnspammer

logger = logging.getLogger(__name__)

inject_ckpt_items_into_oracle()

# Set the time between checkpoint generation to 30 seconds.
ckpt_constants.CKPT_CREATION_TIME_TH = 30.0
# Set the min stake required for checkpoint generation.
ckpt_constants.CKPT_PARTICIPATION_STAKE_TH = 0.01


def read_ic(path: str) -> List["PeerContactInfo"]:
    """
    Reads a list of peer contact from the given file path and returns it.
    """
    try:
        import json
        with open(path, 'r') as fp:
            ic_arr = json.load(fp)
        from abcnet.structures import PeerContactInfo
        initial_contacts_read = [PeerContactInfo.from_dict(ic) for ic in ic_arr]
        return initial_contacts_read
    except Exception as e:
        print("Error trying to read initial contacts file: {}".format(e))
        traceback.print_exc()


def set_ui_server_port(sc_obj: Dict):
    from abccore import zmq_server
    if 'uiServerPort' not in sc_obj:
        logger.warning("No 'uiServerPort' defined in self contact. Using the default port for UI server.")
    else:
        try:
            port = sc_obj['uiServerPort']
            port_nr = int(port)
            if port_nr <= 0 or port_nr > 65535:
                raise ValueError("Cannot set ui port to "+ str(port_nr))
            zmq_server.PORT = port_nr
        except Exception as e:
            logger.error("Error trying to set the ui server port.", exc_info=e)
    logger.info("The UI server agent handler is hosted on port %s", zmq_server.PORT)


def load_self_contact(path: str, create_net_key: bool) -> Tuple["PeerContactInfo", "SocketBinding", "NetPrivKey"]:
    """
    Reads a single peer contact form the given file path and returns it.
    """
    try:
        import json
        with open(path, 'r') as fp:
            sc_obj: Dict = json.load(fp)
            from abcnet.structures import PeerContactInfo, SocketBinding, NetPrivKey
            contact_info = PeerContactInfo.from_dict(sc_obj)
            socket_binding = SocketBinding.from_dict(sc_obj)
            net_priv_key = NetPrivKey.from_dict(sc_obj)
            if net_priv_key is None and contact_info.public_key is not None:
                raise ValueError("Cannot find the private key for the public key used in contact info: %s",
                                 contact_info)
            if net_priv_key is None and create_net_key:
                logger.warning("Couldn't get network private key from file: %s", path)
                logger.info("Generating a new private keyset for network usage.")
                net_priv_key = NetPrivKey.from_seed()
            if net_priv_key is not None:
                logger.info("Public network key is:  %s", net_priv_key.public_key_bytes.hex())
                if contact_info.public_key is None:
                    contact_info.public_key = net_priv_key.public_key_bytes
            else:
                logger.warning("Selecting network key. Messages are not authenticated on the network level.")
            set_ui_server_port(sc_obj)
            return contact_info, socket_binding, net_priv_key
    except Exception as e:
        # print("Error trying to read self contact file: {}".format(e))
        # traceback.print_exc()
        raise


def place_genesis():
    if os.path.exists("./genesis.db"):
        logger.info("Genesis file already exists.")
        return
    logger.warning("No genesis database found. Dumping it from code.")
    from runtime.backups import recall_dump
    recall_dump("./genesis.db")


def initialize_net_app(self_contact: PeerContactInfo, initial_contacts: List[PeerContactInfo],
                        bind_info: SocketBinding, net_priv_key: NetPrivKey, ping_interval: float) \
                        -> Tuple[BaseApp, ContactBook]:

    initial_contacts = [peer for peer in initial_contacts if peer.identifier != self_contact.identifier]
    logger.warning("We have %s many initial contacts.", len(initial_contacts))

    cb = networking.ContactBook(self_contact=self_contact, initial_contacts=initial_contacts)
    if net_priv_key is not None:
        ma = MessageAuthenticatorImpl(self_contact, net_priv_key)
    else:
        ma = MessageIdentification(self_contact)
    cs = ChannelService.initialize_service(cb=cb, bind_info=bind_info, ma=ma)
    ba = BaseApp(cs)

    initialize_basic_network_app(ba, cb)

    from abcnet.pingpong import PingApp
    ba.register_app_layer("ping", PingApp(cb.self_contact, ping_interval))
    return ba, cb


def enable_abc_logic(ba: BaseApp, enabled_ui: bool, keys:List[Ed25519PrivateKey] = None,
                     bot_mode: bool = False) -> Tuple[Agent, CkptService]:
    """
    Initializes a new abc BaseApp with the given configuration.
    """
    agent = initialize_agent(ba, keys, bot_mode)
    ckpt_service = initialize_ckpt(ba, agent)
    agent.checkpoint_service = ckpt_service

    if enabled_ui:
        from abccore.ui_msg_handler import UIMessageHandler
        ui = UIMessageHandler(agent)
        ba.register_app_layer("ui", ui)
    return agent, ckpt_service


def initialize_basic_network_app(ba: BaseApp, cb: ContactBook):
    ba.register_app_layer("magicnr", handlers.MagicNumberCheck())
    ba.register_app_layer("authcheck", auth.AuthenticationHandler(cb))
    ba.register_app_layer("messagetype", handlers.MessageTypeCheck())
    ba.register_app_layer("network", ba.cs.net_maintainer)
    ba.register_app_layer("conntection_watcher", networking.PeerConnectionWatchdog(cb))
    ba.register_app_layer("itemextractor", handlers.ItemExtraction())


def initialize_agent(ba: BaseApp, keys: Optional[List[Ed25519PrivateKey]], bot_mode: bool) -> Agent:
    place_genesis()
    try:
        ag = Agent(keys, bot_mode=bot_mode)
    except TypeError as e:
        logger.error("Error trying to create an agent with multiple keys. "
                     "Trying to create one with a single key only.",
                     exc_info=e)
        # Use the first key only
        ag = Agent(keys[0], bot_mode=bot_mode)

    ba.register_app_layer("agent", ag)
    return ag

def initialize_ckpt(ba: BaseApp, agent: Agent) -> CkptService:
    # ckpt_protocol_app(ba: BaseApp, ckpt_service: CheckpointService, agent: AgentService, pc: PreCheckpoint):
    ckpt: Union[Genesis, Checkpoint] = agent.a_data.tree.latest_checkpoint
    agent_service = AgentService(agent)
    ckpt_service = CkptService()
    ckpt_service.set_checkpoint(agent.a_data.tree)
    state: CkptCreationState = CkptCreationState(ckpt.get_identifier())
    pc: PreCheckpoint = PreCheckpoint(state)
    ckpt_service.set_pc(pc)

    ph = PriorityHandler(pre_ckpt=pc, ckpt_service=ckpt_service)
    hh = HashHandler(pre_ckpt=pc)
    ch = ContentHandler(pc, agent_service, ckpt_service)

    csync = CkptSync(pc, agent_service)

    ba.register_app_layer("checkpoint_sync_handler", csync)
    ba.register_app_layer("prio_handler", ph)
    ba.register_app_layer("content_handler", ch)
    ba.register_app_layer("hash_handler", hh)

    svh = StabVotingHandler(pc, ckpt_service)
    ba.register_app_layer("stab_vote_handler", svh)

    priority_creator = PriorityCrHandler(pc, ckpt_service, agent_service)
    ba.register_app_layer("priority_creator", priority_creator)
    vote_creator = VoteCrHandler(pc, agent_service)
    ba.register_app_layer("vote_creator", vote_creator)
    proposal_creator = ProposalCrHandler(pc, agent_service, ckpt_service)
    ba.register_app_layer("proposal_creator", proposal_creator)

    ph.set_handlers(vote_creator)
    hh.set_handlers(vote_creator)
    ch.set_handlers(vote_creator, csync)
    svh.set_handlers(ph, hh, ch, vote_creator)

    priority_creator.set_handlers(ph)
    vote_creator.set_handlers(svh)
    proposal_creator.set_handler(hh, ch)
    return ckpt_service

def enable_gateway(app: BaseApp, cb: ContactBook):
    gr = GatewayRebroadcast(cb)
    app.register_app_layer("Gateway_rebroadcast", gr)


def configure_runtime_logging(config_dir: Optional[str] = None):
    log_file = f"{config_dir}/log_setting.yaml"
    if config_dir is None or not os.path.exists(log_file):
        log_file = f"log_setting.yaml"
        if not os.path.exists(log_file):
            logger.warning(f"Logger was not configured because no logger was found: {log_file}")
            return

    from abcnet import settings
    settings.configure_logging(log_file)
    logger.info("Configured logger based on %s.", log_file)


def load_priv_key(config_dir: Optional[str] = None) -> List[Ed25519PrivateKey]:
    key_file = f"{config_dir}/privkey.json"
    if config_dir is None or not os.path.exists(key_file):
        # raise ValueError("No private key file supplied.")
        logger.warning("No private key file was supplied. Using a random private key instead.")
        key = Ed25519PrivateKey.generate()
        from abccore.agent_crypto import parse_to_bytes, pub_key_to_bytes
        logger.info("The generated private key is:\n\t%s\nThe generated public key is:\n\t%s",
                    parse_to_bytes(key).hex(),
                    pub_key_to_bytes(key.public_key()).hex())
        return [key]
    else:
        import json
        try:
            with open(key_file, 'r') as kfp:
                keyhex = json.load(kfp)
                if isinstance(keyhex, str):
                    keyhex = [keyhex]
                if not isinstance(keyhex, list):
                    raise ValueError("Expected a list of keys. instead got: " + str(keyhex))
                from abccore.agent_crypto import pub_key_to_bytes, parse_from_bytes
                keys = list()
                for k_str in keyhex:
                    key = parse_from_bytes(bytes.fromhex(k_str))
                    pub_key = pub_key_to_bytes(key.public_key()).hex()
                    logger.info("Loaded private key with public key value: %s", pub_key)
                    keys.append(key)
                return keys
        except:
            logger.warning("Couldn't load privte key: %s", exc_info=True)
            return load_priv_key(None)


def main():
    import argparse
    import os

    def is_valid_file(parser, arg):
        if not os.path.exists(arg):
            parser.error("The file %s does not exist!" % arg)
        else:
            return arg  # return an open file handle

    parser = argparse.ArgumentParser(description='Initialize and start an abc application.')
    # parser.add_argument('-lc', '--log-config', help='Logging configuration',
    #                     metavar="FILE",
    #                     dest="log", required=False,
    #                     type=lambda x: is_valid_file(parser, x))
    parser.add_argument("-cd", "--config-dir", help="Configuration directory.", dest='config',
                        required=False, metavar="FILE",
                        type=lambda x: is_valid_file(parser, x))
    parser.add_argument("-ui", "--enable-ui", help="Enables the ui app layer", dest='ui', action="store_true")
    parser.add_argument("-ep", "--enable_ping", help="Broadcasts ping in the given time interval.",
                        dest="ping_interval", type=int)
    parser.add_argument('-ns', '--net-settings', help='Network settings',
                        metavar="FILE",
                        dest="settings", required=False,
                        type=lambda x: is_valid_file(parser, x))
    parser.add_argument('-g', '--gateway', dest='is_gateway', help='Gateway mode', default=False, action="store_true")
    parser.add_argument('-s', '--stats', dest='stats', help='Enable stats serialization.', default=False,
                        action="store_true")
    parser.add_argument('-enk', '--enable-net-keys', help='Enables net key generation. '
                                                          'If no network private key is given it creates a new keyset.',
                        dest='enk', action="store_true", default=False)
    parser.add_argument('-eb', '--enable-bot-mode', help="Enables bot mode.",
                        dest='bot', action='store_true', default=False)
    parser.add_argument('-esh', '--enable-save-handler', help="Enables save handler of the agent.",
                        dest="save_handler", action="store_true", default=False)

    parser.add_argument('-ms', '--measure-stats', help="Enables save handler of the agent.",
                        dest="measure_stats", action="store_true", default=False)

    args = parser.parse_args()

    config_dir = "agentconfs/conf"
    if args.config:
        config_dir = args.config

    sc_file = f"{config_dir}/self_contact.json"
    ic_file = f"{config_dir}/initial_contacts.json"

    configure_runtime_logging(config_dir)

    keys = load_priv_key(config_dir)

    # TODO read network setting

    logger.info("Reading self contact from %s.", sc_file)

    self_contact, binding_info, net_priv_key = load_self_contact(sc_file, args.enk)

    logger.info("Self contact is: %s.", repr(self_contact))
    logger.info("Socket  Binding is: %s.", repr(binding_info))
    logger.info("Network private key is present.")

    logger.info("Reading initial contacts from %s.", ic_file)
    initial_contacts = read_ic(ic_file)
    logger.info("Initial contacts are %d many. Initial contacts: \n\t- %s", len(initial_contacts),
                "\n\t- ".join([repr(c) for c in initial_contacts]))

    ping_interval = 20
    if args.ping_interval:
        ping_interval = args.ping_interval

    app, cb = initialize_net_app(self_contact=self_contact, initial_contacts=initial_contacts, bind_info=binding_info,
                         net_priv_key=net_priv_key, ping_interval=ping_interval)

    from abcnet.simenv import Simulation
    sim = Simulation([app], 0.1)
    sim.next_round(20)

    if not args.is_gateway:
        agent, ckpt_service = enable_abc_logic(app, enabled_ui=True, keys=keys, bot_mode=args.bot)
        if not args.save_handler:
            # Deactivate save handler by patching the methods with an empty method:
            logger.info("Deactivating the save handler of the agent.")

            def save_handler_monkey_patch(*ignored_args):
                logger.debug("Save handler call by agent ignored because save handler is deactivated.")

            agent.save_data = save_handler_monkey_patch
            agent.load_data = save_handler_monkey_patch
            from abccore import save_handler
            save_handler.update_unconfirmed = save_handler_monkey_patch
            save_handler.add_txn = save_handler_monkey_patch
            save_handler.add_ack = save_handler_monkey_patch
            save_handler.delete_old_data = save_handler_monkey_patch
            save_handler.update_wallet = save_handler_monkey_patch
            agent.a_data.save_data = save_handler_monkey_patch
            agent.a_data.load_data = save_handler_monkey_patch

        if args.measure_stats:
            txn_logger = txnstats.enable_statistics(app, ckpt_service)
            txnspammer.activate_spammer(app, txn_logger, AgentService(agent), 120)

    else:
        # enable_gateway(app, cb)
        pass

    if args.stats:
        netstats.enable_statistics(app)


    try:
        while True:
            sim.next_round()
    finally:
        sim.close()


if __name__ == "__main__":
    main()
