"""
IHSG Alert Bot - File Generator
Jalankan: python create_bot.py
Otomatis buat semua file Python di folder yang sama.
"""
import os, sys

DIR = os.path.dirname(os.path.abspath(__file__))
print(f"\n  Creating bot files in {DIR}...\n")

# ═══════════════════════════════════════
# config.py
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
    volume_surge_multiplier: float = 2.5
    volume_window_minutes: int = 15
    volume_avg_period: int = 20
    max_drop_from_high_pct: float = 5.0
    ma_short: int = 3
    ma_medium: int = 5
    ma_tolerance_pct: float = 1.0
    alert_cooldown_minutes: int = 30
    min_price: int = 100
    min_daily_volume: int = 100_000

@dataclass
class IndicatorConfig:
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
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
    stockbit_username: str = os.getenv("STOCKBIT_USERNAME", "")
    stockbit_password: str = os.getenv("STOCKBIT_PASSWORD", "")
    stockbit_token: str = os.getenv("STOCKBIT_TOKEN", "")
    goapi_token: str = os.getenv("GOAPI_TOKEN", "")
    goapi_base_url: str = "https://api.goapi.io/stock/idx"
    sectors_api_key: str = os.getenv("SECTORS_API_KEY", "")
    sectors_base_url: str = "https://api.sectors.app/v1"
    use_yahoo_fallback: bool = True
    scan_interval_seconds: int = 5
    watchlist: List[str] = field(default_factory=lambda: [
        "BBCA","BBRI","BMRI","BBNI","TLKM","ASII","UNVR","HMSP",
        "ICBP","INDF","KLBF","PGAS","PTBA","ADRO","ANTM","INCO",
        "MEDC","ITMG","EXCL","ISAT","SMGR","INKP","TKIM","BRPT",
        "ESSA","ACES","MAPI","ERAA","AMRT","CPIN","JPFA","MDKA",
        "TOWR","TBIG","MTEL","BRIS","ARTO","BUKA","GOTO","EMTK",
    ])

