import sys
import os
import time
import socket
import unittest
import numpy as np

from src.algo.tick_store import TickStore
from src.algo.symbol_manager import SymbolManager
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

    def test_multi_symbol_bridge_streaming(self):
        manager = SymbolManager(default_symbol="XAUUSD")

        def on_event(sock, symbol, msg_type, data):
            sym = symbol.strip().upper() if symbol else manager.active_symbol
            state = manager.get_or_create(sym)
            if msg_type == 'TICK':
                state.add_tick(
                    ts=data['ts'],
                    bid=data['bid'],
                    ask=data['ask'],
                    last=data['last'],
                    volume=data['volume'],
                    flags=data['flags'],
                    side=data.get('side', 0)
                )
            elif msg_type == 'META':
                state.configure_meta(
                    tick_size=float(data.get('tick_size', 0.01)),
                    digits=int(data.get('digits', 2)),
                    point=float(data.get('point', 0.001)),
                    contract_size=float(data.get('contract_size', 100.0))
                )

        server = BridgeServer(callback=on_event, ports=[5591])
        server.start()
        time.sleep(0.1)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", 5591))

            # Send METAs for both symbols
            s.sendall(b"META|XAUUSD|2|0.01|0.01|100\n")
            s.sendall(b"META|EURUSD|5|0.00001|0.00001|100000\n")

            now = int(time.time() * 1000)
            # Send interleaved ticks
            for i in range(30):
                gold_line = f"TICK|XAUUSD|{now + i * 10}|2740.00|2740.10|2740.05|1.00|32\n"
                eur_line = f"TICK|EURUSD|{now + i * 10}|1.08500|1.08510|1.08505|2.50|64\n"
                s.sendall(gold_line.encode("ascii"))
                s.sendall(eur_line.encode("ascii"))

            time.sleep(0.3)
            s.close()
            time.sleep(0.2)

            gold_state = manager.get("XAUUSD")
            eur_state = manager.get("EURUSD")

            self.assertIsNotNone(gold_state)
            self.assertIsNotNone(eur_state)
            self.assertEqual(gold_state.tick_store.count, 30)
            self.assertEqual(eur_state.tick_store.count, 30)
            self.assertAlmostEqual(gold_state.last_known_price, 2740.05)
            self.assertAlmostEqual(eur_state.last_known_price, 1.08505)
            self.assertEqual(gold_state.digits, 2)
            self.assertEqual(eur_state.digits, 5)

        finally:
            server.stop()

if __name__ == "__main__":
    unittest.main()
