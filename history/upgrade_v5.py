"""
IHSG Alert Bot - UPGRADE v5 (FINAL)
=====================================
- Scan SEMUA saham IHSG (bukan cuma 40)
- 5 parameter screener baru dari artikel
- Optimized batch scanning untuk 800+ saham
- Siap deploy VPS

Jalankan: python upgrade_v5.py
"""
import os
DIR = os.path.dirname(os.path.abspath(__file__))
print("\n  Upgrading to v5 (final)...\n")

# ═══════════════════════════════════════
# config.py — full IHSG stock universe
# ═══════════════════════════════════════
with open(os.path.join(DIR, "config.py"), "w", encoding="utf-8") as f:
    f.write('''import os
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
    # Volume breakout
    volume_surge_multiplier: float = 2.0  # Min 2x, ideal 3x
    # Price breakout margin (aturan 3%)
    breakout_margin_pct: float = 3.0
    # Flag pole minimum gain
    flag_pole_min_pct: float = 5.0
    # RSI short period
    rsi_short_period: int = 6  # 3 or 6 for intraday sensitivity
    rsi_oversold: float = 30.0
    # Gap detection
    max_drop_from_high_pct: float = 5.0
    # Runaway bar range multiplier
    runaway_range_multiplier: float = 2.0
    # MA
    ma_short: int = 3
    ma_medium: int = 5
    ma_tolerance_pct: float = 1.0
    # Alert
    alert_cooldown_minutes: int = 30
    # Batch scanning
    batch_size: int = 20  # Scan 20 stocks per batch to avoid rate limits
    batch_delay: float = 1.0  # Delay between batches (seconds)

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
    scan_interval_seconds: int = 60  # 60s for full IHSG scan cycle

    # Full IHSG stock universe - loaded dynamically at runtime
    # Fallback static list of most liquid stocks
    watchlist: List[str] = field(default_factory=lambda: [])
    # Will be populated dynamically from IDX/iTick

    # Static fallback: IDX80 + LQ45 + others (~200 most liquid)
    static_watchlist: List[str] = field(default_factory=lambda: [
        # LQ45
        "ACES","ADRO","AKRA","AMRT","ANTM","ARTO","ASII","BBCA",
        "BBNI","BBRI","BBTN","BFIN","BMRI","BRPT","BRIS","BUKA",
        "CPIN","EMTK","ERAA","ESSA","EXCL","GOTO","GGRM","HMSP",
        "HRUM","ICBP","INCO","INDF","INKP","ISAT","ITMG","JPFA",
        "KLBF","MAPI","MDKA","MEDC","MIKA","MTEL","PGAS","PTBA",
        "SMGR","TBIG","TKIM","TLKM","TOWR","UNTR","UNVR",
        # IDX80 additions
        "ADMR","AGII","AALI","BBYB","BIRD","BMTR","BSDE","BTPS",
        "CTRA","DNET","DSNG","ELSA","FILM","HEAL","HRTA","INDY",
        "INTA","JSMR","LSIP","MNCN","MBMA","PGEO","PNBN","PSAB",
        "RAJA","SCMA","SIDO","SMRA","SRTG","TAPG","TBLA","TINS",
        "TPIA","TSPC","UNIQ","WIFI",
        # Other liquid mid-caps
        "AISA","BJTM","BNGA","BMHS","CARS","CLEO","DMAS","DSSA",
        "ENRG","FREN","GIAA","GJTL","HEXA","IMPC","KAEF","KIJA",
        "KPIG","LPKR","LPPF","MYOR","NRCA","PANI","PWON","RALS",
        "SCBD","SIMP","SILO","SMMA","SSIA","TMAS","WIKA","WSKT",
        # Coal/Mining
        "BYAN","DOID","GEMS","MBAP","MYOH","PTRO","SGER",
        # Banking
        "BGTG","BTPN","MEGA","NISP","BDMN",
        # Property
        "ASRI","BEST","BSML","DILD","KIJA","MKPI","MTLA",
        # Consumer
        "ARNA","CINT","CMRY","DLTA","GOOD","KEJU","LMPI",
        "MRAT","ROTI","ULTJ","WOOD",
        # Tech/Telco
        "BELI","DCII","EDGE","MTDL","NFCX",
    ])

@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    screener: ScreenerConfig = field(default_factory=ScreenerConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    datasource: DataSourceConfig = field(default_factory=DataSourceConfig)
    timezone: str = "Asia/Jakarta"
    log_level: str = "INFO"

config = AppConfig()

# Populate watchlist from static if empty
if not config.datasource.watchlist:
    config.datasource.watchlist = list(config.datasource.static_watchlist)
''')
print("  [OK] config.py (~150 saham liquid + expandable)")