@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    screener: ScreenerConfig = field(default_factory=ScreenerConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    datasource: DataSourceConfig = field(default_factory=DataSourceConfig)
    market_open_hour: int = 9
    market_close_hour: int = 15
    timezone: str = "Asia/Jakarta"
    log_level: str = "INFO"

config = AppConfig()
''')
print("  [OK] config.py")

# ═══════════════════════════════════════
# indicators.py
# ═══════════════════════════════════════
with open(os.path.join(DIR, "indicators.py"), "w", encoding="utf-8") as f:
    f.write('''from dataclasses import dataclass
from typing import List, Optional

@dataclass
class RSIResult:
    value: float
    signal: str
    is_bullish: bool
    avg_gain: float = 0.0
    avg_loss: float = 0.0

    @property
    def description(self):
        if self.value <= 30:
            return f"RSI {self.value:.1f} - OVERSOLD (potensi rebound)"
        elif self.value >= 70:
            return f"RSI {self.value:.1f} - OVERBOUGHT"
        elif 30 < self.value <= 50:
            return f"RSI {self.value:.1f} - Zona recovery bullish"
        else:
            return f"RSI {self.value:.1f} - Neutral"

@dataclass
class BollingerResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float
    percent_b: float
    is_squeeze: bool
    signal: str

    @property
    def description(self):
        if self.is_squeeze:
            return f"BB Squeeze! BW={self.bandwidth:.1f}% (potensi breakout)"
        elif self.percent_b >= 0.8:
            return f"BB %B={self.percent_b:.2f} - Dekat upper band"
        elif self.percent_b <= 0.2:
            return f"BB %B={self.percent_b:.2f} - Dekat lower band"
        else:
            return f"BB %B={self.percent_b:.2f} - Di dalam band"

@dataclass
class MACDResult:
    macd_line: float
    signal_line: float
    histogram: float
    is_bullish_cross: bool
    is_bearish_cross: bool
    histogram_increasing: bool
    signal: str

    @property
    def description(self):
        if self.is_bullish_cross:
            return f"MACD Bullish Cross! Hist={self.histogram:+.1f}"
        elif self.is_bearish_cross:
            return f"MACD Bearish Cross Hist={self.histogram:+.1f}"
        elif self.histogram > 0 and self.histogram_increasing:
            return f"MACD Bullish momentum Hist={self.histogram:+.1f}"
        elif self.histogram > 0:
            return f"MACD Positif, melemah Hist={self.histogram:+.1f}"
        else:
            return f"MACD Negatif Hist={self.histogram:+.1f}"

@dataclass
class StochasticResult:
    k: float
    d: float
    signal: str
    is_bullish_cross: bool

    @property
    def description(self):
        if self.k <= 20 and self.is_bullish_cross:
            return f"Stoch %K={self.k:.0f} Bullish cross OVERSOLD!"
        elif self.k <= 20:
            return f"Stoch %K={self.k:.0f} %D={self.d:.0f} OVERSOLD"
        elif self.k >= 80:
            return f"Stoch %K={self.k:.0f} %D={self.d:.0f} OVERBOUGHT"
        elif self.is_bullish_cross:
            return f"Stoch Bullish cross %K={self.k:.0f}>%D={self.d:.0f}"
        else:
            return f"Stoch %K={self.k:.0f} %D={self.d:.0f}"

@dataclass
class VWAPResult:
    vwap: float
    price_vs_vwap_pct: float
    is_above: bool

    @property
    def description(self):
        pos = "di atas" if self.is_above else "di bawah"
        return f"VWAP={self.vwap:,.0f} | Harga {pos} VWAP ({self.price_vs_vwap_pct:+.1f}%)"

@dataclass
class IndicatorSuite:
    rsi: Optional[RSIResult] = None
    bollinger: Optional[BollingerResult] = None
    macd: Optional[MACDResult] = None
    stochastic: Optional[StochasticResult] = None
    vwap: Optional[VWAPResult] = None

    @property
    def bullish_count(self):
        c = 0
        if self.rsi and self.rsi.is_bullish: c += 1
        if self.bollinger and self.bollinger.percent_b >= 0.5: c += 1
        if self.macd and (self.macd.is_bullish_cross or self.macd.histogram > 0): c += 1
        if self.stochastic and self.stochastic.is_bullish_cross: c += 1
        if self.vwap and self.vwap.is_above: c += 1
        return c

    @property
    def total_indicators(self):
        return sum(1 for x in [self.rsi, self.bollinger, self.macd, self.stochastic, self.vwap] if x is not None)

    @property
    def confluence_score(self):
        if self.total_indicators == 0: return 0
        return int(self.bullish_count / self.total_indicators * 100)


class TechnicalIndicators:

    @staticmethod
    def calc_rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]
        ag = sum(gains[:period]) / period
        al = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            ag = (ag * (period - 1) + gains[i]) / period
            al = (al * (period - 1) + losses[i]) / period
        rsi = 100.0 if al == 0 else 100 - (100 / (1 + ag / al))
        sig = "OVERSOLD" if rsi <= 30 else ("OVERBOUGHT" if rsi >= 70 else "NEUTRAL")
        return RSIResult(value=rsi, signal=sig, is_bullish=(rsi > 30 and rsi < 70), avg_gain=ag, avg_loss=al)

    @staticmethod
    def calc_bollinger(closes, period=20, num_std=2.0):
        if len(closes) < period:
            return None
        w = closes[-period:]
        mid = sum(w) / period
        std = (sum((x - mid)**2 for x in w) / period) ** 0.5
        upper = mid + num_std * std
        lower = mid - num_std * std
        br = upper - lower
        pb = (closes[-1] - lower) / br if br > 0 else 0.5
        bw = (br / mid * 100) if mid > 0 else 0
        sq = bw < 10
        sig = "SQUEEZE" if sq else ("NEAR_UPPER" if pb >= 0.8 else ("NEAR_LOWER" if pb <= 0.2 else "INSIDE"))
        return BollingerResult(upper=upper, middle=mid, lower=lower, bandwidth=bw, percent_b=pb, is_squeeze=sq, signal=sig)

    @staticmethod
    def _calc_ema(data, period):
        if len(data) < period:
            return None
        m = 2 / (period + 1)
        vals = [sum(data[:period]) / period]
        for i in range(period, len(data)):
            vals.append(data[i] * m + vals[-1] * (1 - m))
        return vals

    @staticmethod
    def calc_macd(closes, fast=12, slow=26, sig_p=9):
        if len(closes) < slow + sig_p:
            return None
        ef = TechnicalIndicators._calc_ema(closes, fast)
        es = TechnicalIndicators._calc_ema(closes, slow)
        if not ef or not es:
            return None
        ml = min(len(ef), len(es))
        mv = [ef[-(ml-i)] - es[-(ml-i)] for i in range(ml)]
        if len(mv) < sig_p:
            return None
        sv = TechnicalIndicators._calc_ema(mv, sig_p)
        if not sv or len(sv) < 2:
            return None
        mline = mv[-1]
        sline = sv[-1]
        hist = mline - sline
        pmac = mv[-2]
        psig = sv[-2]
        bc = pmac <= psig and mline > sline
        brc = pmac >= psig and mline < sline
        hi = hist > (pmac - psig)
        sig = "BULLISH_CROSS" if bc else ("BEARISH_CROSS" if brc else ("BULLISH" if hist > 0 else "BEARISH"))
        return MACDResult(macd_line=mline, signal_line=sline, histogram=hist, is_bullish_cross=bc, is_bearish_cross=brc, histogram_increasing=hi, signal=sig)

    @staticmethod
    def calc_stochastic(highs, lows, closes, k_p=14, d_p=3):
        if len(closes) < k_p + d_p:
            return None
        kvs = []
        for i in range(k_p-1, len(closes)):
            wh = max(highs[i-k_p+1:i+1])
            wl = min(lows[i-k_p+1:i+1])
            kvs.append(((closes[i]-wl)/(wh-wl))*100 if wh != wl else 50.0)
        if len(kvs) < d_p:
            return None
        dvs = [sum(kvs[i-d_p+1:i+1])/d_p for i in range(d_p-1, len(kvs))]
        ck = kvs[-1]
        cd = dvs[-1]
        pk = kvs[-2] if len(kvs) >= 2 else ck
        pd = dvs[-2] if len(dvs) >= 2 else cd
        bc = pk <= pd and ck > cd
        sig = "OVERSOLD_BULLISH" if ck <= 20 and bc else ("OVERSOLD" if ck <= 20 else ("OVERBOUGHT" if ck >= 80 else ("BULLISH_CROSS" if bc else "NEUTRAL")))
        return StochasticResult(k=ck, d=cd, signal=sig, is_bullish_cross=bc)

    @staticmethod
    def calc_vwap(highs, lows, closes, volumes):
        n = min(len(highs), len(lows), len(closes), len(volumes))
        if n == 0:
            return None
        ctv = sum((highs[i]+lows[i]+closes[i])/3 * volumes[i] for i in range(n))
        cv = sum(volumes)
        if cv == 0:
            return None
        vwap = ctv / cv
        cp = closes[-1]
        return VWAPResult(vwap=vwap, price_vs_vwap_pct=((cp-vwap)/vwap)*100, is_above=cp >= vwap)

    @staticmethod
    def calc_all(closes, highs=None, lows=None, volumes=None):
        s = IndicatorSuite()
        if len(closes) >= 15:
            s.rsi = TechnicalIndicators.calc_rsi(closes)
        if len(closes) >= 20:
            s.bollinger = TechnicalIndicators.calc_bollinger(closes)
        if len(closes) >= 35:
            s.macd = TechnicalIndicators.calc_macd(closes)
        if highs and lows and len(closes) >= 17:
            s.stochastic = TechnicalIndicators.calc_stochastic(highs, lows, closes)
        if highs and lows and volumes and len(closes) >= 1:
            s.vwap = TechnicalIndicators.calc_vwap(highs, lows, closes, volumes)
        return s
