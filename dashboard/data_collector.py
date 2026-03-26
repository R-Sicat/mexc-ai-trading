"""
Assembles the full dashboard payload from DB + live price + bot state.
"""
import asyncio
import time
from pathlib import Path

import aiosqlite
import ccxt.async_support as ccxt

from dashboard.state import bot_state
from config.settings import settings

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "trades.db"


async def _fetch_live_price() -> float:
    try:
        exchange = ccxt.mexc({"options": {"defaultType": "swap"}, "enableRateLimit": False})
        ticker = await asyncio.wait_for(exchange.fetch_ticker(settings.SYMBOL), timeout=3)
        await exchange.close()
        return float(ticker["last"])
    except Exception:
        return 0.0


async def _fetch_chart_data(db: aiosqlite.Connection) -> dict:
    async with db.execute(
        """SELECT timestamp, candle_close, confidence
           FROM signals ORDER BY timestamp DESC LIMIT 60"""
    ) as cur:
        rows = await cur.fetchall()
    rows = list(reversed(rows))
    labels = [r[0][:16].replace("T", " ") for r in rows]
    prices = [r[1] or 0 for r in rows]
    confidence = [round(r[2] or 0, 3) for r in rows]
    return {"labels": labels, "prices": prices, "confidence": confidence}


async def _fetch_recent_trades(db: aiosqlite.Connection) -> list:
    async with db.execute(
        """SELECT id, entry_time, exit_time, direction, entry_price,
                  exit_price, net_pnl, exit_reason
           FROM trades ORDER BY entry_time DESC LIMIT 20"""
    ) as cur:
        rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "entry_time": (r[1] or "")[:16].replace("T", " "),
            "exit_time": (r[2] or "")[:16].replace("T", " "),
            "direction": r[3],
            "entry_price": r[4],
            "exit_price": r[5],
            "net_pnl": round(r[6] or 0, 2),
            "exit_reason": (r[7] or "OPEN").upper(),
        }
        for r in rows
    ]


async def _fetch_gate_log(db: aiosqlite.Connection) -> list:
    async with db.execute(
        """SELECT timestamp, direction, confidence, gate_passed,
                  gate_fail_reason, tech_score, ml_score, pattern_score, sentiment_score
           FROM signals ORDER BY timestamp DESC LIMIT 12"""
    ) as cur:
        rows = await cur.fetchall()
    return [
        {
            "ts": (r[0] or "")[:19].replace("T", " "),
            "direction": r[1],
            "confidence": round(r[2] or 0, 3),
            "passed": bool(r[3]),
            "reason": r[4] or "",
            "tech": round(r[5] or 0, 2),
            "ml": round(r[6] or 0, 2),
            "pattern": round(r[7] or 0, 2),
            "sentiment": round(r[8] or 0, 2),
        }
        for r in rows
    ]


async def _fetch_metrics(db: aiosqlite.Connection) -> dict:
    # Try metrics table first
    async with db.execute(
        "SELECT win_rate, total_trades, sharpe_30d, max_drawdown, daily_pnl FROM metrics ORDER BY timestamp DESC LIMIT 1"
    ) as cur:
        row = await cur.fetchone()
    if row and row[1]:
        return {
            "win_rate": round((row[0] or 0) * 100, 1),
            "total_trades": row[1] or 0,
            "sharpe": round(row[2] or 0, 2),
            "max_drawdown": round(row[3] or 0, 2),
            "daily_pnl": round(row[4] or 0, 2),
        }

    # Fallback: compute from trades table
    async with db.execute("SELECT net_pnl FROM trades WHERE net_pnl IS NOT NULL") as cur:
        pnls = [r[0] for r in await cur.fetchall()]

    async with db.execute("SELECT COUNT(*) FROM trades") as cur:
        total = (await cur.fetchone())[0] or 0

    from datetime import date
    today = date.today().isoformat()
    async with db.execute(
        "SELECT COALESCE(SUM(net_pnl),0) FROM trades WHERE DATE(exit_time)=?", (today,)
    ) as cur:
        daily = (await cur.fetchone())[0] or 0

    wins = sum(1 for p in pnls if p > 0)
    win_rate = round(wins / len(pnls) * 100, 1) if pnls else 0

    return {
        "win_rate": win_rate,
        "total_trades": total,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "daily_pnl": round(daily, 2),
    }


