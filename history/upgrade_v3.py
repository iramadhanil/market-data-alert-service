"""
IHSG Alert Bot - UPGRADE v3
=============================
1. Formula baru: 4 pola deteksi (Breakout, Gap, Flag, Runaway)
2. Tampilan Telegram aesthetic + emoji tasteful
Jalankan: python upgrade_v3.py
"""
import os
DIR = r"C:\ihsg-bot"
print("\n  Upgrading to v3...\n")

# ═══════════════════════════════════════
# screener.py — NEW FORMULAS
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
    emoji: str = ""


@dataclass
class PatternDetected:
    """Pola yang terdeteksi"""
    name: str
    description: str
    strength: int = 0  # 0-100


@dataclass
class AlertSignal:
    ticker: str
    timestamp: datetime
    snapshot: StockSnapshot
    # Core signals
    volume_signal: Optional[SignalDetail] = None
    breakout_signal: Optional[SignalDetail] = None
    price_strength_signal: Optional[SignalDetail] = None
    ma_signal: Optional[SignalDetail] = None
    # Patterns detected
    patterns: List[PatternDetected] = field(default_factory=list)
    # Indicators
    indicators: Optional[IndicatorSuite] = None
    # Overall
    is_strong_buy: bool = False
    overall_strength: int = 0
    confidence: str = ""
    reasons: List[str] = field(default_factory=list)


