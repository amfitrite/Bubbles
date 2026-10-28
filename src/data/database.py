import sqlite3
import threading
import queue
import logging
from pathlib import Path
from src.config import config, BASE_DIR

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        db_path_str = config.get("database", "path", "data/bubbles.db")
        self.db_path = BASE_DIR / db_path_str
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.write_queue = queue.Queue(maxsize=100000)
        self.running = False
        self.thread = None

        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -64000")

        cursor = conn.cursor()

        # ticks table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticks (
            id       INTEGER PRIMARY KEY,
            symbol   TEXT    NOT NULL,
            ts       INTEGER NOT NULL,
            bid      REAL,
            ask      REAL,
            last     REAL,
            volume   REAL,
            flags    INTEGER,
            side     INTEGER
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks(symbol, ts)")

        # bars_1m table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bars_1m (
            symbol    TEXT    NOT NULL,
            ts        INTEGER NOT NULL,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    REAL,
            buy_vol   REAL,
            sell_vol  REAL,
            vwap      REAL,
            ticks     INTEGER,
            PRIMARY KEY (symbol, ts)
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bars_symbol_ts ON bars_1m(symbol, ts)")

        # meta table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            symbol        TEXT PRIMARY KEY,
            digits        INTEGER,
            point         REAL,
            tick_size     REAL,
            contract_size REAL,
            updated_at    INTEGER
        )
        """)

        # schema version
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        )
        """)

        cursor.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO schema_version (version) VALUES (1)")

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def start_writer(self):
        self.running = True
        self.thread = threading.Thread(target=self._writer_loop, daemon=True, name="DBWriterThread")
        self.thread.start()

    def stop_writer(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def enqueue_ticks(self, symbol, ticks):
        if not self.running:
            return
        batch = ('INSERT_TICKS', symbol, ticks)
        try:
            self.write_queue.put_nowait(batch)
        except queue.Full:
            logger.warning("DB write queue full, dropping oldest batch")
            try:
                self.write_queue.get_nowait()
                self.write_queue.put_nowait(batch)
            except queue.Empty:
                pass

    def enqueue_meta(self, symbol, meta_data, ts):
        batch = ('UPSERT_META', symbol, meta_data, ts)
        try:
            self.write_queue.put_nowait(batch)
        except queue.Full:
            pass

    def enqueue_bars_1m(self, symbol, bars):
        """
        bars: list of tuples (ts, open, high, low, close, volume, buy_vol, sell_vol, vwap, ticks)
        """
        if not self.running or not bars:
            return
        batch = ('UPSERT_BARS_1M', symbol, bars)
        try:
            self.write_queue.put_nowait(batch)
        except queue.Full:
            pass

    def get_bars_1m(self, symbol, start_ts, end_ts):
        """Queries 1-minute historical bars synchronously for macro views."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ts, open, high, low, close, volume, buy_vol, sell_vol, vwap, ticks
            FROM bars_1m
            WHERE symbol = ? AND ts >= ? AND ts <= ?
            ORDER BY ts ASC
        """, (symbol, start_ts, end_ts))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_last_ts(self, symbol):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ts) FROM ticks WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else 0

    def _writer_loop(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")

        batch_size = 500
        pending_commits = 0

        while self.running or not self.write_queue.empty():
            try:
                batch = self.write_queue.get(timeout=0.1)

                cmd = batch[0]
                if cmd == 'INSERT_TICKS':
                    symbol = batch[1]
                    ticks = batch[2]
                    records = [(symbol, t[0], t[1], t[2], t[3], t[4], t[5], t[6]) for t in ticks]
                    conn.executemany(
                        "INSERT INTO ticks (symbol, ts, bid, ask, last, volume, flags, side) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        records
                    )
                    pending_commits += len(records)

                elif cmd == 'UPSERT_BARS_1M':
                    symbol = batch[1]
                    bars = batch[2]
                    records = [(symbol, b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9]) for b in bars]
                    conn.executemany("""
                    INSERT INTO bars_1m (symbol, ts, open, high, low, close, volume, buy_vol, sell_vol, vwap, ticks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, ts) DO UPDATE SET
                        high = MAX(bars_1m.high, excluded.high),
                        low = MIN(bars_1m.low, excluded.low),
                        close = excluded.close,
                        volume = bars_1m.volume + excluded.volume,
                        buy_vol = bars_1m.buy_vol + excluded.buy_vol,
                        sell_vol = bars_1m.sell_vol + excluded.sell_vol,
                        vwap = excluded.vwap,
                        ticks = bars_1m.ticks + excluded.ticks
                    """, records)
                    pending_commits += len(records)

                elif cmd == 'UPSERT_META':
                    symbol = batch[1]
                    m = batch[2]
                    ts = batch[3]
                    conn.execute("""
                    INSERT INTO meta (symbol, digits, point, tick_size, contract_size, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        digits=excluded.digits,
                        point=excluded.point,
                        tick_size=excluded.tick_size,
                        contract_size=excluded.contract_size,
                        updated_at=excluded.updated_at
                    """, (symbol, m['digits'], m['point'], m['tick_size'], m['contract_size'], ts))
                    pending_commits += 1

                if pending_commits >= batch_size or self.write_queue.empty():
                    conn.commit()
                    pending_commits = 0

                self.write_queue.task_done()

            except queue.Empty:
                if pending_commits > 0:
                    conn.commit()
                    pending_commits = 0
            except Exception as e:
                logger.error(f"Error in DB writer loop: {e}")

        if pending_commits > 0:
            conn.commit()
        conn.close()
