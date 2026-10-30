import unittest
from src.network.protocol import ProtocolParser

class TestProtocolParser(unittest.TestCase):
    def setUp(self):
        self.parser = ProtocolParser()

    def test_symbol_command(self):
        msg_type, data = self.parser.parse_line("#SYMBOL:XAUUSD")
        self.assertEqual(msg_type, "SYMBOL")
        self.assertEqual(data, "XAUUSD")
        self.assertEqual(self.parser.symbol, "XAUUSD")

    def test_meta_command(self):
        msg_type, data = self.parser.parse_line("#META:XAUUSD,2,0.01,0.01,100.00")
        self.assertEqual(msg_type, "META")
        self.assertEqual(data['symbol'], "XAUUSD")
        self.assertEqual(data['digits'], 2)
        self.assertEqual(data['point'], 0.01)
        self.assertEqual(data['tick_size'], 0.01)
        self.assertEqual(data['contract_size'], 100.00)

    def test_tick_6_field(self):
        # timestamp_ms,bid,ask,last,volume,flags
        msg_type, data = self.parser.parse_line("1700000000123,2400.10,2400.20,2400.15,1.0,32")
        self.assertEqual(msg_type, "TICK")
        self.assertEqual(data['ts'], 1700000000123)
        self.assertEqual(data['bid'], 2400.10)
        self.assertEqual(data['ask'], 2400.20)
        self.assertEqual(data['last'], 2400.15)
        self.assertEqual(data['volume'], 1.0)
        self.assertEqual(data['flags'], 32)

    def test_tick_5_field_legacy(self):
        # timestamp_ms,bid,ask,volume,flags
        msg_type, data = self.parser.parse_line("1700000000456,2400.09,2400.19,1.0,64")
        self.assertEqual(msg_type, "TICK")
        self.assertEqual(data['ts'], 1700000000456)
        self.assertEqual(data['bid'], 2400.09)
        self.assertEqual(data['ask'], 2400.19)
        self.assertEqual(data['last'], 0.0)
        self.assertEqual(data['volume'], 1.0)
        self.assertEqual(data['flags'], 64)

if __name__ == '__main__':
    unittest.main()
