import logging

logger = logging.getLogger(__name__)

class ProtocolParser:
    """
    High-performance parser for MT5 TCP Bridge protocol stream.
    Supports BOTH:
      1. MT5 EA native format:
         - #SYMBOL:XAUUSD
         - #META:XAUUSD,digits,point,tick_size,contract_size
         - #HIST_START:count / #HIST_END
         - timestamp_ms,bid,ask,last,volume,flags (comma-separated)
         - timestamp_ms,bid,ask,volume,flags (legacy 5-field)
      2. ASCII Pipe-delimited format (for tools & simulator):
         - TICK|symbol|ts|bid|ask|last|volume|flags
         - META|symbol|digits|point|tick_size|contract_size
         - SYMBOL|symbol
    """
    def __init__(self):
        self.buffer = ""
        self.symbol = "XAUUSD"
        self.meta = {}
        self.in_history = False

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
            line = line.strip().replace("\r", "")
            if not line:
                continue
            event = self.parse_line(line)
            if event:
                parsed_events.append(event)

        return parsed_events

    def parse_line(self, line: str):
        line = line.strip().replace("\r", "")
        if not line:
            return None

        try:
            # --- Format A: MT5 Command Lines Starting With '#' ---
            if line.startswith("#"):
                if line.startswith("#SYMBOL:"):
                    sym = line.split(":", 1)[1].strip()
                    if sym:
                        self.symbol = sym
                    return ("SYMBOL", self.symbol, {'symbol': self.symbol})

                elif line.startswith("#META:"):
                    # #META:XAUUSD,2,0.01,0.01,100.00
                    content = line.split(":", 1)[1].strip()
                    parts = content.split(",")
                    if len(parts) >= 5:
                        sym = parts[0].strip()
                        if sym:
                            self.symbol = sym
                        digits = int(parts[1])
                        point = float(parts[2])
                        tick_size = float(parts[3])
                        contract_size = float(parts[4])
                        if tick_size <= 0:
                            tick_size = point

                        self.meta = {
                            'symbol': self.symbol,
                            'digits': digits,
                            'point': point,
                            'tick_size': tick_size,
                            'contract_size': contract_size
                        }
                        return ("META", self.symbol, self.meta)
                    return None

                elif line.startswith("#HIST_START:"):
                    self.in_history = True
                    try:
                        count = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        count = 0
                    return ("HIST_START", self.symbol, {'count': count})

                elif line.startswith("#HIST_END"):
                    self.in_history = False
                    return ("HIST_END", self.symbol, {})

                return None

            # --- Format B: Pipe-Delimited Messages (TICK|..., META|..., SYMBOL|...) ---
            if "|" in line:
                parts = line.split("|")
                msg_type = parts[0]

                if msg_type == "TICK":
                    if len(parts) < 8:
                        return None
                    sym = parts[1].strip()
                    if sym:
                        self.symbol = sym
                    ts = int(parts[2])
                    bid = float(parts[3])
                    ask = float(parts[4])
                    last = float(parts[5])
                    volume = float(parts[6])
                    flags = int(parts[7])
                    side = 1 if (flags & 32) != 0 else (-1 if (flags & 64) != 0 else 0)
                    if last <= 0.0:
                        last = ask if side == 1 else bid

                    return ("TICK", self.symbol, {
                        'ts': ts,
                        'bid': bid,
                        'ask': ask,
                        'last': last,
                        'volume': volume,
                        'flags': flags,
                        'side': side
                    })

                elif msg_type == "META":
                    if len(parts) < 6:
                        return None
                    sym = parts[1].strip()
                    if sym:
                        self.symbol = sym
                    digits = int(parts[2])
                    point = float(parts[3])
                    tick_size = float(parts[4])
                    contract_size = float(parts[5])
                    if tick_size <= 0:
                        tick_size = point

                    self.meta = {
                        'symbol': self.symbol,
                        'digits': digits,
                        'point': point,
                        'tick_size': tick_size,
                        'contract_size': contract_size
                    }
                    return ("META", self.symbol, self.meta)

                elif msg_type == "SYMBOL":
                    if len(parts) >= 2:
                        sym = parts[1].strip()
                        if sym:
                            self.symbol = sym
                        return ("SYMBOL", self.symbol, {'symbol': self.symbol})

                return None

            # --- Format C: MT5 Comma-Separated Tick Lines ---
            if "," in line:
                parts = line.split(",")
                if len(parts) >= 6:
                    # 6-field: timestamp_ms,bid,ask,last,volume,flags
                    ts = int(parts[0])
                    bid = float(parts[1])
                    ask = float(parts[2])
                    last = float(parts[3])
                    volume = float(parts[4])
                    flags = int(parts[5])
                elif len(parts) == 5:
                    # 5-field: timestamp_ms,bid,ask,volume,flags
                    ts = int(parts[0])
                    bid = float(parts[1])
                    ask = float(parts[2])
                    last = 0.0
                    volume = float(parts[3])
                    flags = int(parts[4])
                else:
                    return None

                side = 1 if (flags & 32) != 0 else (-1 if (flags & 64) != 0 else 0)
                if last <= 0.0:
                    last = ask if side == 1 else bid

                return ("TICK", self.symbol, {
                    'ts': ts,
                    'bid': bid,
                    'ask': ask,
                    'last': last,
                    'volume': volume,
                    'flags': flags,
                    'side': side
                })

        except Exception as e:
            logger.debug(f"Protocol parse error on line '{line}': {e}")
            return None

        return None
