"""
IHSG Alert Bot - Fix Script
Fixes: timezone (JST→WIB), watchlist display, Stockbit source
Jalankan: python create_bot_fix.py
"""
import os

DIR = r"C:\ihsg-bot"
print(f"\n  Patching files in {DIR}...\n")

# ═══════════════════════════════════════
# telegram_bot.py - FIXED timezone + watchlist display
# ═══════════════════════════════════════
with open(os.path.join(DIR, "telegram_bot.py"), "w", encoding="utf-8") as f:
    f.write('''import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import config
from screener import AlertSignal, ScreenerEngine

logger = logging.getLogger(__name__)

# WIB timezone (UTC+7)
WIB = timezone(timedelta(hours=7))


def now_wib():
    """Get current time in WIB regardless of system timezone"""
    return datetime.now(WIB)


def is_market_hours():
    """Check if IDX market is open (WIB time)"""
    now = now_wib()
    h, m = now.hour, now.minute
    weekday = now.weekday()  # 0=Mon, 6=Sun

    # Weekend
    if weekday >= 5:
        return False

    # Sesi 1: 09:00 - 11:30 WIB
    session_1 = (h == 9) or (h == 10) or (h == 11 and m <= 30)
    # Sesi 2: 13:30 - 15:00 WIB
    session_2 = (h == 13 and m >= 30) or (h == 14) or (h == 15 and m == 0)

    return session_1 or session_2


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
        t = now_wib().strftime("%H:%M:%S")
        msg += f"\\n{t} WIB\\nBukan rekomendasi investasi. DYOR!"
        return msg

    @staticmethod
    def format_summary(alerts, total):
        t = now_wib().strftime("%H:%M:%S")
        msg = f"SCAN {t} WIB\\n"
        msg += f"Scanned: {total} | Strong Buy: {len(alerts)}\\n\\n"
        if not alerts:
            msg += "Belum ada sinyal Strong Buy saat ini.\\n"
            msg += "Bot akan terus memantau selama jam pasar."
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

        # Show startup info with watchlist
        n = len(config.datasource.watchlist)
        src = self.screener.fetcher.source_name
        wl = config.datasource.watchlist
        t = now_wib().strftime("%H:%M:%S")
        mkt = "BUKA" if is_market_hours() else "TUTUP"

        msg = f"IHSG Alert Bot Started!\\n"
        msg += f"============================\\n\\n"
        msg += f"Waktu: {t} WIB\\n"
        msg += f"Pasar: {mkt}\\n"
        msg += f"Source: {src}\\n"
        msg += f"Saham: {n} tickers\\n\\n"
        msg += f"--- Watchlist ---\\n"
        for i in range(0, len(wl), 8):
            msg += " ".join(wl[i:i+8]) + "\\n"
        msg += f"\\n--- Screener ---\\n"
        msg += f"Volume Surge: >= {config.screener.volume_surge_multiplier}x avg\\n"
        msg += f"Max Drop: <= {config.screener.max_drop_from_high_pct}% dari high\\n"
        msg += f"MA: {config.screener.ma_short}/{config.screener.ma_medium}\\n"
        msg += f"Scan interval: {config.datasource.scan_interval_seconds}s\\n\\n"
        msg += "Commands:\\n"
        msg += "/scan - Scan manual sekarang\\n"
        msg += "/detail BBCA - Analisis 1 saham\\n"
        msg += "/watchlist - Lihat watchlist\\n"
        msg += "/add TICKER - Tambah saham\\n"
        msg += "/remove TICKER - Hapus saham\\n"
        msg += "/stop - Hentikan bot"

        await update.message.reply_text(msg)
        self._task = asyncio.create_task(self._loop(update.effective_chat.id, ctx))

    async def cmd_stop(self, update: Update, ctx):
        self.is_scanning = False
        if self._task:
            self._task.cancel()
        await update.message.reply_text("Bot stopped.")

    async def cmd_scan(self, update: Update, ctx):
        """Manual scan - works anytime, even outside market hours"""
        t = now_wib().strftime("%H:%M:%S")
        mkt = "BUKA" if is_market_hours() else "TUTUP"
        await update.message.reply_text(f"Scanning... ({t} WIB, Pasar: {mkt})")

        alerts = self.screener.scan_all(config.datasource.watchlist)
        await update.message.reply_text(
            AlertFormatter.format_summary(alerts, len(config.datasource.watchlist))
        )
        for a in alerts[:5]:
            await update.message.reply_text(AlertFormatter.format_alert(a))
            await asyncio.sleep(0.5)

    async def cmd_status(self, update: Update, ctx):
        st = "RUNNING" if self.is_scanning else "STOPPED"
        src = self.screener.fetcher.source_name
        n = len(config.datasource.watchlist)
        t = now_wib().strftime("%H:%M:%S")
        mkt = "BUKA" if is_market_hours() else "TUTUP"
        await update.message.reply_text(
            f"Status: {st}\\n"
            f"Waktu: {t} WIB | Pasar: {mkt}\\n"
            f"Source: {src}\\n"
            f"Watchlist: {n} saham\\n\\n"
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
            await update.message.reply_text("Usage: /add BBCA")
            return
        t = ctx.args[0].upper()
        if t not in config.datasource.watchlist:
            config.datasource.watchlist.append(t)
        await update.message.reply_text(f"{t} ditambahkan ({len(config.datasource.watchlist)} total)")

    async def cmd_rm(self, update: Update, ctx):
        if not ctx.args:
            await update.message.reply_text("Usage: /remove BBCA")
            return
        t = ctx.args[0].upper()
        if t in config.datasource.watchlist:
            config.datasource.watchlist.remove(t)
        await update.message.reply_text(f"{t} dihapus ({len(config.datasource.watchlist)} total)")

    async def _loop(self, cid, ctx):
        """Auto-scan loop - only scans during market hours (WIB)"""
        logger.info("Scanning loop started")
        while self.is_scanning:
            try:
                if not is_market_hours():
                    # Outside market hours: check every 5 minutes
                    now = now_wib()
                    logger.debug(f"Market closed ({now.strftime('%H:%M')} WIB). Next check in 5 min.")
                    await asyncio.sleep(300)
                    continue

                # Market is open - run scan
                logger.info("Running scheduled scan...")
                alerts = self.screener.scan_all(config.datasource.watchlist)

                if alerts:
                    logger.info(f"Found {len(alerts)} strong buy signals!")
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

        logger.info("Scanning loop stopped")

    def run(self):
        logger.info("Starting bot...")
        self.app.run_polling(drop_pending_updates=True)
''')
print("  [OK] telegram_bot.py (timezone fix + watchlist display)")

