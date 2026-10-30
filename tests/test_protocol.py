import unittest
from src.network.protocol import ProtocolParser

class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.parser = ProtocolParser()

    def test_mt5_native_symbol_and_meta(self):
        events = self.parser.feed("#SYMBOL:XAUUSD\n#META:XAUUSD,2,0.01,0.01,100.00\n")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0][0], "SYMBOL")
        self.assertEqual(events[0][1], "XAUUSD")
        self.assertEqual(events[1][0], "META")
        self.assertEqual(events[1][2]['digits'], 2)
        self.assertEqual(events[1][2]['tick_size'], 0.01)

    def test_mt5_native_ticks_comma_separated(self):
        self.parser.symbol = "XAUUSD"
        stream = (
            "1700000000123,4000.10,4000.20,4000.15,2.5,32\n"
            "1700000000124,4000.10,4000.20,4000.10,1.0,64\n"
        )
        events = self.parser.feed(stream)
        self.assertEqual(len(events), 2)

        # Tick 1: Buy (flag 32)
        self.assertEqual(events[0][0], "TICK")
        self.assertEqual(events[0][1], "XAUUSD")
        self.assertEqual(events[0][2]['last'], 4000.15)
        self.assertEqual(events[0][2]['volume'], 2.5)
        self.assertEqual(events[0][2]['side'], 1)

        # Tick 2: Sell (flag 64)
        self.assertEqual(events[1][0], "TICK")
        self.assertEqual(events[1][2]['side'], -1)

    def test_pipe_delimited_format(self):
        line = "TICK|BTCUSD|1700000000500|65000.0|65000.5|65000.5|0.5|32\n"
        events = self.parser.feed(line)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "TICK")
        self.assertEqual(events[0][1], "BTCUSD")
        self.assertEqual(events[0][2]['last'], 65000.5)

    def test_chunked_stream(self):
        chunk1 = "1700000000100,4000.0,4000.1,4000.05,1.0,32\n1700000000"
        chunk2 = "105,4000.0,4000.1,4000.05,2.0,64\n"

        e1 = self.parser.feed(chunk1)
        self.assertEqual(len(e1), 1)
        self.assertEqual(e1[0][2]['volume'], 1.0)

        e2 = self.parser.feed(chunk2)
        self.assertEqual(len(e2), 1)
        self.assertEqual(e2[0][2]['ts'], 1700000000105)
        self.assertEqual(e2[0][2]['volume'], 2.0)

if __name__ == "__main__":
    unittest.main()
