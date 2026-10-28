import socket
import threading
import logging
import selectors
import time
from src.network.protocol import ProtocolParser
from src.config import config

logger = logging.getLogger(__name__)

class BridgeServer:
    def __init__(self, callback):
        self.ports = config.get("network", "ports", [5558])
        self.host = config.get("network", "host", "127.0.0.1")
        self.callback = callback # Function to call when a tick/event is parsed
        self.running = False
        self.sockets = []
        self.selector = selectors.DefaultSelector()
        self.thread = None
        self.clients = {} # sock -> { 'buffer': '', 'parser': ProtocolParser(), 'addr': addr }

    def start(self):
        self.running = True

        # Bind to ports
        for port in self.ports:
            try:
                server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                # Setup reuse addr so we can restart quickly
                if os.name != 'nt':
                    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                else:
                    # Windows SO_EXCLUSIVEADDRUSE is slightly different but SO_REUSEADDR usually works for standard python
                    pass

                # TCP_NODELAY
                server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                server_sock.bind((self.host, port))
                server_sock.listen(5)
                server_sock.setblocking(False)

                self.selector.register(server_sock, selectors.EVENT_READ, data=None)
                self.sockets.append(server_sock)
                logger.info(f"BridgeServer listening on {self.host}:{port}")

            except Exception as e:
                logger.error(f"Failed to bind to {self.host}:{port}: {e}")

        if not self.sockets:
            logger.error("No ports could be bound. Server cannot start.")
            return False

        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="BridgeServerThread")
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

        for sock in list(self.clients.keys()):
            self._close_connection(sock)

        for sock in self.sockets:
            try:
                self.selector.unregister(sock)
                sock.close()
            except:
                pass

        self.selector.close()
        logger.info("BridgeServer stopped.")

    def _run_loop(self):
        while self.running:
            try:
                events = self.selector.select(timeout=1.0)
                for key, mask in events:
                    if key.data is None:
                        self._accept_wrapper(key.fileobj)
                    else:
                        self._service_connection(key, mask)
            except Exception as e:
                if self.running:
                    logger.error(f"Error in selector loop: {e}")

    def _accept_wrapper(self, sock):
        try:
            conn, addr = sock.accept()
            logger.info(f"Accepted connection from {addr}")
            conn.setblocking(False)
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Register client
            self.clients[conn] = {
                'buffer': '',
                'parser': ProtocolParser(),
                'addr': addr
            }
            self.selector.register(conn, selectors.EVENT_READ, data="client")

        except Exception as e:
            logger.error(f"Error accepting connection: {e}")

    def _service_connection(self, key, mask):
        sock = key.fileobj
        if mask & selectors.EVENT_READ:
            try:
                recv_data = sock.recv(8192)
                if recv_data:
                    self._handle_data(sock, recv_data)
                else:
                    logger.info(f"Connection closed by client {self.clients[sock]['addr']}")
                    self._close_connection(sock)
            except Exception as e:
                logger.error(f"Error reading from client {self.clients[sock]['addr']}: {e}")
                self._close_connection(sock)

    def _handle_data(self, sock, recv_data):
        client_state = self.clients[sock]
        try:
            text = recv_data.decode('utf-8')
        except UnicodeDecodeError:
            # Handle partial decodes or invalid chars by ignoring errors for now
            text = recv_data.decode('utf-8', errors='ignore')

        client_state['buffer'] += text

        # Split by newline
        while '\n' in client_state['buffer']:
            line, client_state['buffer'] = client_state['buffer'].split('\n', 1)
            line = line.replace('\r', '') # handle CRLF

            msg_type, data = client_state['parser'].parse_line(line)

            if msg_type and msg_type != 'UNKNOWN':
                # Call the callback with the parsed data
                # We include the parser symbol to know which symbol this belongs to
                symbol = client_state['parser'].symbol
                try:
                    self.callback(sock, symbol, msg_type, data)
                except Exception as e:
                    logger.error(f"Error in callback for {msg_type}: {e}")

    def _close_connection(self, sock):
        if sock in self.clients:
            logger.info(f"Closing connection {self.clients[sock]['addr']}")
            try:
                self.selector.unregister(sock)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

            # Notify callback about disconnection
            symbol = self.clients[sock]['parser'].symbol
            try:
                self.callback(sock, symbol, 'DISCONNECT', None)
            except Exception:
                pass

            del self.clients[sock]
