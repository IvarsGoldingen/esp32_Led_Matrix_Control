import socket
from threading import Thread
import queue
from queue import Queue
import time
import logging
import threading

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)


class EspSocketCntrl(threading.Thread):
    """
    Class for connecting to ESP controller using sockets
    """
    # class statuses for sending to main
    MSG_TEST = 0
    STATUS_CONNECTED = 1
    STATUS_DISCONNECTED = 2
    STATUS_SENDING = 3
    STATUS_CONNECTING = 4
    # how often to attempt reconnection
    AUTO_RECONNECT_S = 1.0

    def __init__(self, q_main_to_s: Queue, q_s_to_main: Queue, host, port):
        super(EspSocketCntrl, self).__init__()
        # Socket for communicating with the controller
        self.socket = None
        self.host = host
        self.port = port
        # Queues to receive commands and send status to main/UI
        self.q_in = q_main_to_s
        self.q_out = q_s_to_main
        # Current status of the connection
        self.status = self.STATUS_DISCONNECTED
        # If set the Thread will stop
        self.stop_flag = False
        # For timing autorecoonects
        self.time_of_last_connection_attempt = 0.0

    def run(self):
        # Start loop
        logger.debug("ESP controller socket Thread started")
        self.loop()

    def connect(self):
        # Connect to ESP controller socket
        self.update_status(self.STATUS_CONNECTING)
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.update_status(self.STATUS_CONNECTED)
        except TimeoutError:
            logger.debug(f"Timeout connecting")
            self.time_of_last_connection_attempt = time.perf_counter()
            self.update_status(self.STATUS_DISCONNECTED)
        except ConnectionRefusedError:
            logger.debug(f"Connection refused")
            self.time_of_last_connection_attempt = time.perf_counter()
            self.update_status(self.STATUS_DISCONNECTED)

    def update_status(self, status: int):
        # Update the status variable and send it back to main as well
        self.status = status
        self.send_to_main(f"ST_{self.status}")

    def disconnect(self):
        # Disconnect from controller
        try:
            self.socket.close()
            self.update_status(self.STATUS_DISCONNECTED)
        except Exception as e:
            logger.error(f"Error disconnecting {e}")

    def send_to_main(self, msg: str):
        # Put message in queue for main
        self.q_out.put(msg)

    def listen_for_cmds(self):
        # Check if queue contains message from main
        message = ""
        try:
            message = self.q_in.get(block=True, timeout=0)
            self.process_message(message)
        except queue.Empty:
            # no message in queue
            pass

    def process_message(self, message: str):
        # React to message received from main
        if message == 'QUIT':
            self.disconnect()
            self.stop_flag = True
        elif message == 'TEST':
            self.send_to_main("test")
        elif self.STATUS_CONNECTED:
            if message == 'RESET':
                self.disconnect()
            else:
                # TODO: check for invalid messages.
                self.send_to_controller(message)
            # all other message relate to sending data to the controller so only accept those if connected
        else:
            logger.debug("Not connected, ignoring message")

    def send_to_controller(self, msg: str):
        # Send command to controller socket
        fail = False
        logger.debug(f"Sending message to controller {msg}")
        msg = msg + "\r\n"
        self.update_status(self.STATUS_SENDING)
        try:
            result = self.socket.sendall(bytes(msg, 'utf-8'))
            if result is not None:
                fail = True
            else:
                self.update_status(self.STATUS_CONNECTED)
        except Exception as e:
            fail = True
            logger.error(f"Failed to send. {e}")
        if fail:
            self.disconnect()
            logger.error("Failed to send")

    def auto_reconnect(self):
        # If not connected and not connecting try again
        if self.status != self.STATUS_CONNECTED:
            time_since_last_con_attempt = time.perf_counter() - self.time_of_last_connection_attempt
            if time_since_last_con_attempt >= self.AUTO_RECONNECT_S:
                self.connect()

    def loop(self):
        while True:
            # Listen for messages on the input queue
            self.listen_for_cmds()
            # end thread fif stop flag received
            if self.stop_flag: break
            self.auto_reconnect()
            time.sleep(0.1)