class ScreenerEngine:
    """
    Screener berdasarkan 4 pola dari Technical Analysis:

    1. BREAKOUT + VOLUME EXPLOSION (Aturan 3%)
       Volume >= 2x avg AND Close > MA AND Close >= MA * 1.03

    2. BREAKAWAY GAP
       Low saat ini > High sebelumnya AND Volume > avg

    3. FLAGS & PENNANTS
       Kenaikan tajam -> konsolidasi volume menyusut -> breakout

    4. RUNAWAY DAYS / SPIKES
       Range > 2x avg range AND Open near Low AND Close near High
    """

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
        if len(hist) < 5:
            return None

        closes = [d["close"] for d in hist] + [snap.close]
        highs = [d.get("high", d["close"]) for d in hist] + [snap.high or snap.close]
        lows = [d.get("low", d["close"]) for d in hist] + [snap.low or snap.close]
        volumes = [d.get("volume", 0) for d in hist] + [snap.volume]
        opens = [d.get("open", d["close"]) for d in hist] + [snap.open or snap.close]

        # MAs
        snap.ma3 = self._ma(closes, config.screener.ma_short)
        snap.ma5 = self._ma(closes, config.screener.ma_medium)

        # Avg volume 20d
        vol_window = volumes[-21:-1] if len(volumes) > 21 else volumes[:-1]
        avg_vol = int(sum(vol_window) / len(vol_window)) if vol_window else 1
        if avg_vol <= 0:
            avg_vol = 1
        snap.avg_volume_20d = avg_vol
        snap.volume_surge_ratio = snap.volume / avg_vol

        # ── 4 Pattern Detection ─────────────────────
        patterns = []

        # Pattern 1: Breakout + Volume Explosion (3% rule)
        p1 = self._detect_breakout_volume(snap, closes, volumes, avg_vol)
        if p1: patterns.append(p1)

        # Pattern 2: Breakaway Gap
        p2 = self._detect_gap(snap, highs, lows, volumes, avg_vol)
        if p2: patterns.append(p2)

        # Pattern 3: Flags & Pennants
        p3 = self._detect_flag(closes, volumes, avg_vol)
        if p3: patterns.append(p3)

        # Pattern 4: Runaway Days / Spikes
        p4 = self._detect_runaway(snap, highs, lows, opens, closes, volumes, avg_vol)
        if p4: patterns.append(p4)

        # ── Core signals ────────────────────────────
        vol_signal = self._check_volume(snap, avg_vol)
        price_signal = self._check_price_strength(snap)
        ma_signal = self._check_ma(snap)

        # ── Indicators ──────────────────────────────
        inds = TechnicalIndicators.calc_all(closes, highs, lows, volumes)

        # ── Build alert ─────────────────────────────
        alert = AlertSignal(
            ticker=snap.ticker, timestamp=datetime.now(), snapshot=snap,
            volume_signal=vol_signal, price_strength_signal=price_signal,
            ma_signal=ma_signal, patterns=patterns, indicators=inds,
        )

        # Strong Buy = at least 1 pattern detected + volume surge
        has_pattern = len(patterns) > 0
        vol_ok = vol_signal.passed

        if has_pattern and vol_ok:
            alert.is_strong_buy = True

            # Strength from patterns
            pattern_str = max(p.strength for p in patterns)
            vol_str = vol_signal.strength
            price_str = price_signal.strength

            base = int(pattern_str * 0.45 + vol_str * 0.35 + price_str * 0.20)

            # Confluence bonus
            bonus = 0
            if inds:
                bonus = int(inds.bullish_count * config.indicators.confluence_weight * 100)
            # Extra bonus per additional pattern
            bonus += (len(patterns) - 1) * 5

            alert.overall_strength = min(100, base + bonus)

            if alert.overall_strength >= 80:
                alert.confidence = "VERY HIGH"
            elif alert.overall_strength >= 65:
                alert.confidence = "HIGH"
            elif alert.overall_strength >= 50:
                alert.confidence = "MEDIUM"
            else:
                alert.confidence = "MODERATE"

            alert.reasons = self._build_reasons(snap, patterns, inds)

        return alert

    # ── Pattern 1: Breakout + Volume Explosion ──────

    def _detect_breakout_volume(self, snap, closes, volumes, avg_vol):
        """
        Breakout Resistensi + Ledakan Volume (Aturan 3%)
        - Volume >= 2x avg 20 bar
        - Close > MA (resistance proxy)
        - Close >= MA * 1.03 (margin 3%)
        """
        if snap.ma5 <= 0:
            return None

        vol_surge = snap.volume >= avg_vol * 2
        above_ma = snap.close > snap.ma5
        margin_3pct = snap.close >= snap.ma5 * 1.03

        if vol_surge and above_ma and margin_3pct:
            pct_above = ((snap.close - snap.ma5) / snap.ma5) * 100
            strength = min(100, int(50 + pct_above * 5 + (snap.volume_surge_ratio - 2) * 10))
            return PatternDetected(
                name="Breakout + Volume",
                description=f"Close {pct_above:.1f}% di atas MA5, Volume {snap.volume_surge_ratio:.1f}x",
                strength=strength,
            )
        return None

    # ── Pattern 2: Breakaway Gap ────────────────────

    def _detect_gap(self, snap, highs, lows, volumes, avg_vol):
        """
        Breakaway Gap
        - Low saat ini > High bar sebelumnya (gap up)
        - Volume > rata-rata
        """
        if len(highs) < 2:
            return None

        prev_high = highs[-2]
        curr_low = snap.low if snap.low > 0 else lows[-1]
        gap = curr_low > prev_high
        vol_ok = snap.volume > avg_vol

        if gap and vol_ok and prev_high > 0:
            gap_pct = ((curr_low - prev_high) / prev_high) * 100
            strength = min(100, int(60 + gap_pct * 10 + (snap.volume_surge_ratio - 1) * 10))
            return PatternDetected(
                name="Breakaway Gap",
                description=f"Gap Up {gap_pct:.1f}%, Volume {snap.volume_surge_ratio:.1f}x",
                strength=strength,
            )
        return None

    # ── Pattern 3: Flags & Pennants ─────────────────

    def _detect_flag(self, closes, volumes, avg_vol):
        """
        Flags & Pennants
        - Pole: kenaikan > 5% dalam 5 bar terakhir
        - Consolidation: volume menyusut di 3 bar terakhir
        - Breakout: close terakhir > high konsolidasi + volume naik
        """
        if len(closes) < 10:
            return None

        # Check pole (bar -10 to -5): kenaikan tajam
        pole_start = closes[-10]
        pole_end = closes[-5]
        if pole_start <= 0:
            return None
        pole_gain = ((pole_end - pole_start) / pole_start) * 100

        if pole_gain < 5:
            return None

        # Check consolidation (bar -5 to -2): volume menyusut
        consol_vols = volumes[-5:-1]
        if not consol_vols:
            return None
        avg_consol_vol = sum(consol_vols) / len(consol_vols)
        vol_shrink = avg_consol_vol < avg_vol * 0.8

        # Check breakout: current close > max of consolidation
        consol_high = max(closes[-5:-1])
        breakout = closes[-1] > consol_high
        vol_surge = volumes[-1] > avg_vol

        if vol_shrink and breakout and vol_surge:
            strength = min(100, int(55 + pole_gain * 2))
            return PatternDetected(
                name="Flag/Pennant Breakout",
                description=f"Pole +{pole_gain:.0f}%, konsolidasi selesai, breakout!",
                strength=strength,
            )
        return None

    # ── Pattern 4: Runaway Days / Spikes ────────────

    def _detect_runaway(self, snap, highs, lows, opens, closes, volumes, avg_vol):
        """
        Runaway Days / Spikes
        - Range (H-L) > 2x avg range 10 bar
        - Open dekat Low (buka dari bawah)
        - Close dekat High (tutup di puncak)
        - Volume > avg
        """
        if len(highs) < 11:
            return None

        # Avg range 10 bar
        ranges = [highs[i] - lows[i] for i in range(-11, -1)]
        avg_range = sum(ranges) / len(ranges) if ranges else 0
        if avg_range <= 0:
            return None

        curr_range = snap.high - snap.low if snap.high > 0 and snap.low > 0 else 0
        range_ratio = curr_range / avg_range if avg_range > 0 else 0

        # Open near low (within 1%)
        price_1pct = snap.close * 0.01
        open_near_low = (snap.open - snap.low) <= price_1pct if snap.low > 0 else False

        # Close near high (within 1%)
        close_near_high = (snap.high - snap.close) <= price_1pct if snap.high > 0 else False

        vol_ok = snap.volume > avg_vol

        if range_ratio >= 2 and open_near_low and close_near_high and vol_ok:
            strength = min(100, int(60 + range_ratio * 10))
            return PatternDetected(
                name="Runaway Day",
                description=f"Range {range_ratio:.1f}x normal, buka di Low tutup di High!",
                strength=strength,
            )
        return None

    # ── Core checks ─────────────────────────────────

    def _check_volume(self, snap, avg_vol):
        ratio = snap.volume_surge_ratio
        passed = ratio >= 2.0
        if ratio >= 5: st = 100
        elif ratio >= 2: st = int(50 + (ratio - 2) / 3 * 50)
        else: st = int(ratio / 2 * 50)
        return SignalDetail("Volume", passed, ratio, 2.0,
            f"{ratio:.1f}x avg", min(100, st), "")

    def _check_price_strength(self, snap):
        md = config.screener.max_drop_from_high_pct
        if snap.high <= 0:
            return SignalDetail("Price", False, 0, md, "N/A", 0, "")
        drop = ((snap.high - snap.close) / snap.high) * 100
        snap.drop_from_high_pct = drop
        passed = drop <= md
        st = 100 if drop <= 0 else (int(100 - drop/md*50) if drop <= md else max(0, int(50-(drop-md)*10)))
        return SignalDetail("Price", passed, drop, md, f"{drop:.1f}% dari high", st, "")

    def _check_ma(self, snap):
        if snap.ma3 <= 0 or snap.ma5 <= 0:
            return SignalDetail("MA", False, 0, 0, "N/A", 0, "")
        bull = snap.ma3 >= snap.ma5
        above = snap.close >= snap.ma5
        passed = bull and above
        st = 80 if passed else 30
        return SignalDetail("MA", passed, 0, 0,
            f"MA3={snap.ma3:,.0f} MA5={snap.ma5:,.0f}", st, "")

    # ── Helpers ─────────────────────────────────────

    def _ma(self, prices, period):
        if len(prices) < period: return 0.0
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
        if ticker not in self.alert_history: return False
        return datetime.now() - self.alert_history[ticker] < timedelta(minutes=config.screener.alert_cooldown_minutes)

    def _build_reasons(self, snap, patterns, inds):
        r = []
        for p in patterns:
            r.append(f"{p.name}: {p.description}")
        if snap.change_pct > 0:
            r.append(f"Naik {snap.change_pct:+.1f}% hari ini")
        if inds:
            if inds.rsi: r.append(inds.rsi.description)
            if inds.macd and (inds.macd.is_bullish_cross or inds.macd.histogram > 0):
                r.append(inds.macd.description)
            if inds.bollinger and inds.bollinger.is_squeeze:
                r.append(inds.bollinger.description)
            r.append(f"Konfluensi: {inds.bullish_count}/{inds.total_indicators} bullish")
        return r
