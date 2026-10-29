import logging, time, json
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
