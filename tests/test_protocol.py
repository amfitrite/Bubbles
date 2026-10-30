import unittest
from src.network.protocol import ProtocolParser

class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.parser = ProtocolParser()

    def test_parse_single_tick(self):
        line = "TICK|XAUUSD|1700000000123|2735.10|2735.20|2735.15|2.5|32\n"
        events = self.parser.feed(line)
        self.assertEqual(len(events), 1)
        m_type, sym, data = events[0]
        self.assertEqual(m_type, "TICK")
        self.assertEqual(sym, "XAUUSD")
        self.assertEqual(data['ts'], 1700000000123)
        self.assertAlmostEqual(data['bid'], 2735.10)
        self.assertAlmostEqual(data['ask'], 2735.20)
        self.assertAlmostEqual(data['last'], 2735.15)
        self.assertAlmostEqual(data['volume'], 2.5)
        self.assertEqual(data['flags'], 32)
        self.assertEqual(data['side'], 1) # Buy

    def test_parse_chunked_stream(self):
        # Chunk split across packet boundary
        chunk1 = "TICK|XAUUSD|1000|2700|2701|2700.5|1.0|64\nTI"
        chunk2 = "CK|XAUUSD|1005|2700|2701|2700.5|3.0|32\nMETA|XAUUSD|2|0.01|0.01|100\n"

        e1 = self.parser.feed(chunk1)
        self.assertEqual(len(e1), 1)
        self.assertEqual(e1[0][2]['side'], -1) # Sell (flags 64)

        e2 = self.parser.feed(chunk2)
        self.assertEqual(len(e2), 2)
        self.assertEqual(e2[0][0], "TICK")
        self.assertEqual(e2[1][0], "META")
        self.assertEqual(e2[1][2]['digits'], 2)

if __name__ == "__main__":
    unittest.main()
