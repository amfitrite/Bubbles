import logging

logger = logging.getLogger(__name__)

class ProtocolParser:
    def __init__(self):
        self.symbol = None
        self.meta = {}
        self.in_history = False

    def parse_line(self, line: str):
        """
        Parses a single line from the EA.
        Returns a tuple: (msg_type, data)
        msg_type can be: 'SYMBOL', 'META', 'HIST_START', 'HIST_END', 'TICK', 'UNKNOWN'
        """
        line = line.strip()
        if not line:
            return None, None

        if line.startswith('#'):
            return self._parse_command(line)

        # If it's not a command, it should be a tick line
        return self._parse_tick(line)

    def _parse_command(self, line: str):
        if line.startswith('#SYMBOL:'):
            self.symbol = line.split(':', 1)[1].strip()
            return 'SYMBOL', self.symbol

        elif line.startswith('#META:'):
            # #META:XAUUSD,2,0.01,0.01,100.00
            # symbol,digits,point,tick_size,contract_size
            parts = line.split(':', 1)[1].split(',')
            if len(parts) >= 5:
                symbol = parts[0].strip()
                try:
                    digits = int(parts[1])
                    point = float(parts[2])
                    tick_size = float(parts[3])
                    contract_size = float(parts[4])

                    if tick_size <= 0:
                        tick_size = point

                    self.meta = {
                        'symbol': symbol,
                        'digits': digits,
                        'point': point,
                        'tick_size': tick_size,
                        'contract_size': contract_size
                    }
                    return 'META', self.meta
                except ValueError as e:
                    logger.error(f"Error parsing META values: {e}")

            return 'UNKNOWN', line

        elif line.startswith('#HIST_START:'):
            self.in_history = True
            try:
                count = int(line.split(':', 1)[1].strip())
            except ValueError:
                count = 0
            return 'HIST_START', count

        elif line.startswith('#HIST_END'):
            self.in_history = False
            return 'HIST_END', None

        return 'UNKNOWN', line

    def _parse_tick(self, line: str):
        # Format: timestamp_ms,bid,ask,last,volume,flags
        parts = line.split(',')

        try:
            if len(parts) == 6:
                # New 6-field format
                ts = int(parts[0])
                bid = float(parts[1])
                ask = float(parts[2])
                last = float(parts[3])
                vol = float(parts[4])
                flags = int(parts[5])
            elif len(parts) == 5:
                # Legacy 5-field format: timestamp,bid,ask,volume,flags
                ts = int(parts[0])
                bid = float(parts[1])
                ask = float(parts[2])
                last = 0.0 # Unknown last
                vol = float(parts[3])
                flags = int(parts[4])
            else:
                return 'UNKNOWN', line

            tick_data = {
                'ts': ts,
                'bid': bid,
                'ask': ask,
                'last': last,
                'volume': vol,
                'flags': flags
            }
            return 'TICK', tick_data

        except ValueError as e:
            logger.error(f"Error parsing tick line '{line}': {e}")
            return 'UNKNOWN', line
