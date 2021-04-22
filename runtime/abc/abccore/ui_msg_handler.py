from abcnet.handlers import MessageHandler
import zmq


class UIMessageHandler(MessageHandler):

    def __init__(self, agent):
        self.agent = agent
        self.poller = zmq.Poller()
        self.poller.register(self.agent.socket, zmq.POLLIN)

    def perform_maintenance(self, cs: "ChannelService"):
        super().perform_maintenance(cs)
        # self.local_message_handler.handle(self.local_message_handler.socket.recv_json())
        sockets = dict(self.poller.poll(1))
        if self.agent.socket in sockets and sockets[self.agent.socket] == zmq.POLLIN:
            self.agent.handle(self.agent.socket.recv_json())