# ═══════════════════════════════════════
# data_fetcher.py - ADD Stockbit support
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


# ════════════════════════════════════════
# Stockbit Data Source (Real-time)
# ════════════════════════════════════════

class StockbitDataSource(DataSource):
    """
    Stockbit REST API - real-time IDX data.
    Login via username/password, then fetch via internal API.
    """

    AUTH_URL = "https://api.stockbit.com/v2.4/login"
    BASE_URL = "https://api.stockbit.com/v2.4"

    def __init__(self):
        self.token = config.datasource.stockbit_token
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": "https://stockbit.com",
            "Referer": "https://stockbit.com/",
        })
        self._authenticated = False

    def _login(self):
        """Login to Stockbit and get token"""
        # If manual token provided
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            self._authenticated = True
            logger.info("Stockbit: using manual token")
            return True

        username = config.datasource.stockbit_username
        password = config.datasource.stockbit_password
        if not username or not password:
            return False

        try:
            resp = self.session.post(
                self.AUTH_URL,
                json={"username": username, "password": password},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("data", {}).get("token", "")
                if self.token:
                    self.session.headers["Authorization"] = f"Bearer {self.token}"
                    self._authenticated = True
                    logger.info("Stockbit: login successful!")
                    return True
            logger.error(f"Stockbit login failed: {resp.status_code} {resp.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"Stockbit login error: {e}")
            return False

    def is_available(self):
        if self._authenticated:
            return True
        return self._login()

    def _get(self, endpoint, params=None):
        """Make authenticated GET request"""
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/{endpoint}",
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("data", {})
            elif resp.status_code == 401:
                # Token expired, try re-login
                logger.warning("Stockbit token expired, re-logging in...")
                self.token = ""
                self._authenticated = False
                if self._login():
                    resp = self.session.get(f"{self.BASE_URL}/{endpoint}", params=params, timeout=10)
                    if resp.status_code == 200:
                        return resp.json().get("data", {})
            return None
        except Exception as e:
            logger.error(f"Stockbit API error: {e}")
            return None

    def fetch_snapshot(self, ticker):
        data = self._get(f"stockdata/{ticker}")
        if not data:
            return None
        try:
            return StockSnapshot(
                ticker=ticker,
                timestamp=datetime.now(),
                open=float(data.get("open", 0)),
                high=float(data.get("high", 0)),
                low=float(data.get("low", 0)),
                close=float(data.get("last", data.get("close", 0))),
                prev_close=float(data.get("prev_close", data.get("prev", 0))),
                volume=int(data.get("volume", data.get("vol", 0))),
                avg_volume_20d=int(data.get("avg_vol_20d", 0)),
            )
        except Exception as e:
            logger.error(f"Stockbit parse error {ticker}: {e}")
            return None

    def fetch_bulk(self, tickers):
        results = {}
        for ticker in tickers:
            snap = self.fetch_snapshot(ticker)
            if snap:
                results[ticker] = snap
            time.sleep(0.2)  # Rate limit
        return results

    def fetch_historical(self, ticker, days=30):
        """Fetch chart data from Stockbit"""
        try:
            end = int(datetime.now().timestamp())
            start = int((datetime.now() - timedelta(days=days)).timestamp())
            data = self._get(f"chart/{ticker}", params={
                "interval": "D", "from": start, "to": end,
            })
            if not data:
                return []

            result = []
            timestamps = data.get("t", [])
            opens = data.get("o", [])
            highs = data.get("h", [])
            lows = data.get("l", [])
            closes = data.get("c", [])
            volumes = data.get("v", [])

            for i in range(len(timestamps)):
                result.append({
                    "date": datetime.fromtimestamp(timestamps[i]).strftime("%Y-%m-%d"),
                    "open": float(opens[i]) if i < len(opens) else 0,
                    "high": float(highs[i]) if i < len(highs) else 0,
                    "low": float(lows[i]) if i < len(lows) else 0,
                    "close": float(closes[i]) if i < len(closes) else 0,
                    "volume": int(volumes[i]) if i < len(volumes) else 0,
                })
            return result
        except Exception as e:
            logger.error(f"Stockbit historical error {ticker}: {e}")
            return []


# ════════════════════════════════════════
# Yahoo Finance Data Source (Fallback)
# ════════════════════════════════════════

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
                    "open": float(r["Open"]), "high": float(r["High"]),
                    "low": float(r["Low"]), "close": float(r["Close"]),
                    "volume": int(r["Volume"]),
                }
                for idx, r in hist.iterrows()
            ]
        except Exception:
            return []


