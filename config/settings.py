from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # MEXC API
    MEXC_API_KEY: str = ""
    MEXC_SECRET: str = ""
    MEXC_SANDBOX: bool = True  # Always start in paper mode

    # Trading config
    SYMBOL: str = "XAUT/USDT:USDT"
    TIMEFRAME: str = "15m"
    CONFIRM_TIMEFRAME: str = "1h"
    LEVERAGE: int = 200

    # Risk
    RISK_PER_TRADE_PCT: float = 1.5
    MAX_DAILY_LOSS_PCT: float = 5.0
    MAX_CONCURRENT_TRADES: int = 1

    # Confidence gate
    MIN_CONFIDENCE_SCORE: float = 0.72

    # Signal weights
    WEIGHT_TECHNICAL: float = 0.35
    WEIGHT_ML: float = 0.30
    WEIGHT_PATTERNS: float = 0.15
    WEIGHT_SENTIMENT: float = 0.20

    # External APIs
    NEWS_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    @field_validator("WEIGHT_TECHNICAL", "WEIGHT_ML", "WEIGHT_PATTERNS", "WEIGHT_SENTIMENT", mode="before")
    @classmethod
    def weights_positive(cls, v: float) -> float:
        assert 0 <= float(v) <= 1, "Weights must be between 0 and 1"
        return float(v)


settings = Settings()