# ═══════════════════════════════════════
# data_fetcher.py — batch-optimized + dynamic stock list
# ═══════════════════════════════════════
with open(os.path.join(DIR, "data_fetcher.py"), "w", encoding="utf-8") as f:
    f.write('''import logging, time, json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

from config import config
logger = logging.getLogger(__name__)

@dataclass
class StockSnapshot:
    ticker: str; timestamp: datetime
    open: float = 0.0; high: float = 0.0; low: float = 0.0
    close: float = 0.0; prev_close: float = 0.0
    volume: int = 0; avg_volume_20d: int = 0
    volume_history: List[Dict] = field(default_factory=list)
    ma3: float = 0.0; ma5: float = 0.0
    volume_surge_ratio: float = 0.0; drop_from_high_pct: float = 0.0
    @property
    def change_pct(self):
        if self.prev_close == 0: return 0.0
        return ((self.close - self.prev_close) / self.prev_close) * 100

class DataSource(ABC):
    @abstractmethod
    def fetch_snapshot(self, ticker): pass
    @abstractmethod
    def fetch_bulk(self, tickers): pass
    @abstractmethod
    def fetch_historical(self, ticker, days): pass
    @abstractmethod
    def is_available(self): pass
    def fetch_stock_list(self) -> List[str]:
        return []

class ITickDataSource(DataSource):
    BASE_URL = "https://api.itick.org/stock"
    def __init__(self):
        self.api_key = config.datasource.itick_api_key
        self.headers = {"token": self.api_key, "Accept": "application/json"}

    def is_available(self):
        if not self.api_key: return False
        try:
            resp = requests.get(f"{self.BASE_URL}/quote",
                params={"region": "ID", "code": "BBCA"},
                headers=self.headers, timeout=10)
            return resp.json().get("code") == 0
        except: return False

    def fetch_stock_list(self) -> List[str]:
        """Try to fetch full IDX stock list from iTick"""
        try:
            resp = requests.get(f"{self.BASE_URL}/symbols",
                params={"region": "ID"}, headers=self.headers, timeout=15)
            data = resp.json()
            if data.get("code") == 0:
                stocks = data.get("data", [])
                tickers = [s.get("code", s.get("symbol", "")) for s in stocks if s]
                tickers = [t for t in tickers if t and len(t) <= 5]
                if tickers:
                    logger.info(f"Loaded {len(tickers)} stocks from iTick")
                    return tickers
        except Exception as e:
            logger.debug(f"iTick stock list fetch failed: {e}")
        return []

    def fetch_snapshot(self, ticker):
        try:
            resp = requests.get(f"{self.BASE_URL}/quote",
                params={"region": "ID", "code": ticker},
                headers=self.headers, timeout=10)
            data = resp.json()
            if data.get("code") != 0: return None
            d = data.get("data", {})
            return StockSnapshot(
                ticker=ticker, timestamp=datetime.now(),
                open=float(d.get("o", 0)), high=float(d.get("h", 0)),
                low=float(d.get("l", 0)),
                close=float(d.get("ld", d.get("c", 0))),
                prev_close=float(d.get("pc", 0)),
                volume=int(d.get("v", 0)),
            )
        except Exception as e:
            logger.debug(f"iTick error {ticker}: {e}")
            return None

    def fetch_bulk(self, tickers):
        """Batch fetch with rate limiting"""
        results = {}
        batch_size = config.screener.batch_size
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            for ticker in batch:
                snap = self.fetch_snapshot(ticker)
                if snap and snap.close > 0:
                    results[ticker] = snap
                time.sleep(0.15)
            if i + batch_size < len(tickers):
                time.sleep(config.screener.batch_delay)
        return results

    def fetch_historical(self, ticker, days=30):
        try:
            resp = requests.get(f"{self.BASE_URL}/kline",
                params={"region": "ID", "code": ticker, "interval": "8", "limit": days},
                headers=self.headers, timeout=15)
            data = resp.json()
            if data.get("code") != 0: return []
            bars = data.get("data", [])
            result = []
            for bar in bars:
                ts = bar.get("t", 0)
                date_str = datetime.fromtimestamp(ts/1000).strftime("%Y-%m-%d") if ts > 1e9 else str(ts)
                result.append({
                    "date": date_str,
                    "open": float(bar.get("o", 0)), "high": float(bar.get("h", 0)),
                    "low": float(bar.get("l", 0)), "close": float(bar.get("c", 0)),
                    "volume": int(bar.get("v", 0)),
                })
            return result
        except: return []

class YahooDataSource(DataSource):
    def _jk(self, t): return f"{t}.JK" if not t.endswith(".JK") else t
    def is_available(self): return HAS_YF
    def fetch_stock_list(self): return []
    def fetch_snapshot(self, ticker):
        try:
            yt = yf.Ticker(self._jk(ticker))
            hist = yt.history(period="5d", interval="1d")
            if hist.empty: return None
            today = hist.iloc[-1]; prev = hist.iloc[-2] if len(hist) >= 2 else today
            h30 = yt.history(period="1mo", interval="1d")
            av = int(h30["Volume"].mean()) if not h30.empty else 0
            return StockSnapshot(
                ticker=ticker.replace(".JK",""), timestamp=datetime.now(),
                open=float(today.get("Open",0)), high=float(today.get("High",0)),
                low=float(today.get("Low",0)), close=float(today.get("Close",0)),
                prev_close=float(prev.get("Close",0)),
                volume=int(today.get("Volume",0)), avg_volume_20d=av)
        except: return None
    def fetch_bulk(self, tickers):
        results = {}
        for t in tickers:
            s = self.fetch_snapshot(t)
            if s: results[t] = s
            time.sleep(0.3)
        return results
    def fetch_historical(self, ticker, days=30):
        try:
            yt = yf.Ticker(self._jk(ticker))
            hist = yt.history(period=f"{days}d", interval="1d")
            return [{"date":idx.strftime("%Y-%m-%d"),"open":float(r["Open"]),
                "high":float(r["High"]),"low":float(r["Low"]),
                "close":float(r["Close"]),"volume":int(r["Volume"])}
                for idx,r in hist.iterrows()]
        except: return []

class DataFetcher:
    def __init__(self):
        self.sources = []; self.active_source = None
        self._init_sources()
        self._load_stock_universe()

    def _init_sources(self):
        if config.datasource.itick_api_key:
            itick = ITickDataSource()
            if itick.is_available():
                self.sources.append(itick)
                logger.info("iTick: ACTIVE (real-time IDX)")
            else:
                logger.warning("iTick: key invalid")
        if HAS_YF:
            self.sources.append(YahooDataSource())
            if not self.sources or not isinstance(self.sources[0], ITickDataSource):
                logger.info("Yahoo Finance: ACTIVE (delayed)")
        self.active_source = self.sources[0] if self.sources else None

    def _load_stock_universe(self):
        """Try to load full IHSG stock list dynamically"""
        for source in self.sources:
            stocks = source.fetch_stock_list()
            if stocks and len(stocks) > 50:
                config.datasource.watchlist = stocks
                logger.info(f"Loaded {len(stocks)} stocks dynamically")
                return
        # Fallback to static list
        if not config.datasource.watchlist:
            config.datasource.watchlist = list(config.datasource.static_watchlist)
        logger.info(f"Using {len(config.datasource.watchlist)} stocks (static list)")

    def fetch_snapshot(self, ticker):
        for s in self.sources:
            r = s.fetch_snapshot(ticker)
            if r: return r
        return None
    def fetch_bulk(self, tickers):
        for s in self.sources:
            r = s.fetch_bulk(tickers)
            if r: return r
        return {}
    def fetch_historical(self, ticker, days=30):
        for s in self.sources:
            r = s.fetch_historical(ticker, days)
            if r: return r
        return []
    @property
    def source_name(self):
        if self.active_source:
            n = type(self.active_source).__name__
            if "ITick" in n: return "iTick (Real-time IDX)"
            return n
        return "None"
''')
print("  [OK] data_fetcher.py (batch scanning + dynamic stock list)")