''')
print("  [OK] screener.py (4 pola baru)")

# ═══════════════════════════════════════
# telegram_bot.py — AESTHETIC DISPLAY
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

WIB = timezone(timedelta(hours=7))

def now_wib():
    return datetime.now(WIB)

def is_market_hours():
    now = now_wib()
    if now.weekday() >= 5: return False
    h, m = now.hour, now.minute
    s1 = (h == 9) or (h == 10) or (h == 11 and m <= 30)
    s2 = (h == 13 and m >= 30) or (h == 14) or (h == 15 and m == 0)
    return s1 or s2


PATTERN_EMOJI = {
    "Breakout + Volume": "\\U0001F4A5",   # 💥
    "Breakaway Gap": "\\u26A1",            # ⚡
    "Flag/Pennant Breakout": "\\U0001F3F4", # 🏴
    "Runaway Day": "\\U0001F680",          # 🚀
}


class AlertFormatter:

    @staticmethod
    def format_alert(a):
        s = a.snapshot
        chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"

        # ── Header ──
        msg = f"\\u2501" * 26 + "\\n"
        msg += f"\\U0001F6A8  STRONG BUY  \\u2022  {s.ticker}\\n"
        msg += f"\\u2501" * 26 + "\\n\\n"

        # ── Price block ──
        msg += f"Rp {s.close:,.0f}  ({chg}%)\\n"
        msg += f"Vol {s.volume:,}  \\u2022  {s.volume_surge_ratio:.1f}x avg\\n\\n"

        # ── Patterns ──
        if a.patterns:
            msg += "POLA TERDETEKSI\\n"
            for p in a.patterns:
                emoji = PATTERN_EMOJI.get(p.name, "\\u25C6")
                bar = "\\u2588" * (p.strength // 10) + "\\u2591" * (10 - p.strength // 10)
                msg += f"  {emoji}  {p.name}\\n"
                msg += f"       {p.description}\\n"
                msg += f"       {bar} {p.strength}\\n\\n"

        # ── Score ──
        score_bar = "\\u2588" * (a.overall_strength // 10) + "\\u2591" * (10 - a.overall_strength // 10)
        msg += f"SKOR  {score_bar}  {a.overall_strength}/100\\n"
        msg += f"Confidence: {a.confidence}\\n\\n"

        # ── OHLC ──
        msg += f"O {s.open:>10,.0f}    H {s.high:>10,.0f}\\n"
        msg += f"L {s.low:>10,.0f}    C {s.close:>10,.0f}\\n\\n"

        # ── Indicators ──
        ind = a.indicators
        if ind:
            parts = []
            if ind.rsi:
                parts.append(f"RSI {ind.rsi.value:.0f}")
            if ind.macd:
                parts.append(f"MACD {ind.macd.histogram:+.1f}")
            if ind.bollinger:
                parts.append(f"BB {ind.bollinger.percent_b:.2f}")
            if ind.stochastic:
                parts.append(f"Stoch {ind.stochastic.k:.0f}")
            if ind.vwap:
                v_dir = "\\u25B2" if ind.vwap.is_above else "\\u25BC"
                parts.append(f"VWAP {v_dir}")
            if parts:
                msg += " \\u2022 ".join(parts) + "\\n"
                msg += f"Bullish: {ind.bullish_count}/{ind.total_indicators}\\n\\n"

        # ── Reasons ──
        if a.reasons:
            for r in a.reasons:
                msg += f"  \\u25B8 {r}\\n"
            msg += "\\n"

        # ── Footer ──
        t = now_wib().strftime("%H:%M:%S")
        msg += f"\\u2500" * 26 + "\\n"
        msg += f"{t} WIB  \\u2022  DYOR, bukan rekomendasi."
        return msg

    @staticmethod
    def format_summary(alerts, total):
        t = now_wib().strftime("%H:%M:%S")
        mkt = "\\U0001F7E2" if is_market_hours() else "\\U0001F534"

        msg = f"{mkt}  Scan  \\u2022  {t} WIB\\n"
        msg += f"Scanned {total} saham\\n\\n"

        if not alerts:
            msg += "Belum ada sinyal. Bot terus memantau."
            return msg

        msg += f"Ditemukan {len(alerts)} sinyal:\\n\\n"
        for i, a in enumerate(alerts, 1):
            s = a.snapshot
            chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"
            patterns = ", ".join(p.name for p in a.patterns)
            msg += f"{i}. {s.ticker}  Rp {s.close:,.0f}  ({chg}%)\\n"
            msg += f"   Vol {s.volume_surge_ratio:.1f}x  \\u2022  Skor {a.overall_strength}  \\u2022  {patterns}\\n\\n"

        msg += "/detail TICKER untuk analisis lengkap"
        return msg

    @staticmethod
    def format_detail(alert):
        """Same as format_alert but always shown (even if not strong buy)"""
        if alert.is_strong_buy:
            return AlertFormatter.format_alert(alert)

        s = alert.snapshot
        chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"

        msg = f"\\U0001F50D  {s.ticker}  \\u2022  Rp {s.close:,.0f}  ({chg}%)\\n"
        msg += f"\\u2500" * 26 + "\\n\\n"
        msg += f"Vol: {s.volume:,}  ({s.volume_surge_ratio:.1f}x avg)\\n"
        msg += f"High: {s.high:,.0f}  \\u2022  Drop: {s.drop_from_high_pct:.1f}%\\n"
        msg += f"MA3: {s.ma3:,.0f}  \\u2022  MA5: {s.ma5:,.0f}\\n\\n"

        if alert.patterns:
            msg += "Pola terdeteksi:\\n"
            for p in alert.patterns:
                msg += f"  \\u25B8 {p.name}: {p.description}\\n"
        else:
            msg += "Tidak ada pola terdeteksi.\\n"

        # Volume check
        vs = alert.volume_signal
        if vs:
            status = "\\u2713" if vs.passed else "\\u2717"
            msg += f"\\nVolume: {status} {vs.description}\\n"

        ind = alert.indicators
        if ind:
            msg += "\\nIndikator:\\n"
            if ind.rsi: msg += f"  RSI: {ind.rsi.value:.1f} ({ind.rsi.signal})\\n"
            if ind.macd: msg += f"  MACD: {ind.macd.histogram:+.1f} ({ind.macd.signal})\\n"
            if ind.bollinger: msg += f"  BB %B: {ind.bollinger.percent_b:.2f}\\n"
            msg += f"  Bullish: {ind.bullish_count}/{ind.total_indicators}\\n"

        msg += f"\\nStatus: {'STRONG BUY' if alert.is_strong_buy else 'Belum memenuhi kriteria'}"
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
            await update.message.reply_text("Bot sudah berjalan.")
            return
        self.is_scanning = True

        t = now_wib().strftime("%H:%M")
        mkt = "Buka" if is_market_hours() else "Tutup"
        src = self.screener.fetcher.source_name
        n = len(config.datasource.watchlist)
        wl = config.datasource.watchlist

        msg = f"\\U0001F4C8  IHSG Alert Bot\\n"
        msg += f"\\u2500" * 26 + "\\n\\n"
        msg += f"\\u23F0  {t} WIB  \\u2022  Pasar {mkt}\\n"
        msg += f"\\U0001F4E1  {src}\\n"
        msg += f"\\U0001F4CA  {n} saham  \\u2022  Interval {config.datasource.scan_interval_seconds}s\\n\\n"

        # Watchlist compact
        msg += "Watchlist\\n"
        for i in range(0, len(wl), 8):
            msg += "  " + "  ".join(wl[i:i+8]) + "\\n"

        # Screener info
        msg += f"\\nPola yang dipantau:\\n"
        msg += f"  \\U0001F4A5  Breakout + Volume (aturan 3%)\\n"
        msg += f"  \\u26A1  Breakaway Gap\\n"
        msg += f"  \\U0001F3F4  Flag/Pennant Breakout\\n"
        msg += f"  \\U0001F680  Runaway Day / Spike\\n"

        msg += f"\\nFilter: Vol \\u2265 2x  \\u2022  Drop \\u2264 {config.screener.max_drop_from_high_pct}%\\n"
        msg += f"MA: {config.screener.ma_short}/{config.screener.ma_medium}  \\u2022  "
        msg += f"RSI \\u2022 MACD \\u2022 BB \\u2022 Stoch \\u2022 VWAP\\n\\n"

        msg += "/scan  /detail BBCA  /watchlist\\n"
        msg += "/add TICKER  /remove TICKER  /stop"

        await update.message.reply_text(msg)
        self._task = asyncio.create_task(self._loop(update.effective_chat.id, ctx))

    async def cmd_stop(self, update: Update, ctx):
        self.is_scanning = False
        if self._task: self._task.cancel()
        await update.message.reply_text("\\U0001F6D1  Bot stopped.")

    async def cmd_scan(self, update: Update, ctx):
        t = now_wib().strftime("%H:%M:%S")
        await update.message.reply_text(f"\\U0001F50D  Scanning... ({t} WIB)")
        alerts = self.screener.scan_all(config.datasource.watchlist)
        await update.message.reply_text(
            AlertFormatter.format_summary(alerts, len(config.datasource.watchlist))
        )
        for a in alerts[:5]:
            await update.message.reply_text(AlertFormatter.format_alert(a))
            await asyncio.sleep(0.5)

    async def cmd_status(self, update: Update, ctx):
        st = "Running" if self.is_scanning else "Stopped"
        t = now_wib().strftime("%H:%M")
        mkt = "Buka" if is_market_hours() else "Tutup"
        msg = f"Status: {st}  \\u2022  {t} WIB  \\u2022  Pasar {mkt}\\n"
        msg += f"Source: {self.screener.fetcher.source_name}\\n"
        msg += f"Watchlist: {len(config.datasource.watchlist)} saham\\n\\n"
        msg += "/start  /stop  /scan  /detail  /watchlist"
        await update.message.reply_text(msg)

    async def cmd_detail(self, update: Update, ctx):
        if not ctx.args:
            await update.message.reply_text("Ketik: /detail BBCA")
            return
        t = ctx.args[0].upper()
        await update.message.reply_text(f"Analyzing {t}...")
        snap = self.screener.fetcher.fetch_snapshot(t)
        if not snap:
            await update.message.reply_text(f"Gagal fetch {t}")
            return
        alert = self.screener.analyze(snap)
        if not alert:
            await update.message.reply_text(f"Data tidak cukup untuk {t}")
            return
        await update.message.reply_text(AlertFormatter.format_detail(alert))

    async def cmd_wl(self, update: Update, ctx):
        wl = config.datasource.watchlist
        msg = f"\\U0001F4CB  Watchlist ({len(wl)})\\n\\n"
        for i in range(0, len(wl), 6):
            msg += "  ".join(wl[i:i+6]) + "\\n"
        msg += "\\n/add TICKER  \\u2022  /remove TICKER"
        await update.message.reply_text(msg)

    async def cmd_add(self, update: Update, ctx):
        if not ctx.args: return
        t = ctx.args[0].upper()
        if t not in config.datasource.watchlist:
            config.datasource.watchlist.append(t)
        await update.message.reply_text(f"\\u2713  {t} ditambahkan ({len(config.datasource.watchlist)} saham)")

    async def cmd_rm(self, update: Update, ctx):
        if not ctx.args: return
        t = ctx.args[0].upper()
        if t in config.datasource.watchlist:
            config.datasource.watchlist.remove(t)
        await update.message.reply_text(f"\\u2713  {t} dihapus ({len(config.datasource.watchlist)} saham)")

    async def _loop(self, cid, ctx):
        logger.info("Scan loop started")
        while self.is_scanning:
            try:
                if not is_market_hours():
                    await asyncio.sleep(300)
                    continue
                alerts = self.screener.scan_all(config.datasource.watchlist)
                for a in alerts[:3]:
                    try:
                        await ctx.bot.send_message(chat_id=cid, text=AlertFormatter.format_alert(a))
                    except Exception as e:
                        logger.error(f"Send error: {e}")
                    await asyncio.sleep(1)
                await asyncio.sleep(config.datasource.scan_interval_seconds)
            except asyncio.CancelledError: break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(10)
        logger.info("Scan loop stopped")

    def run(self):
        logger.info("Starting bot...")
        self.app.run_polling(drop_pending_updates=True)
''')
print("  [OK] telegram_bot.py (aesthetic display)")

print()
print("  ==========================================")
print("  UPGRADE v3 COMPLETE!")
print("  ==========================================")
print()
print("  Formula baru (4 pola):")
print("    1. Breakout + Volume Explosion (aturan 3%)")
print("    2. Breakaway Gap")
print("    3. Flag/Pennant Breakout")
print("    4. Runaway Day / Spike")
print()
print("  Tampilan: aesthetic, clean, emoji tasteful")
print()
print("  Jalankan:  python main.py")
print()