''')
print("  [OK] indicators.py")

# ═══════════════════════════════════════
# data_fetcher.py
# ═══════════════════════════════════════
with open(os.path.join(DIR, "data_fetcher.py"), "w", encoding="utf-8") as f:
    f.write('''import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import yfinance as yf

from config import config

logger = logging.getLogger(__name__)


@dataclass
class StockSnapshot:
    ticker: str
    timestamp: datetime
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    prev_close: float = 0.0
    volume: int = 0
    avg_volume_20d: int = 0
    volume_history: List[Dict] = field(default_factory=list)
    ma3: float = 0.0
    ma5: float = 0.0
    volume_surge_ratio: float = 0.0
    drop_from_high_pct: float = 0.0

    @property
    def change_pct(self):
        if self.prev_close == 0:
            return 0.0
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


class YahooDataSource(DataSource):
    def _jk(self, t):
        return f"{t}.JK" if not t.endswith(".JK") else t

    def _clean(self, t):
        return t.replace(".JK", "")

    def is_available(self):
        return True

    def fetch_snapshot(self, ticker):
        try:
            yt = yf.Ticker(self._jk(ticker))
            hist = yt.history(period="5d", interval="1d")
            if hist.empty:
                return None
            today = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) >= 2 else today
            hist30 = yt.history(period="1mo", interval="1d")
            avg_vol = int(hist30["Volume"].mean()) if not hist30.empty else 0
            snap = StockSnapshot(
                ticker=self._clean(ticker), timestamp=datetime.now(),
                open=float(today.get("Open", 0)), high=float(today.get("High", 0)),
                low=float(today.get("Low", 0)), close=float(today.get("Close", 0)),
                prev_close=float(prev.get("Close", 0)),
                volume=int(today.get("Volume", 0)), avg_volume_20d=avg_vol,
            )
            intra = yt.history(period="1d", interval="1m")
            if not intra.empty:
                cv = 0
                for idx, row in intra.iterrows():
                    cv += int(row.get("Volume", 0))
                    snap.volume_history.append({
                        "timestamp": idx.to_pydatetime(),
                        "cumulative_volume": cv,
                        "close": float(row.get("Close", 0)),
                    })
            return snap
        except Exception as e:
            logger.error(f"Yahoo error {ticker}: {e}")
            return None

    def fetch_bulk(self, tickers):
        results = {}
        jks = [self._jk(t) for t in tickers]
        try:
            data = yf.download(
                jks, period="1mo", interval="1d",
                group_by="ticker", progress=False, threads=True,
            )
            for ticker in tickers:
                try:
                    jk = self._jk(ticker)
                    if len(tickers) > 1:
                        td = data[jk] if jk in data.columns.get_level_values(0) else None
                    else:
                        td = data
                    if td is None or td.empty:
                        continue
                    td = td.dropna()
                    if td.empty:
                        continue
                    today = td.iloc[-1]
                    prev = td.iloc[-2] if len(td) >= 2 else today
                    av = int(td["Volume"].tail(20).mean())
                    results[ticker] = StockSnapshot(
                        ticker=ticker, timestamp=datetime.now(),
                        open=float(today.get("Open", 0)), high=float(today.get("High", 0)),
                        low=float(today.get("Low", 0)), close=float(today.get("Close", 0)),
                        prev_close=float(prev.get("Close", 0)),
                        volume=int(today.get("Volume", 0)), avg_volume_20d=av,
                    )
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Yahoo bulk error: {e}")
            for t in tickers:
                s = self.fetch_snapshot(t)
                if s:
                    results[t] = s
                time.sleep(0.5)
        return results

    def fetch_historical(self, ticker, days=30):
        try:
            yt = yf.Ticker(self._jk(ticker))
            hist = yt.history(period=f"{days}d", interval="1d")
            return [
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": float(r["Open"]),
                    "high": float(r["High"]),
                    "low": float(r["Low"]),
                    "close": float(r["Close"]),
                    "volume": int(r["Volume"]),
                }
                for idx, r in hist.iterrows()
            ]
        except Exception:
            return []


