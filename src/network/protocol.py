import logging

logger = logging.getLogger(__name__)

class ProtocolParser:
    """
    High-performance parser for MT5 TCP Bridge protocol stream.
    Messages are newline-delimited ASCII strings:
      - TICK|symbol|ts_ms|bid|ask|last|volume|flags
      - META|symbol|digits|point|tick_size|contract_size
      - BAR|symbol|timeframe|ts_ms|open|high|low|close|vol|buy_vol|sell_vol|vwap|ticks
    """
    def __init__(self):
        self.buffer = ""

    def feed(self, chunk: str):
        """
        Feeds incoming string chunk from TCP socket.
        Returns list of parsed (msg_type, symbol, data) tuples.
        """
        self.buffer += chunk
        lines = self.buffer.split("\n")
        # Keep trailing incomplete line in buffer
        self.buffer = lines[-1]
        completed_lines = lines[:-1]

        parsed_events = []
        for line in completed_lines:
            line = line.strip()
            if not line:
                continue
            event = self.parse_line(line)
            if event:
                parsed_events.append(event)

        return parsed_events

    def parse_line(self, line: str):
        try:
            parts = line.split("|")
            msg_type = parts[0]

            if msg_type == "TICK":
                # TICK|symbol|ts|bid|ask|last|volume|flags
                if len(parts) < 8:
                    return None
                symbol = parts[1]
                ts = int(parts[2])
                bid = float(parts[3])
                ask = float(parts[4])
                last = float(parts[5])
                volume = float(parts[6])
                flags = int(parts[7])
                # Side determination from MT5 flags: 32 = Buy, 64 = Sell
                side = 1 if (flags & 32) != 0 else (-1 if (flags & 64) != 0 else 0)

                return ("TICK", symbol, {
                    'ts': ts,
                    'bid': bid,
                    'ask': ask,
                    'last': last,
                    'volume': volume,
                    'flags': flags,
                    'side': side
                })

            elif msg_type == "META":
                # META|symbol|digits|point|tick_size|contract_size
                if len(parts) < 6:
                    return None
                symbol = parts[1]
                return ("META", symbol, {
                    'symbol': symbol,
                    'digits': int(parts[2]),
                    'point': float(parts[3]),
                    'tick_size': float(parts[4]),
                    'contract_size': float(parts[5])
                })

            elif msg_type == "SYMBOL":
                # SYMBOL|symbol
                if len(parts) < 2:
                    return None
                return ("SYMBOL", parts[1], {'symbol': parts[1]})

            elif msg_type == "BAR":
                # BAR|symbol|tf|ts|open|high|low|close|vol|buy_vol|sell_vol|vwap|ticks
                if len(parts) < 13:
                    return None
                symbol = parts[1]
                return ("BAR", symbol, {
                    'timeframe': parts[2],
                    'ts': int(parts[3]),
                    'open': float(parts[4]),
                    'high': float(parts[5]),
                    'low': float(parts[6]),
                    'close': float(parts[7]),
                    'volume': float(parts[8]),
                    'buy_vol': float(parts[9]),
                    'sell_vol': float(parts[10]),
                    'vwap': float(parts[11]),
                    'ticks': int(parts[12])
                })

        except Exception as e:
            logger.debug(f"Protocol parse error for line '{line}': {e}")
            return None

        return None
