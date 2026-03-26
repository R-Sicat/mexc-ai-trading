import aiosqlite
import asyncio
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "trades.db"

CREATE_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence REAL NOT NULL,
    tech_score REAL,
    ml_score REAL,
    pattern_score REAL,
    sentiment_score REAL,
    gate_passed INTEGER NOT NULL DEFAULT 0,
    gate_fail_reason TEXT,
    candle_open REAL,
    candle_close REAL,
    atr REAL
)
"""

CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES signals(id),
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    contracts REAL NOT NULL,
    sl_price REAL NOT NULL,
    tp_price REAL NOT NULL,
    exit_reason TEXT,
    realized_pnl REAL,
    commission REAL,
    net_pnl REAL,
    duration_minutes INTEGER
)
"""

CREATE_METRICS = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    win_rate REAL,
    total_trades INTEGER,
    avg_rr REAL,
    sharpe_7d REAL,
    sharpe_30d REAL,
    max_drawdown REAL,
    current_streak INTEGER,
    daily_pnl REAL,
    weekly_pnl REAL,
    account_balance REAL
)
"""


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SIGNALS)
        await db.execute(CREATE_TRADES)
        await db.execute(CREATE_METRICS)
        await db.commit()


async def insert_signal(signal: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO signals
               (timestamp, symbol, timeframe, direction, confidence,
                tech_score, ml_score, pattern_score, sentiment_score,
                gate_passed, gate_fail_reason, candle_open, candle_close, atr)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal["timestamp"], signal["symbol"], signal["timeframe"],
                signal["direction"], signal["confidence"],
                signal.get("tech_score"), signal.get("ml_score"),
                signal.get("pattern_score"), signal.get("sentiment_score"),
                int(signal.get("gate_passed", False)),
                signal.get("gate_fail_reason"),
                signal.get("candle_open"), signal.get("candle_close"),
                signal.get("atr"),
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def insert_trade(trade: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO trades
               (signal_id, entry_time, direction, entry_price, contracts,
                sl_price, tp_price)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                trade["signal_id"], trade["entry_time"], trade["direction"],
                trade["entry_price"], trade["contracts"],
                trade["sl_price"], trade["tp_price"],
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def close_trade(trade_id: int, update: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE trades SET
               exit_time=?, exit_price=?, exit_reason=?,
               realized_pnl=?, commission=?, net_pnl=?, duration_minutes=?
               WHERE id=?""",
            (
                update["exit_time"], update["exit_price"], update["exit_reason"],
                update["realized_pnl"], update.get("commission", 0),
                update["net_pnl"], update.get("duration_minutes"),
                trade_id,
            ),
        )
        await db.commit()


async def get_daily_pnl(date_str: str) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(net_pnl), 0) FROM trades WHERE DATE(exit_time) = ?",
            (date_str,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0


async def get_open_trades() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM trades WHERE exit_time IS NULL"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