class DataFetcher:
    def __init__(self):
        self.sources = []
        self.active_source = None
        self._ws_mode = False
        yahoo = YahooDataSource()
        self.sources.append(yahoo)
        logger.info("Yahoo Finance: ACTIVE")
        self.active_source = self.sources[0]

    @property
    def is_realtime(self):
        return self._ws_mode

    def subscribe_realtime(self, tickers):
        pass

    def on_price_update(self, cb):
        pass

    def fetch_snapshot(self, ticker):
        for s in self.sources:
            r = s.fetch_snapshot(ticker)
            if r:
                return r
        return None

    def fetch_bulk(self, tickers):
        for s in self.sources:
            r = s.fetch_bulk(tickers)
            if r:
                return r
        return {}

    def fetch_historical(self, ticker, days=30):
        for s in self.sources:
            r = s.fetch_historical(ticker, days)
            if r:
                return r
        return []

    @property
    def source_name(self):
        return type(self.active_source).__name__ if self.active_source else "None"
''')
print("  [OK] data_fetcher.py")

# ═══════════════════════════════════════
# screener.py
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
    name: str
    passed: bool
    value: float
    threshold: float
    description: str
    strength: int = 0


@dataclass
class AlertSignal:
    ticker: str
    timestamp: datetime
    snapshot: StockSnapshot
    volume_signal: Optional[SignalDetail] = None
    price_strength_signal: Optional[SignalDetail] = None
    ma_signal: Optional[SignalDetail] = None
    indicators: Optional[IndicatorSuite] = None
    is_strong_buy: bool = False
    overall_strength: int = 0
    confidence: str = ""
    reasons: List[str] = field(default_factory=list)


class ScreenerEngine:
    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.alert_history: Dict[str, datetime] = {}
        self._hist_cache: Dict[str, List] = {}
        self._cache_exp: Dict[str, datetime] = {}

    def scan_all(self, tickers):
        alerts = []
        snaps = self.fetcher.fetch_bulk(tickers)
        logger.info(f"Fetched {len(snaps)}/{len(tickers)} snapshots")
        for t, snap in snaps.items():
            try:
                sig = self.analyze(snap)
                if sig and sig.is_strong_buy and not self._cooldown(t):
                    alerts.append(sig)
                    self.alert_history[t] = datetime.now()
            except Exception as e:
                logger.error(f"Error {t}: {e}")
        alerts.sort(key=lambda a: a.overall_strength, reverse=True)
        return alerts

    def analyze(self, snap):
        if not snap or snap.close <= 0:
            return None
        hist = self._get_hist(snap.ticker)
        closes = [d["close"] for d in hist if "close" in d] + [snap.close]
        highs = [d.get("high", d["close"]) for d in hist if "close" in d] + [snap.high or snap.close]
        lows = [d.get("low", d["close"]) for d in hist if "close" in d] + [snap.low or snap.close]
        volumes = [d.get("volume", 0) for d in hist if "close" in d] + [snap.volume]

        snap.ma3 = self._ma(closes, config.screener.ma_short)
        snap.ma5 = self._ma(closes, config.screener.ma_medium)

        vs = self._vol_surge(snap)
        ps = self._price_str(snap)
        ms = self._ma_align(snap)
        inds = TechnicalIndicators.calc_all(closes, highs, lows, volumes)

        alert = AlertSignal(
            ticker=snap.ticker, timestamp=datetime.now(), snapshot=snap,
            volume_signal=vs, price_strength_signal=ps, ma_signal=ms, indicators=inds,
        )

        if vs.passed and ps.passed and ms.passed:
            alert.is_strong_buy = True
            base = int(vs.strength * 0.4 + ps.strength * 0.35 + ms.strength * 0.25)
            bonus = int(inds.bullish_count * config.indicators.confluence_weight * 100) if inds else 0
            alert.overall_strength = min(100, base + bonus)
            if alert.overall_strength >= 80:
                alert.confidence = "VERY HIGH"
            elif alert.overall_strength >= 65:
                alert.confidence = "HIGH"
            elif alert.overall_strength >= 50:
                alert.confidence = "MEDIUM"
            else:
                alert.confidence = "LOW"
            alert.reasons = self._reasons(vs, ps, ms, snap, inds)
        return alert

    def _vol_surge(self, snap):
        th = config.screener.volume_surge_multiplier
        av = snap.avg_volume_20d
        if av <= 0:
            h = self._get_hist(snap.ticker)
            vols = [d.get("volume", 0) for d in h[-20:]]
            av = int(sum(vols) / len(vols)) if vols else 1
            snap.avg_volume_20d = av
        ratio = snap.volume / av if av > 0 else 0
        snap.volume_surge_ratio = ratio
        p = ratio >= th
        if ratio >= 5:
            st = 100
        elif ratio >= th:
            st = int(50 + (ratio - th) / (5.0 - th) * 50)
        else:
            st = int(ratio / th * 50)
        st = min(100, st)
        return SignalDetail("Volume Surge", p, ratio, th, f"Volume {ratio:.1f}x avg 20 hari (threshold: {th}x)", st)

    def _price_str(self, snap):
        md = config.screener.max_drop_from_high_pct
        if snap.high <= 0:
            return SignalDetail("Price Strength", False, 0, md, "No data", 0)
        drop = ((snap.high - snap.close) / snap.high) * 100
        snap.drop_from_high_pct = drop
        p = drop <= md
        if drop <= 0:
            st = 100
        elif drop <= md:
            st = int(100 - drop / md * 50)
        else:
            st = max(0, int(50 - (drop - md) * 10))
        d = f"Harga {drop:.1f}% dari All Day High"
        if drop <= 1:
            d += " (sangat dekat!)"
        return SignalDetail("Price Strength", p, drop, md, d, st)

    def _ma_align(self, snap):
        tol = config.screener.ma_tolerance_pct / 100
        if snap.ma3 <= 0 or snap.ma5 <= 0:
            return SignalDetail("MA Alignment", False, 0, 0, "Insufficient data", 0)
        m3d = (snap.close - snap.ma3) / snap.ma3
        m5d = (snap.close - snap.ma5) / snap.ma5
        above3 = m3d >= -tol
        above5 = m5d >= -tol
        bull = snap.ma3 >= snap.ma5
        p = above3 and above5 and bull
        st = 0
        if above3:
            st += 35 + (10 if m3d > 0.01 else 0)
        if above5:
            st += 35 + (10 if m5d > 0.01 else 0)
        if bull:
            st += 10
        st = min(100, st)
        d = f"MA3={snap.ma3:,.0f} MA5={snap.ma5:,.0f} | {'MA3>MA5' if bull else 'MA3<MA5'}"
        return SignalDetail("MA3/MA5 Alignment", p, m3d * 100, tol * 100, d, st)

    def _ma(self, prices, period):
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period

    def _get_hist(self, ticker):
        now = datetime.now()
        if ticker in self._hist_cache and self._cache_exp.get(ticker, now) > now:
            return self._hist_cache[ticker]
        data = self.fetcher.fetch_historical(ticker, 30)
        self._hist_cache[ticker] = data
        self._cache_exp[ticker] = now + timedelta(hours=1)
        return data

    def _cooldown(self, ticker):
        if ticker not in self.alert_history:
            return False
        return datetime.now() - self.alert_history[ticker] < timedelta(minutes=config.screener.alert_cooldown_minutes)

    def _reasons(self, vs, ps, ms, snap, inds):
        r = []
        if vs.value >= 5:
            r.append(f"Volume LUAR BIASA: {vs.value:.1f}x avg")
        elif vs.value >= 3:
            r.append(f"Volume SANGAT tinggi: {vs.value:.1f}x avg")
        else:
            r.append(f"Volume meningkat: {vs.value:.1f}x avg")
        if snap.drop_from_high_pct <= 1:
            r.append(f"Harga di All Day High! (gap {snap.drop_from_high_pct:.1f}%)")
        else:
            r.append(f"Harga bertahan kuat, {snap.drop_from_high_pct:.1f}% dari high")
        if snap.ma3 > snap.ma5:
            r.append(f"MA3({snap.ma3:,.0f}) > MA5({snap.ma5:,.0f}) Bullish")
        if snap.change_pct > 0:
            r.append(f"Naik {snap.change_pct:+.1f}% hari ini")
        if inds:
            if inds.rsi:
                r.append(inds.rsi.description)
            if inds.macd:
                r.append(inds.macd.description)
            if inds.bollinger:
                r.append(inds.bollinger.description)
            if inds.stochastic and inds.stochastic.is_bullish_cross:
                r.append(inds.stochastic.description)
            if inds.vwap and inds.vwap.is_above:
                r.append(inds.vwap.description)
            r.append(f"Konfluensi: {inds.bullish_count}/{inds.total_indicators} bullish (+{inds.bullish_count*5}%)")
        return r
''')
print("  [OK] screener.py")