# ═══════════════════════════════════════
# screener.py — 5 PARAMETERS FROM ARTICLE
# ═══════════════════════════════════════
with open(os.path.join(DIR, "screener.py"), "w", encoding="utf-8") as f:
    f.write('''import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import config
from data_fetcher import DataFetcher, StockSnapshot
from indicators import IndicatorSuite, TechnicalIndicators

logger = logging.getLogger(__name__)

@dataclass
class SignalDetail:
    name: str; passed: bool; value: float; threshold: float
    description: str; strength: int = 0

@dataclass
class PatternDetected:
    name: str; emoji: str; description: str
    strength: int = 0; details: Dict = field(default_factory=dict)

@dataclass
class AlertSignal:
    ticker: str; timestamp: datetime; snapshot: StockSnapshot
    volume_signal: Optional[SignalDetail] = None
    price_strength_signal: Optional[SignalDetail] = None
    ma_signal: Optional[SignalDetail] = None
    patterns: List[PatternDetected] = field(default_factory=list)
    indicators: Optional[IndicatorSuite] = None
    is_strong_buy: bool = False; overall_strength: int = 0
    confidence: str = ""; reasons: List[str] = field(default_factory=list)

class ScreenerEngine:
    """
    5 Parameter Screener:
    1. Volume Breakout (lonjakan volume + breakout resistensi)
    2. Flags & Pennants (konsolidasi super cepat)
    3. RSI Short-Period (RSI 6 bouncing dari oversold)
    4. Breakaway/Runaway Gap
    5. Runaway Bars/Spikes
    """
    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.alert_history: Dict[str, datetime] = {}
        self._hist_cache: Dict[str, List] = {}
        self._cache_exp: Dict[str, datetime] = {}

    def scan_all(self, tickers):
        alerts = []
        snaps = self.fetcher.fetch_bulk(tickers)
        logger.info(f"Scanned {len(snaps)}/{len(tickers)} stocks")
        for t, snap in snaps.items():
            try:
                sig = self.analyze(snap)
                if sig and sig.is_strong_buy and not self._cooldown(t):
                    alerts.append(sig)
                    self.alert_history[t] = datetime.now()
            except Exception as e:
                logger.debug(f"Error {t}: {e}")
        alerts.sort(key=lambda a: a.overall_strength, reverse=True)
        return alerts

    def fetch_market_movers(self, tickers):
        snaps = self.fetcher.fetch_bulk(tickers)
        valid = [s for s in snaps.values() if s and s.close > 0 and s.prev_close > 0]
        gainers = sorted(valid, key=lambda s: s.change_pct, reverse=True)
        losers = sorted(valid, key=lambda s: s.change_pct)
        return gainers, losers

    def analyze(self, snap):
        if not snap or snap.close <= 0: return None
        hist = self._get_hist(snap.ticker)
        if len(hist) < 5: return None

        closes = [d["close"] for d in hist] + [snap.close]
        highs = [d.get("high", d["close"]) for d in hist] + [snap.high or snap.close]
        lows = [d.get("low", d["close"]) for d in hist] + [snap.low or snap.close]
        volumes = [d.get("volume", 0) for d in hist] + [snap.volume]
        opens = [d.get("open", d["close"]) for d in hist] + [snap.open or snap.close]

        snap.ma3 = self._ma(closes, config.screener.ma_short)
        snap.ma5 = self._ma(closes, config.screener.ma_medium)

        vol_w = volumes[-21:-1] if len(volumes) > 21 else volumes[:-1]
        avg_vol = int(sum(vol_w) / len(vol_w)) if vol_w else 1
        if avg_vol <= 0: avg_vol = 1
        snap.avg_volume_20d = avg_vol
        snap.volume_surge_ratio = snap.volume / avg_vol
        if snap.high > 0:
            snap.drop_from_high_pct = ((snap.high - snap.close) / snap.high) * 100

        # ── 5 PATTERN DETECTION ─────────────────
        patterns = []

        # 1. Volume Breakout + Aturan 3%
        p1 = self._p1_volume_breakout(snap, closes, avg_vol)
        if p1: patterns.append(p1)

        # 2. Flags & Pennants
        p2 = self._p2_flag_pennant(closes, volumes, avg_vol)
        if p2: patterns.append(p2)

        # 3. RSI Short-Period Bounce
        p3 = self._p3_rsi_bounce(closes)
        if p3: patterns.append(p3)

        # 4. Breakaway / Runaway Gap
        p4 = self._p4_gap(snap, highs, lows, avg_vol)
        if p4: patterns.append(p4)

        # 5. Runaway Bars / Spikes
        p5 = self._p5_runaway_bar(snap, highs, lows, avg_vol)
        if p5: patterns.append(p5)

        # Indicators
        inds = TechnicalIndicators.calc_all(closes, highs, lows, volumes)

        alert = AlertSignal(
            ticker=snap.ticker, timestamp=datetime.now(), snapshot=snap,
            patterns=patterns, indicators=inds,
        )

        # STRONG BUY = minimal 1 pola + volume surge
        vol_ok = snap.volume_surge_ratio >= config.screener.volume_surge_multiplier
        if len(patterns) > 0 and vol_ok:
            alert.is_strong_buy = True
            pstr = max(p.strength for p in patterns)
            vol_str = min(100, int(snap.volume_surge_ratio / 5 * 100))
            base = int(pstr * 0.5 + vol_str * 0.3 + (20 if snap.drop_from_high_pct <= 3 else 0))
            bonus = 0
            if inds: bonus = int(inds.bullish_count * config.indicators.confluence_weight * 100)
            bonus += (len(patterns) - 1) * 8
            alert.overall_strength = min(100, base + bonus)
            if alert.overall_strength >= 80: alert.confidence = "VERY HIGH"
            elif alert.overall_strength >= 65: alert.confidence = "HIGH"
            elif alert.overall_strength >= 50: alert.confidence = "MEDIUM"
            else: alert.confidence = "MODERATE"
            alert.reasons = [f"{p.name}: {p.description}" for p in patterns]
            if snap.change_pct > 0:
                alert.reasons.append(f"Naik {snap.change_pct:+.1f}%")
            if inds:
                alert.reasons.append(f"Konfluensi: {inds.bullish_count}/{inds.total_indicators} bullish")
        return alert

    # ── P1: Volume Breakout + Aturan 3% ────────
    def _p1_volume_breakout(self, snap, closes, avg_vol):
        if snap.ma5 <= 0: return None
        vol_ok = snap.volume >= avg_vol * config.screener.volume_surge_multiplier
        above = snap.close > snap.ma5
        margin = snap.close >= snap.ma5 * (1 + config.screener.breakout_margin_pct / 100)
        if vol_ok and above and margin:
            pct = ((snap.close - snap.ma5) / snap.ma5) * 100
            return PatternDetected(
                name="Volume Breakout", emoji="\\U0001F4A5",
                description=f"Close +{pct:.1f}% di atas MA5, Vol {snap.volume_surge_ratio:.1f}x",
                strength=min(100, int(55 + pct * 4 + (snap.volume_surge_ratio - 2) * 8)),
                details={"close": snap.close, "ma5": snap.ma5, "pct_above": round(pct,1),
                    "volume": snap.volume, "avg_vol": avg_vol,
                    "vol_ratio": round(snap.volume_surge_ratio,1),
                    "margin_rule": f"{config.screener.breakout_margin_pct}%"})
        return None

    # ── P2: Flags & Pennants ───────────────────
    def _p2_flag_pennant(self, closes, volumes, avg_vol):
        if len(closes) < 10: return None
        ps = closes[-10]; pe = closes[-5]
        if ps <= 0: return None
        pole = ((pe - ps) / ps) * 100
        if pole < config.screener.flag_pole_min_pct: return None
        cv = volumes[-5:-1]
        if not cv: return None
        acv = sum(cv) / len(cv)
        shrink = acv < avg_vol * 0.8
        ch = max(closes[-5:-1])
        bo = closes[-1] > ch
        vbo = volumes[-1] > avg_vol
        if shrink and bo and vbo:
            return PatternDetected(
                name="Flag Breakout", emoji="\\U0001F3F4",
                description=f"Pole +{pole:.0f}%, konsolidasi, breakout!",
                strength=min(100, int(55 + pole * 2)),
                details={"pole_start": ps, "pole_end": pe, "pole_pct": round(pole,1),
                    "consol_vol_shrink": f"{(1-acv/avg_vol)*100:.0f}%",
                    "breakout_price": closes[-1], "consol_high": ch,
                    "breakout_vol": volumes[-1]})
        return None

    # ── P3: RSI Short Bounce ──────────────────
    def _p3_rsi_bounce(self, closes):
        period = config.screener.rsi_short_period
        if len(closes) < period + 3: return None
        # Current RSI
        rsi_now = self._quick_rsi(closes, period)
        # Previous RSI (2 bars ago)
        rsi_prev = self._quick_rsi(closes[:-2], period)
        if rsi_now is None or rsi_prev is None: return None
        # Was oversold, now crossing up
        if rsi_prev < config.screener.rsi_oversold and rsi_now > rsi_prev + 5:
            return PatternDetected(
                name=f"RSI-{period} Bounce", emoji="\\U0001F4C8",
                description=f"RSI {rsi_prev:.0f} -> {rsi_now:.0f} (bounce dari oversold)",
                strength=min(100, int(50 + (rsi_now - rsi_prev) * 2)),
                details={"rsi_prev": round(rsi_prev,1), "rsi_now": round(rsi_now,1),
                    "period": period, "threshold": config.screener.rsi_oversold})
        return None

    def _quick_rsi(self, closes, period):
        if len(closes) < period + 1: return None
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(d, 0) for d in deltas]; losses = [abs(min(d, 0)) for d in deltas]
        ag = sum(gains[:period]) / period; al = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            ag = (ag * (period-1) + gains[i]) / period
            al = (al * (period-1) + losses[i]) / period
        return 100.0 if al == 0 else 100 - (100 / (1 + ag/al))

    # ── P4: Gap (Breakaway/Runaway) ───────────
    def _p4_gap(self, snap, highs, lows, avg_vol):
        if len(highs) < 2: return None
        ph = highs[-2]; cl = snap.low if snap.low > 0 else lows[-1]
        if cl > ph and ph > 0:
            gp = ((cl - ph) / ph) * 100
            gs = cl - ph
            if snap.volume > avg_vol:
                return PatternDetected(
                    name="Breakaway Gap", emoji="\\u26A1",
                    description=f"Gap +{gp:.1f}%, Vol {snap.volume_surge_ratio:.1f}x",
                    strength=min(100, int(60 + gp * 8)),
                    details={"prev_high": ph, "curr_low": cl,
                        "gap_rp": round(gs), "gap_pct": round(gp,2),
                        "volume": snap.volume, "vol_ratio": round(snap.volume_surge_ratio,1)})
        return None

    # ── P5: Runaway Bar / Spike ───────────────
    def _p5_runaway_bar(self, snap, highs, lows, avg_vol):
        if len(highs) < 11: return None
        ranges = [highs[i]-lows[i] for i in range(-11,-1)]
        ar = sum(ranges)/len(ranges) if ranges else 0
        if ar <= 0: return None
        cr = (snap.high - snap.low) if snap.high > 0 and snap.low > 0 else 0
        rr = cr / ar
        tol = snap.close * 0.01
        cnhi = (snap.high - snap.close) <= tol if snap.high > 0 else False
        if rr >= config.screener.runaway_range_multiplier and cnhi and snap.volume > avg_vol:
            return PatternDetected(
                name="Runaway Bar", emoji="\\U0001F680",
                description=f"Range {rr:.1f}x normal, close di High!",
                strength=min(100, int(60 + rr * 10)),
                details={"open": snap.open, "high": snap.high, "low": snap.low,
                    "close": snap.close, "range": round(cr), "avg_range": round(ar),
                    "range_ratio": round(rr,1),
                    "close_to_high": round(snap.high - snap.close),
                    "volume": snap.volume, "vol_ratio": round(snap.volume_surge_ratio,1)})
        return None

    def _ma(self, p, n):
        if len(p) < n: return 0.0
        return sum(p[-n:]) / n

    def _get_hist(self, ticker):
        now = datetime.now()
        if ticker in self._hist_cache and self._cache_exp.get(ticker, now) > now:
            return self._hist_cache[ticker]
        data = self.fetcher.fetch_historical(ticker, 30)
        self._hist_cache[ticker] = data
        self._cache_exp[ticker] = now + timedelta(hours=1)
        return data

    def _cooldown(self, ticker):
        if ticker not in self.alert_history: return False
        return datetime.now() - self.alert_history[ticker] < timedelta(minutes=config.screener.alert_cooldown_minutes)
''')
print("  [OK] screener.py (5 parameter baru)")

