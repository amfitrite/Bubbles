import socket
import threading
import logging
import selectors
import time
import os
from typing import Callable, List
from src.network.protocol import ProtocolParser

logger = logging.getLogger(__name__)

class BridgeServer:
    """
    Non-blocking multi-port TCP server for receiving real-time ticks from MT5 EA.
    Listens on ports 5555..5559 (or configured ports).
    """
    def __init__(self, callback: Callable, host: str = "127.0.0.1", ports: List[int] = None):
        self.host = host
        self.ports = ports if ports is not None else [5555, 5556, 5557, 5558, 5559]
        self.callback = callback
        self.running = False
        self.sockets = []
        self.selector = selectors.DefaultSelector()
        self.thread = None
        self.clients = {} # sock -> {'parser': ProtocolParser(), 'addr': addr}

    def start(self):
        self.running = True

        for port in self.ports:
            try:
                server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if os.name != 'nt':
                    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                server_sock.bind((self.host, port))
                server_sock.listen(5)
                server_sock.setblocking(False)

                self.selector.register(server_sock, selectors.EVENT_READ, data=None)
                self.sockets.append(server_sock)
                logger.info(f"BridgeServer listening on {self.host}:{port}")
            except Exception as e:
                logger.warning(f"Could not bind to {self.host}:{port}: {e}")

        if not self.sockets:
            logger.error("No ports could be bound. Server cannot start.")
            return False

        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="BridgeServerThread")
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        for sock in list(self.clients.keys()):
            self._disconnect_client(sock)

        for sock in self.sockets:
            try:
                self.selector.unregister(sock)
                sock.close()
            except Exception:
                pass
        self.sockets.clear()

        try:
            self.selector.close()
        except Exception:
            pass

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        logger.info("BridgeServer stopped.")

    def _run_loop(self):
        while self.running:
            try:
                events = self.selector.select(timeout=0.1)
                for key, mask in events:
                    if key.data is None:
                        self._accept_client(key.fileobj)
                    else:
                        self._read_client(key.fileobj)
            except Exception as e:
                if self.running:
                    logger.error(f"Error in BridgeServer loop: {e}")
                    time.sleep(0.01)

    def _accept_client(self, server_sock):
        try:
            client_sock, addr = server_sock.accept()
            client_sock.setblocking(False)
            client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            self.clients[client_sock] = {
                'parser': ProtocolParser(),
                'addr': addr
            }
            self.selector.register(client_sock, selectors.EVENT_READ, data=self.clients[client_sock])
            logger.info(f"Accepted connection from {addr}")
        except Exception as e:
            logger.error(f"Failed to accept connection: {e}")

    def _read_client(self, client_sock):
        try:
            data = client_sock.recv(65536)
            if not data:
                self._disconnect_client(client_sock)
                return

            text = data.decode("utf-8", errors="ignore")
            client_info = self.clients.get(client_sock)
            if not client_info:
                return

            events = client_info['parser'].feed(text)
            for msg_type, symbol, payload in events:
                if self.callback:
                    try:
                        self.callback(client_sock, symbol, msg_type, payload)
                    except Exception as cb_err:
                        logger.error(f"Error in network event callback: {cb_err}")

        except (ConnectionResetError, BrokenPipeError):
            self._disconnect_client(client_sock)
        except Exception as e:
            logger.debug(f"Socket read error: {e}")
            self._disconnect_client(client_sock)

    def _disconnect_client(self, client_sock):
        info = self.clients.pop(client_sock, None)
        if info:
            logger.info(f"Closing connection {info.get('addr')}")
        try:
            self.selector.unregister(client_sock)
        except Exception:
            pass
        try:
            client_sock.close()
        except Exception:
            pass
