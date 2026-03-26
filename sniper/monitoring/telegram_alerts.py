"""
Telegram push notifications for trade events.
"""
import aiohttp
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_message(text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.debug("telegram_not_configured")
        return
    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning("telegram_send_failed", status=resp.status)
    except Exception as e:
        logger.warning("telegram_error", error=str(e))


async def alert_trade_open(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    contracts: float,
    confidence: float,
    risk_usd: float,
) -> None:
    emoji = "🟢" if direction == "LONG" else "🔴"
    rr = round(abs(tp - entry) / abs(sl - entry), 1)
    msg = (
        f"{emoji} *TRADE OPEN* — XAUUSDT {direction}\n"
        f"Entry: `${entry:.2f}`\n"
        f"SL: `${sl:.2f}` | TP: `${tp:.2f}` (RR 1:{rr})\n"
        f"Size: `{contracts}` contracts\n"
        f"Risk: `${risk_usd:.2f}` | Confidence: `{confidence:.1%}`"
    )
    await send_message(msg)


async def alert_trade_close(
    direction: str,
    exit_reason: str,
    entry: float,
    exit_price: float,
    net_pnl: float,
    win_rate: float,
    daily_pnl: float,
) -> None:
    emoji = "✅" if net_pnl > 0 else "❌"
    pct = (exit_price - entry) / entry * 100 * (1 if direction == "LONG" else -1)
    msg = (
        f"{emoji} *TRADE CLOSED* — {exit_reason}\n"
        f"Exit: `${exit_price:.2f}` ({pct:+.2f}%)\n"
        f"P&L: `${net_pnl:+.2f}`\n"
        f"Win rate: `{win_rate:.1%}` | Daily P&L: `${daily_pnl:+.2f}`"
    )
    await send_message(msg)


async def alert_gate_near_miss(confidence: float, reason: str) -> None:
    msg = (
        f"⚠️ *NEAR MISS* — Gate blocked at `{confidence:.1%}` confidence\n"
        f"Reason: `{reason}`"
    )
    await send_message(msg)


async def alert_system(message: str) -> None:
    msg = f"🔔 *SYSTEM ALERT*\n{message}"
    await send_message(msg)
