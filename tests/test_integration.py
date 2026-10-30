import sys
import os
import time
import socket
import unittest
import numpy as np

from src.algo.tick_store import TickStore
from src.network.bridge_server import BridgeServer
from src.network.protocol import ProtocolParser

class TestIntegrationNetworkAlgo(unittest.TestCase):
    def test_bridge_server_to_tickstore(self):
        store = TickStore(max_ticks=1000)
        events_received = []

        def on_event(sock, symbol, msg_type, data):
            events_received.append((symbol, msg_type, data))
            if msg_type == 'TICK':
                store.add_tick(
                    ts=data['ts'],
                    bid=data['bid'],
                    ask=data['ask'],
                    last=data['last'],
                    volume=data['volume'],
                    flags=data['flags'],
                    side=data.get('side', 0)
                )

        server = BridgeServer(callback=on_event, ports=[5590])
        server.start()
        time.sleep(0.1)

        try:
            # Connect as client
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", 5590))

            # Send META
            s.sendall(b"META|XAUUSD|2|0.01|0.01|100\n")
            # Send 50 TICKs
            now = int(time.time() * 1000)
            for i in range(50):
                line = f"TICK|XAUUSD|{now + i * 10}|4000.00|4000.10|4000.05|1.50|32\n"
                s.sendall(line.encode("ascii"))
            
            time.sleep(0.3)
            s.close()
            time.sleep(0.2)

            self.assertTrue(len(events_received) >= 50)
            self.assertEqual(store.count, 50)
            snapshot, _ = store.get_snapshot()
            self.assertEqual(len(snapshot), 50)
            self.assertEqual(snapshot[0]['last'], 4000.05)

        finally:
            server.stop()

if __name__ == "__main__":
    unittest.main()
