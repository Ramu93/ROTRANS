
import logging
import random

from abcnet import pingpong
from abcnet.settings import configure_logging, configure_test_logging
from abcnet.nettesthelpers import ping_app, pseudo_peer
from abcnet.timer import SimpleTimer
from abcnet.simenv import Simulation, configure_mocked_network_env


configure_test_logging()
logger = logging.getLogger("abctestnet")

# configure_fast_test_network()
configure_mocked_network_env()

sim = Simulation(msg_timeout=0)
gateway = ping_app(pseudo_peer("Gateway"))
sim += gateway
for i in range(6):
    sim += ping_app(pseudo_peer(f'Peer-{i}'), initial_contacts=[gateway.cs.contact])

logger.debug("Test net begins")
sim.next_round(10)

ping_timer: SimpleTimer = SimpleTimer(10)

try:
    while True:
        sim.next_round()
        if ping_timer():
            ping_node = sim.participants[random.randint(0, len(sim.participants) - 1)]
            logger.info("Node `%s` is pinging its neighbors.", ping_node.cs.contact)
            pa: pingpong.PingApp = ping_node.app("ping")
            pa.broadcast_new_ping()
except KeyboardInterrupt:
    sim.close()