# ═══════════════════════════════════════
# telegram_bot.py — same as v4 but with stock count
# ═══════════════════════════════════════
# (keeping v4's telegram_bot.py, just update /start message)
bot_path = os.path.join(DIR, "telegram_bot.py")
if os.path.exists(bot_path):
    content = open(bot_path, "r", encoding="utf-8").read()
    # Update pattern list in /start
    old = '"  \\\\U0001F4A5  Breakout + Volume (aturan 3%)\\\\n"'
    if "Breakout + Volume (aturan 3%)" in content:
        content = content.replace(
            "Breakout + Volume (aturan 3%)",
            "Volume Breakout (aturan 3%)")
        content = content.replace(
            "Flag/Pennant Breakout",
            "Flag/Pennant Breakout")
        # Add RSI bounce pattern
        if "RSI-6 Bounce" not in content:
            content = content.replace(
                '  \\U0001F680  Runaway Day / Spike\\n\\n',
                '  \\U0001F4C8  RSI-6 Bounce (oversold recovery)\\n'
                '  \\U0001F680  Runaway Bar / Spike\\n\\n')
        with open(bot_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  [OK] telegram_bot.py (updated patterns)")
    else:
        print("  [OK] telegram_bot.py (no changes needed)")
else:
    print("  [WARN] telegram_bot.py not found, run upgrade_v4.py first")

print(f"""
  ==========================================
  UPGRADE v5 COMPLETE!
  ==========================================

  Perubahan:
  1. Scan ~150 saham liquid IHSG (bukan 40)
     + auto-load full list dari iTick jika tersedia
  2. 5 parameter screener baru:
     P1. Volume Breakout (aturan 3%)
     P2. Flag/Pennant Breakout
     P3. RSI-6 Bounce (oversold recovery)
     P4. Breakaway/Runaway Gap
     P5. Runaway Bar / Spike
  3. Batch scanning (20/batch, rate limited)
  4. Scan interval: 60s untuk full cycle

  TEST:  python main.py
  ==========================================
""")