async def _fetch_latest_signal(db: aiosqlite.Connection) -> dict:
    async with db.execute(
        """SELECT direction, confidence, tech_score, ml_score, pattern_score, sentiment_score
           FROM signals ORDER BY timestamp DESC LIMIT 1"""
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return {}
    return {
        "direction": row[0],
        "confidence": row[1],
        "tech_score": row[2],
        "ml_score": row[3],
        "pattern_score": row[4],
        "sentiment_score": row[5],
    }


async def collect_dashboard_payload() -> dict:
    if not DB_PATH.exists():
        return _empty_payload()

    try:
        live_price_task = asyncio.create_task(_fetch_live_price())

        async with aiosqlite.connect(DB_PATH) as db:
            chart, trades, gate_log, metrics, latest_signal = await asyncio.gather(
                _fetch_chart_data(db),
                _fetch_recent_trades(db),
                _fetch_gate_log(db),
                _fetch_metrics(db),
                _fetch_latest_signal(db),
            )

        live_price = await live_price_task

        # Gauges from latest signal in DB (works across separate bot/dashboard processes)
        sig = latest_signal
        gauges = {
            "tech": round(sig.get("tech_score") or 0, 2),
            "ml": round(sig.get("ml_score") or 0, 2),
            "pattern": round(sig.get("pattern_score") or 0, 2),
            "sentiment": round(sig.get("sentiment_score") or 0, 2),
        }

        # Position with unrealized P&L
        pos = None
        if bot_state.open_position:
            p = bot_state.open_position
            entry = p.get("entry_price", 0)
            contracts = p.get("contracts", 0)
            direction = p.get("direction", "LONG")
            if live_price and entry:
                pnl = (live_price - entry) * contracts * (1 if direction == "LONG" else -1)
            else:
                pnl = 0
            pos = {
                "direction": direction,
                "entry": entry,
                "sl": p.get("sl_price", 0),
                "tp": p.get("tp_price", 0),
                "contracts": contracts,
                "unrealized_pnl": round(pnl, 2),
            }

        # Bot is "running" if a signal was recorded in the last 20 minutes
        from datetime import datetime, timezone, timedelta
        last_seen = sig.get("confidence") is not None  # any signal in DB = bot ran at least once
        last_signal_ts = (gate_log[0]["ts"] if gate_log else None)
        bot_active = False
        if last_signal_ts:
            try:
                dt = datetime.fromisoformat(last_signal_ts.replace(" ", "T"))
                bot_active = (datetime.now() - dt) < timedelta(minutes=20)
            except Exception:
                pass

        return {
            "ts": int(time.time()),
            "header": {
                "symbol": settings.SYMBOL,
                "mode": "PAPER" if settings.MEXC_SANDBOX else "LIVE",
                "balance": round(bot_state.balance, 2),
                "status": "running" if bot_active else "stopped",
                "live_price": live_price,
            },
            "chart": chart,
            "gauges": gauges,
            "position": pos,
            "metrics": metrics,
            "trades": trades,
            "gate_log": gate_log,
            "last_direction": sig.get("direction") or "—",
            "last_confidence": round(sig.get("confidence") or 0, 3),
        }

    except Exception as e:
        return _empty_payload(error=str(e))


def _empty_payload(error: str = "") -> dict:
    return {
        "ts": int(time.time()),
        "header": {"symbol": settings.SYMBOL, "mode": "PAPER", "balance": 0, "status": "stopped", "live_price": 0},
        "chart": {"labels": [], "prices": [], "confidence": []},
        "gauges": {"tech": 0, "ml": 0, "pattern": 0, "sentiment": 0},
        "position": None,
        "metrics": {"win_rate": 0, "total_trades": 0, "sharpe": 0, "max_drawdown": 0, "daily_pnl": 0},
        "trades": [],
        "gate_log": [],
        "last_direction": "—",
        "last_confidence": 0,
        "error": error,
    }