# ═══════════════════════════════════════
# telegram_bot.py
# ═══════════════════════════════════════
with open(os.path.join(DIR, "telegram_bot.py"), "w", encoding="utf-8") as f:
    f.write('''import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import config
from screener import AlertSignal, ScreenerEngine

logger = logging.getLogger(__name__)


class AlertFormatter:
    @staticmethod
    def format_alert(a):
        s = a.snapshot
        ce = "+" if s.change_pct >= 0 else ""
        msg = "===== STRONG BUY ALERT =====\\n\\n"
        msg += f"Ticker: {s.ticker}\\n"
        msg += f"Harga: Rp {s.close:,.0f} ({ce}{s.change_pct:.1f}%)\\n"
        msg += f"Volume: {s.volume:,} ({s.volume_surge_ratio:.1f}x avg)\\n"
        msg += f"Strength: {a.overall_strength}/100 | {a.confidence}\\n\\n"

        msg += "--- Kriteria ---\\n"
        for sig in [a.volume_signal, a.price_strength_signal, a.ma_signal]:
            if sig:
                ic = "PASS" if sig.passed else "FAIL"
                msg += f"[{ic}] {sig.name}: {sig.description} ({sig.strength}/100)\\n"

        ind = a.indicators
        if ind:
            msg += "\\n--- Indikator ---\\n"
            if ind.rsi:
                msg += f"RSI: {ind.rsi.value:.1f} ({ind.rsi.signal})\\n"
            if ind.macd:
                msg += f"MACD: hist={ind.macd.histogram:+.1f} ({ind.macd.signal})\\n"
            if ind.bollinger:
                msg += f"BB: %B={ind.bollinger.percent_b:.2f} BW={ind.bollinger.bandwidth:.1f}%\\n"
            if ind.stochastic:
                msg += f"Stoch: %K={ind.stochastic.k:.0f} %D={ind.stochastic.d:.0f}\\n"
            if ind.vwap:
                msg += f"VWAP: {ind.vwap.vwap:,.0f} ({ind.vwap.price_vs_vwap_pct:+.1f}%)\\n"
            msg += f"Konfluensi: {ind.bullish_count}/{ind.total_indicators} bullish\\n"

        if a.reasons:
            msg += "\\nAlasan:\\n"
            for r in a.reasons:
                msg += f"- {r}\\n"
        msg += f"\\n{a.timestamp.strftime('%H:%M:%S')} WIB\\nBukan rekomendasi investasi. DYOR!"
        return msg

    @staticmethod
    def format_summary(alerts, total):
        msg = f"SCAN {datetime.now().strftime('%H:%M:%S')}\\n"
        msg += f"Scanned: {total} | Found: {len(alerts)}\\n\\n"
        if not alerts:
            msg += "Belum ada sinyal Strong Buy."
            return msg
        for i, a in enumerate(alerts, 1):
            s = a.snapshot
            msg += f"{i}. {s.ticker} Rp {s.close:,.0f} ({s.change_pct:+.1f}%) "
            msg += f"Vol:{s.volume_surge_ratio:.1f}x Str:{a.overall_strength}/100\\n"
        msg += "\\n/detail TICKER untuk detail"
        return msg


class IHSGAlertBot:
    def __init__(self, screener):
        self.screener = screener
        self.is_scanning = False
        self._task = None
        self.app = Application.builder().token(config.telegram.bot_token).build()
        for cmd, fn in [
            ("start", self.cmd_start), ("stop", self.cmd_stop),
            ("scan", self.cmd_scan), ("status", self.cmd_status),
            ("detail", self.cmd_detail), ("watchlist", self.cmd_wl),
            ("add", self.cmd_add), ("remove", self.cmd_rm),
            ("help", self.cmd_status),
        ]:
            self.app.add_handler(CommandHandler(cmd, fn))

    async def cmd_start(self, update: Update, ctx):
        if self.is_scanning:
            await update.message.reply_text("Bot sudah berjalan!")
            return
        self.is_scanning = True
        n = len(config.datasource.watchlist)
        src = self.screener.fetcher.source_name
        await update.message.reply_text(
            f"IHSG Alert Bot Started!\\n{n} saham | Source: {src}\\nKirim /stop untuk berhenti."
        )
        self._task = asyncio.create_task(self._loop(update.effective_chat.id, ctx))

    async def cmd_stop(self, update: Update, ctx):
        self.is_scanning = False
        if self._task:
            self._task.cancel()
        await update.message.reply_text("Bot stopped.")

    async def cmd_scan(self, update: Update, ctx):
        await update.message.reply_text("Scanning...")
        alerts = self.screener.scan_all(config.datasource.watchlist)
        await update.message.reply_text(
            AlertFormatter.format_summary(alerts, len(config.datasource.watchlist))
        )
        for a in alerts[:3]:
            await update.message.reply_text(AlertFormatter.format_alert(a))
            await asyncio.sleep(0.5)

    async def cmd_status(self, update: Update, ctx):
        st = "RUNNING" if self.is_scanning else "STOPPED"
        src = self.screener.fetcher.source_name
        n = len(config.datasource.watchlist)
        await update.message.reply_text(
            f"Status: {st}\\nSource: {src}\\nWatchlist: {n}\\n\\n"
            "/start /stop /scan /detail /watchlist /add /remove"
        )

    async def cmd_detail(self, update: Update, ctx):
        if not ctx.args:
            await update.message.reply_text("Usage: /detail BBCA")
            return
        t = ctx.args[0].upper()
        await update.message.reply_text(f"Analyzing {t}...")
        snap = self.screener.fetcher.fetch_snapshot(t)
        if not snap:
            await update.message.reply_text(f"Gagal fetch {t}")
            return
        alert = self.screener.analyze(snap)
        if not alert:
            await update.message.reply_text(f"Gagal analisis {t}")
            return
        await update.message.reply_text(AlertFormatter.format_alert(alert))

    async def cmd_wl(self, update: Update, ctx):
        wl = config.datasource.watchlist
        msg = f"Watchlist ({len(wl)}):\\n\\n"
        for i in range(0, len(wl), 8):
            msg += " ".join(wl[i:i+8]) + "\\n"
        msg += "\\n/add TICKER | /remove TICKER"
        await update.message.reply_text(msg)

    async def cmd_add(self, update: Update, ctx):
        if not ctx.args:
            return
        t = ctx.args[0].upper()
        if t not in config.datasource.watchlist:
            config.datasource.watchlist.append(t)
        await update.message.reply_text(f"{t} ditambahkan")

    async def cmd_rm(self, update: Update, ctx):
        if not ctx.args:
            return
        t = ctx.args[0].upper()
        if t in config.datasource.watchlist:
            config.datasource.watchlist.remove(t)
        await update.message.reply_text(f"{t} dihapus")

    async def _loop(self, cid, ctx):
        while self.is_scanning:
            try:
                now = datetime.now()
                h, m = now.hour, now.minute
                s1 = (h == 9) or (h == 10) or (h == 11 and m <= 30)
                s2 = (h == 13 and m >= 30) or (h == 14) or (h == 15 and m == 0)
                if not (s1 or s2):
                    await asyncio.sleep(300)
                    continue
                alerts = self.screener.scan_all(config.datasource.watchlist)
                for a in alerts[:3]:
                    try:
                        await ctx.bot.send_message(
                            chat_id=cid, text=AlertFormatter.format_alert(a)
                        )
                    except Exception as e:
                        logger.error(f"Send error: {e}")
                    await asyncio.sleep(1)
                await asyncio.sleep(config.datasource.scan_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(10)

    def run(self):
        logger.info("Starting bot...")
        self.app.run_polling(drop_pending_updates=True)
''')
print("  [OK] telegram_bot.py")