# ════════════════════════════════════════
# Data Fetcher Manager (Auto-fallback)
# ════════════════════════════════════════

class DataFetcher:
    """
    Priority: Stockbit (real-time) -> Yahoo Finance (delayed)
    """
    def __init__(self):
        self.sources = []
        self.active_source = None
        self._init_sources()

    def _init_sources(self):
        # 1. Try Stockbit
        has_sb = bool(
            config.datasource.stockbit_token or
            (config.datasource.stockbit_username and config.datasource.stockbit_password)
        )
        if has_sb:
            try:
                sb = StockbitDataSource()
                if sb.is_available():
                    self.sources.append(sb)
                    logger.info("Stockbit: ACTIVE (real-time)")
                else:
                    logger.warning("Stockbit: login failed, using Yahoo fallback")
            except Exception as e:
                logger.warning(f"Stockbit error: {e}")

        # 2. Yahoo Finance fallback
        yahoo = YahooDataSource()
        self.sources.append(yahoo)
        if not self.sources[0].__class__.__name__.startswith("Stockbit"):
            logger.info("Yahoo Finance: ACTIVE (delayed ~15min)")

        self.active_source = self.sources[0]

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
        if self.active_source:
            name = type(self.active_source).__name__
            if "Stockbit" in name:
                return "Stockbit (Real-time)"
            return name
        return "None"
''')
print("  [OK] data_fetcher.py (Stockbit + Yahoo auto-fallback)")

print()
print("  ====================================")
print("  FIX COMPLETE!")
print("  ====================================")
print()
print("  Fixed:")
print("  1. Timezone: sekarang pakai WIB (bukan system time)")
print("  2. /start: tampilkan watchlist + parameter screener")
print("  3. Stockbit: auto-login jika credentials diisi di .env")
print("  4. /scan: bisa dipakai kapanpun (termasuk di luar jam pasar)")
print()
print("  Jalankan bot:")
print("    python main.py")
print()