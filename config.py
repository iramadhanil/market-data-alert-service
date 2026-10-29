import os
from dataclasses import dataclass, field
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@dataclass
class TelegramConfig:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

@dataclass
class ScreenerConfig:
    volume_surge_multiplier: float = 2.0
    breakout_margin_pct: float = 3.0
    flag_pole_min_pct: float = 5.0
    rsi_short_period: int = 6
    rsi_oversold: float = 30.0
    max_drop_from_high_pct: float = 5.0
    runaway_range_multiplier: float = 2.0
    ma_short: int = 3
    ma_medium: int = 5
    ma_tolerance_pct: float = 1.0
    alert_cooldown_minutes: int = 30
    batch_size: int = 20
    batch_delay: float = 1.0

@dataclass
class IndicatorConfig:
    rsi_period: int = 14
    bb_period: int = 20
    bb_std_dev: float = 2.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    stoch_k_period: int = 14
    stoch_d_period: int = 3
    confluence_weight: float = 0.05

@dataclass
class DataSourceConfig:
    itick_api_key: str = os.getenv("ITICK_API_KEY", "")
    stockbit_username: str = os.getenv("STOCKBIT_USERNAME", "")
    stockbit_password: str = os.getenv("STOCKBIT_PASSWORD", "")
    stockbit_token: str = os.getenv("STOCKBIT_TOKEN", "")
    goapi_token: str = os.getenv("GOAPI_TOKEN", "")
    sectors_api_key: str = os.getenv("SECTORS_API_KEY", "")
    use_yahoo_fallback: bool = True
    scan_interval_seconds: int = 120  # 2 min for 600+ stocks
    watchlist: List[str] = field(default_factory=list)
    # Will be populated with full ISSI at startup

@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    screener: ScreenerConfig = field(default_factory=ScreenerConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    datasource: DataSourceConfig = field(default_factory=DataSourceConfig)
    timezone: str = "Asia/Jakarta"
    log_level: str = "INFO"

config = AppConfig()
