"""
Production bot entry point.
Usage:
    python scripts/run_bot.py

Set MEXC_SANDBOX=false in .env when ready for live trading.
"""
import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sniper.execution.trade_engine import TradeEngine
from sniper.utils.db import init_db
from sniper.monitoring.logger import setup_logging, get_logger
from sniper.monitoring.telegram_alerts import alert_system
from config.settings import settings

setup_logging()
logger = get_logger(__name__)


async def main():
    # Initialize DB
    await init_db()

    engine = TradeEngine()

    # Graceful shutdown handler
    loop = asyncio.get_event_loop()

    def shutdown(sig):
        logger.info("shutdown_signal_received", signal=sig.name)
        asyncio.create_task(graceful_shutdown(engine))

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown, sig)

    mode = "SANDBOX" if settings.MEXC_SANDBOX else "LIVE"
    logger.info("bot_starting", symbol=settings.SYMBOL, mode=mode)
    await alert_system(f"Bot starting in {mode} mode — {settings.SYMBOL}")

    try:
        await engine.start()
    except Exception as e:
        logger.error("engine_crashed", error=str(e))
        await alert_system(f"Bot crashed: {e}")
        raise


async def graceful_shutdown(engine: TradeEngine):
    logger.info("graceful_shutdown")
    await engine.stop()
    await alert_system("Bot stopped gracefully.")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