# ═══════════════════════════════════════
# main.py
# ═══════════════════════════════════════
with open(os.path.join(DIR, "main.py"), "w", encoding="utf-8") as f:
    f.write('''import logging
import sys
from datetime import datetime

from config import config
from data_fetcher import DataFetcher
from screener import ScreenerEngine
from telegram_bot import IHSGAlertBot


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    print()
    print("  ====================================")
    print("  IHSG STRONG BUY ALERT BOT")
    print("  ====================================")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Watchlist: {len(config.datasource.watchlist)} saham")
    print()

    if not config.telegram.bot_token:
        print("  ERROR: TELEGRAM_BOT_TOKEN not set in .env!")
        sys.exit(1)

    fetcher = DataFetcher()
    screener = ScreenerEngine(fetcher)
    bot = IHSGAlertBot(screener)

    print("  Bot running! Kirim /start di Telegram.")
    print("  Press Ctrl+C to stop.\\n")

    try:
        bot.run()
    except KeyboardInterrupt:
        print("\\n  Stopped.")


if __name__ == "__main__":
    main()
''')
print("  [OK] main.py")

# ═══════════════════════════════════════
# Done!
# ═══════════════════════════════════════
print()
print("  ====================================")
print("  SETUP COMPLETE!")
print("  ====================================")
print()
print(f"  Folder: {DIR}")
print(f"  Files: config.py, indicators.py, data_fetcher.py,")
print(f"         screener.py, telegram_bot.py, main.py")
print()
print("  NEXT: pastikan .env sudah diisi, lalu jalankan:")
print(f"    cd {DIR}")
print("    python main.py")
print()
