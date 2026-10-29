"""
IHSG Alert Bot - UPGRADE v4 (FINAL)
=====================================
- Hapus watchlist commands → Top Gainer/Loser
- Alert otomatis real-time (push notification)
- Detail lengkap per pola terdeteksi
- Siap deploy ke VPS

Jalankan: python upgrade_v4.py
"""
import os
DIR = r"C:\ihsg-bot"
print("\n  Upgrading to v4 (final)...\n")

# ═══════════════════════════════════════
# screener.py — DETAILED PATTERN OUTPUT
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
    name: str
    emoji: str
    description: str
    strength: int = 0
    details: Dict = field(default_factory=dict)

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

    def fetch_market_movers(self, tickers):
        """Fetch all stocks and return sorted by change%"""
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

        vol_window = volumes[-21:-1] if len(volumes) > 21 else volumes[:-1]
        avg_vol = int(sum(vol_window) / len(vol_window)) if vol_window else 1
        if avg_vol <= 0: avg_vol = 1
        snap.avg_volume_20d = avg_vol
        snap.volume_surge_ratio = snap.volume / avg_vol

        patterns = []
        p1 = self._detect_breakout_volume(snap, closes, volumes, avg_vol)
        if p1: patterns.append(p1)
        p2 = self._detect_gap(snap, highs, lows, volumes, avg_vol)
        if p2: patterns.append(p2)
        p3 = self._detect_flag(closes, volumes, avg_vol)
        if p3: patterns.append(p3)
        p4 = self._detect_runaway(snap, highs, lows, opens, closes, volumes, avg_vol)
        if p4: patterns.append(p4)

        vol_signal = self._check_volume(snap, avg_vol)
        price_signal = self._check_price_strength(snap)
        ma_signal = self._check_ma(snap)
        inds = TechnicalIndicators.calc_all(closes, highs, lows, volumes)

        alert = AlertSignal(
            ticker=snap.ticker, timestamp=datetime.now(), snapshot=snap,
            volume_signal=vol_signal, price_strength_signal=price_signal,
            ma_signal=ma_signal, patterns=patterns, indicators=inds,
        )

        if len(patterns) > 0 and vol_signal.passed:
            alert.is_strong_buy = True
            pattern_str = max(p.strength for p in patterns)
            base = int(pattern_str * 0.45 + vol_signal.strength * 0.35 + price_signal.strength * 0.20)
            bonus = 0
            if inds: bonus = int(inds.bullish_count * config.indicators.confluence_weight * 100)
            bonus += (len(patterns) - 1) * 5
            alert.overall_strength = min(100, base + bonus)
            if alert.overall_strength >= 80: alert.confidence = "VERY HIGH"
            elif alert.overall_strength >= 65: alert.confidence = "HIGH"
            elif alert.overall_strength >= 50: alert.confidence = "MEDIUM"
            else: alert.confidence = "MODERATE"
            alert.reasons = self._build_reasons(snap, patterns, inds)
        return alert

    def _detect_breakout_volume(self, snap, closes, volumes, avg_vol):
        if snap.ma5 <= 0: return None
        vol_surge = snap.volume >= avg_vol * 2
        above_ma = snap.close > snap.ma5
        margin_3pct = snap.close >= snap.ma5 * 1.03
        if vol_surge and above_ma and margin_3pct:
            pct_above = ((snap.close - snap.ma5) / snap.ma5) * 100
            strength = min(100, int(50 + pct_above * 5 + (snap.volume_surge_ratio - 2) * 10))
            return PatternDetected(
                name="Breakout + Volume", emoji="\\U0001F4A5",
                description=f"Close {pct_above:.1f}% di atas MA5, Volume {snap.volume_surge_ratio:.1f}x",
                strength=strength,
                details={
                    "close": snap.close, "ma5": snap.ma5,
                    "pct_above_ma": round(pct_above, 2),
                    "volume": snap.volume, "avg_volume": avg_vol,
                    "vol_ratio": round(snap.volume_surge_ratio, 2),
                    "rule": "Close >= MA5 x 1.03 AND Vol >= 2x avg",
                },
            )
        return None

    def _detect_gap(self, snap, highs, lows, volumes, avg_vol):
        if len(highs) < 2: return None
        prev_high = highs[-2]
        curr_low = snap.low if snap.low > 0 else lows[-1]
        gap = curr_low > prev_high
        vol_ok = snap.volume > avg_vol
        if gap and vol_ok and prev_high > 0:
            gap_pct = ((curr_low - prev_high) / prev_high) * 100
            gap_size = curr_low - prev_high
            strength = min(100, int(60 + gap_pct * 10 + (snap.volume_surge_ratio - 1) * 10))
            return PatternDetected(
                name="Breakaway Gap", emoji="\\u26A1",
                description=f"Gap Up {gap_pct:.1f}%, Volume {snap.volume_surge_ratio:.1f}x",
                strength=strength,
                details={
                    "prev_high": prev_high, "curr_low": curr_low,
                    "gap_size_rp": round(gap_size), "gap_pct": round(gap_pct, 2),
                    "volume": snap.volume, "avg_volume": avg_vol,
                    "vol_ratio": round(snap.volume_surge_ratio, 2),
                    "rule": "Low > prev High AND Vol > avg",
                },
            )
        return None

    def _detect_flag(self, closes, volumes, avg_vol):
        if len(closes) < 10: return None
        pole_start = closes[-10]; pole_end = closes[-5]
        if pole_start <= 0: return None
        pole_gain = ((pole_end - pole_start) / pole_start) * 100
        if pole_gain < 5: return None
        consol_vols = volumes[-5:-1]
        if not consol_vols: return None
        avg_consol = sum(consol_vols) / len(consol_vols)
        vol_shrink = avg_consol < avg_vol * 0.8
        consol_high = max(closes[-5:-1])
        breakout = closes[-1] > consol_high
        vol_surge = volumes[-1] > avg_vol
        if vol_shrink and breakout and vol_surge:
            strength = min(100, int(55 + pole_gain * 2))
            return PatternDetected(
                name="Flag/Pennant Breakout", emoji="\\U0001F3F4",
                description=f"Pole +{pole_gain:.0f}%, konsolidasi selesai, breakout!",
                strength=strength,
                details={
                    "pole_start": pole_start, "pole_end": pole_end,
                    "pole_gain_pct": round(pole_gain, 1),
                    "consol_avg_vol": int(avg_consol), "avg_vol_20d": avg_vol,
                    "vol_shrink_pct": round((1 - avg_consol/avg_vol) * 100, 1),
                    "breakout_price": closes[-1], "consol_high": consol_high,
                    "breakout_vol": volumes[-1],
                    "rule": "Pole>5%, vol shrink, breakout above consol high",
                },
            )
        return None

    def _detect_runaway(self, snap, highs, lows, opens, closes, volumes, avg_vol):
        if len(highs) < 11: return None
        ranges = [highs[i] - lows[i] for i in range(-11, -1)]
        avg_range = sum(ranges) / len(ranges) if ranges else 0
        if avg_range <= 0: return None
        curr_range = snap.high - snap.low if snap.high > 0 and snap.low > 0 else 0
        range_ratio = curr_range / avg_range if avg_range > 0 else 0
        price_1pct = snap.close * 0.01
        open_near_low = (snap.open - snap.low) <= price_1pct if snap.low > 0 else False
        close_near_high = (snap.high - snap.close) <= price_1pct if snap.high > 0 else False
        vol_ok = snap.volume > avg_vol
        if range_ratio >= 2 and open_near_low and close_near_high and vol_ok:
            strength = min(100, int(60 + range_ratio * 10))
            return PatternDetected(
                name="Runaway Day", emoji="\\U0001F680",
                description=f"Range {range_ratio:.1f}x normal, buka di Low tutup di High!",
                strength=strength,
                details={
                    "open": snap.open, "high": snap.high,
                    "low": snap.low, "close": snap.close,
                    "curr_range": round(curr_range), "avg_range": round(avg_range),
                    "range_ratio": round(range_ratio, 2),
                    "open_to_low": round(snap.open - snap.low),
                    "high_to_close": round(snap.high - snap.close),
                    "volume": snap.volume, "avg_volume": avg_vol,
                    "rule": "Range>2x avg, Open=Low, Close=High, Vol>avg",
                },
            )
        return None

    def _check_volume(self, snap, avg_vol):
        ratio = snap.volume_surge_ratio; passed = ratio >= 2.0
        if ratio >= 5: st = 100
        elif ratio >= 2: st = int(50 + (ratio - 2) / 3 * 50)
        else: st = int(ratio / 2 * 50)
        return SignalDetail("Volume", passed, ratio, 2.0, f"{ratio:.1f}x avg", min(100, st))

    def _check_price_strength(self, snap):
        md = config.screener.max_drop_from_high_pct
        if snap.high <= 0: return SignalDetail("Price", False, 0, md, "N/A", 0)
        drop = ((snap.high - snap.close) / snap.high) * 100
        snap.drop_from_high_pct = drop; passed = drop <= md
        st = 100 if drop <= 0 else (int(100 - drop/md*50) if drop <= md else max(0, int(50-(drop-md)*10)))
        return SignalDetail("Price", passed, drop, md, f"{drop:.1f}% dari high", st)

    def _check_ma(self, snap):
        if snap.ma3 <= 0 or snap.ma5 <= 0: return SignalDetail("MA", False, 0, 0, "N/A", 0)
        bull = snap.ma3 >= snap.ma5; above = snap.close >= snap.ma5
        return SignalDetail("MA", bull and above, 0, 0, f"MA3={snap.ma3:,.0f} MA5={snap.ma5:,.0f}", 80 if bull and above else 30)

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
        for p in patterns: r.append(f"{p.name}: {p.description}")
        if snap.change_pct > 0: r.append(f"Naik {snap.change_pct:+.1f}% hari ini")
        if inds:
            if inds.rsi: r.append(inds.rsi.description)
            if inds.macd and (inds.macd.is_bullish_cross or inds.macd.histogram > 0):
                r.append(inds.macd.description)
            if inds.bollinger and inds.bollinger.is_squeeze:
                r.append(inds.bollinger.description)
            r.append(f"Konfluensi: {inds.bullish_count}/{inds.total_indicators} bullish")
        return r
''')
print("  [OK] screener.py")

# ═══════════════════════════════════════
# telegram_bot.py — TOP GAINER/LOSER + DETAILED ALERTS
# ═══════════════════════════════════════
with open(os.path.join(DIR, "telegram_bot.py"), "w", encoding="utf-8") as f:
    f.write('''import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import config
from screener import AlertSignal, ScreenerEngine

logger = logging.getLogger(__name__)
WIB = timezone(timedelta(hours=7))

def now_wib(): return datetime.now(WIB)

def is_market_hours():
    now = now_wib()
    if now.weekday() >= 5: return False
    h, m = now.hour, now.minute
    return (h==9) or (h==10) or (h==11 and m<=30) or (h==13 and m>=30) or (h==14) or (h==15 and m==0)

def fmt_rp(v):
    if v >= 1_000_000_000: return f"{v/1_000_000_000:.1f}B"
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000: return f"{v/1_000:.0f}K"
    return f"{v:,.0f}"


class AlertFormatter:

    @staticmethod
    def format_alert(a):
        s = a.snapshot
        chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"

        msg = "\\u2501" * 28 + "\\n"
        msg += f"\\U0001F6A8  STRONG BUY  \\u2502  {s.ticker}\\n"
        msg += "\\u2501" * 28 + "\\n\\n"

        msg += f"Rp {s.close:,.0f}  ({chg}%)\\n"
        msg += f"Vol {fmt_rp(s.volume)}  \\u2502  {s.volume_surge_ratio:.1f}x avg\\n\\n"

        # ── Patterns with FULL details ──
        for p in a.patterns:
            bar = "\\u2588" * (p.strength // 10) + "\\u2591" * (10 - p.strength // 10)
            msg += f"{p.emoji}  {p.name}  {bar} {p.strength}\\n"
            msg += f"   {p.description}\\n"

            # Detailed breakdown
            d = p.details
            if p.name == "Breakout + Volume":
                msg += f"   \\u251C Close: Rp {d.get('close',0):,.0f}\\n"
                msg += f"   \\u251C MA5:   Rp {d.get('ma5',0):,.0f}\\n"
                msg += f"   \\u251C Di atas MA: {d.get('pct_above_ma',0)}%\\n"
                msg += f"   \\u251C Volume: {fmt_rp(d.get('volume',0))}\\n"
                msg += f"   \\u251C Avg Vol: {fmt_rp(d.get('avg_volume',0))}\\n"
                msg += f"   \\u2514 Rasio: {d.get('vol_ratio',0)}x\\n"

            elif p.name == "Breakaway Gap":
                msg += f"   \\u251C High kemarin: Rp {d.get('prev_high',0):,.0f}\\n"
                msg += f"   \\u251C Low hari ini: Rp {d.get('curr_low',0):,.0f}\\n"
                msg += f"   \\u251C Gap: Rp {d.get('gap_size_rp',0):,} ({d.get('gap_pct',0)}%)\\n"
                msg += f"   \\u251C Volume: {fmt_rp(d.get('volume',0))}\\n"
                msg += f"   \\u2514 Rasio: {d.get('vol_ratio',0)}x\\n"

            elif p.name == "Flag/Pennant Breakout":
                msg += f"   \\u251C Pole: Rp {d.get('pole_start',0):,.0f} \\u2192 {d.get('pole_end',0):,.0f} (+{d.get('pole_gain_pct',0)}%)\\n"
                msg += f"   \\u251C Vol menyusut: {d.get('vol_shrink_pct',0)}% dari avg\\n"
                msg += f"   \\u251C Breakout: Rp {d.get('breakout_price',0):,.0f} > {d.get('consol_high',0):,.0f}\\n"
                msg += f"   \\u2514 Vol breakout: {fmt_rp(d.get('breakout_vol',0))}\\n"

            elif p.name == "Runaway Day":
                msg += f"   \\u251C Open: Rp {d.get('open',0):,.0f}  (Low +{d.get('open_to_low',0)})\\n"
                msg += f"   \\u251C High: Rp {d.get('high',0):,.0f}  (Close -{d.get('high_to_close',0)})\\n"
                msg += f"   \\u251C Range: Rp {d.get('curr_range',0):,} ({d.get('range_ratio',0)}x normal)\\n"
                msg += f"   \\u2514 Volume: {fmt_rp(d.get('volume',0))} ({d.get('volume',0)//d.get('avg_volume',1) if d.get('avg_volume',0)>0 else 0}x avg)\\n"

            msg += "\\n"

        # Score
        bar = "\\u2588" * (a.overall_strength // 10) + "\\u2591" * (10 - a.overall_strength // 10)
        msg += f"Skor  {bar}  {a.overall_strength}/100  ({a.confidence})\\n\\n"

        # OHLC compact
        msg += f"O {s.open:>10,.0f}   H {s.high:>10,.0f}\\n"
        msg += f"L {s.low:>10,.0f}   C {s.close:>10,.0f}\\n\\n"

        # Indicators
        ind = a.indicators
        if ind:
            parts = []
            if ind.rsi: parts.append(f"RSI {ind.rsi.value:.0f}")
            if ind.macd: parts.append(f"MACD {ind.macd.histogram:+.1f}")
            if ind.bollinger: parts.append(f"BB {ind.bollinger.percent_b:.2f}")
            if ind.stochastic: parts.append(f"Stoch {ind.stochastic.k:.0f}")
            if ind.vwap:
                parts.append(f"VWAP {'\\u25B2' if ind.vwap.is_above else '\\u25BC'}")
            if parts:
                msg += " \\u2502 ".join(parts) + "\\n"
                msg += f"Bullish: {ind.bullish_count}/{ind.total_indicators}\\n\\n"

        # Footer
        t = now_wib().strftime("%H:%M:%S")
        msg += "\\u2500" * 28 + "\\n"
        msg += f"{t} WIB  \\u2502  DYOR, bukan rekomendasi."
        return msg

    @staticmethod
    def format_summary(alerts, total):
        t = now_wib().strftime("%H:%M:%S")
        dot = "\\U0001F7E2" if is_market_hours() else "\\U0001F534"
        msg = f"{dot}  Scan  \\u2502  {t} WIB\\n"
        msg += f"Scanned {total} saham\\n\\n"
        if not alerts:
            msg += "Belum ada sinyal. Bot terus memantau."
            return msg
        msg += f"\\U0001F6A8 {len(alerts)} sinyal ditemukan:\\n\\n"
        for i, a in enumerate(alerts, 1):
            s = a.snapshot
            chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"
            pats = " ".join(p.emoji for p in a.patterns)
            msg += f"{i}. {s.ticker}  Rp {s.close:,.0f}  ({chg}%)\\n"
            msg += f"   {pats}  Vol {s.volume_surge_ratio:.1f}x  Skor {a.overall_strength}\\n\\n"
        msg += "/detail TICKER untuk analisis lengkap"
        return msg

    @staticmethod
    def format_movers(gainers, losers, count=10):
        t = now_wib().strftime("%H:%M")
        msg = f"\\U0001F4CA  Market Movers  \\u2502  {t} WIB\\n"
        msg += "\\u2500" * 28 + "\\n\\n"

        msg += "\\U0001F7E2  TOP GAINER\\n"
        for i, s in enumerate(gainers[:count], 1):
            msg += f"  {i:>2}. {s.ticker:<5} Rp {s.close:>8,.0f}  +{s.change_pct:.1f}%  Vol {fmt_rp(s.volume)}\\n"

        msg += f"\\n\\U0001F534  TOP LOSER\\n"
        for i, s in enumerate(losers[:count], 1):
            msg += f"  {i:>2}. {s.ticker:<5} Rp {s.close:>8,.0f}  {s.change_pct:.1f}%  Vol {fmt_rp(s.volume)}\\n"

        msg += f"\\n/detail TICKER untuk analisis"
        return msg

    @staticmethod
    def format_detail(alert):
        if alert.is_strong_buy:
            return AlertFormatter.format_alert(alert)
        s = alert.snapshot
        chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"
        msg = f"\\U0001F50D  {s.ticker}  Rp {s.close:,.0f}  ({chg}%)\\n"
        msg += "\\u2500" * 28 + "\\n\\n"
        msg += f"Volume: {s.volume:,} ({s.volume_surge_ratio:.1f}x avg)\\n"
        msg += f"Drop dari High: {s.drop_from_high_pct:.1f}%\\n"
        msg += f"MA3: {s.ma3:,.0f}  MA5: {s.ma5:,.0f}\\n\\n"
        if alert.patterns:
            msg += "Pola terdeteksi:\\n"
            for p in alert.patterns:
                msg += f"  {p.emoji} {p.name}: {p.description}\\n"
                for k, v in p.details.items():
                    if k != "rule":
                        msg += f"     {k}: {v}\\n"
        else:
            msg += "Tidak ada pola terdeteksi.\\n"
            msg += "Syarat: Vol>=2x + salah satu pola (Breakout/Gap/Flag/Runaway)\\n"
        vs = alert.volume_signal
        if vs: msg += f"\\nVolume: {'\\u2713' if vs.passed else '\\u2717'} {vs.description}\\n"
        ind = alert.indicators
        if ind:
            msg += "\\nIndikator:\\n"
            if ind.rsi: msg += f"  RSI: {ind.rsi.value:.1f} ({ind.rsi.signal})\\n"
            if ind.macd: msg += f"  MACD: {ind.macd.histogram:+.1f} ({ind.macd.signal})\\n"
            if ind.bollinger: msg += f"  BB %B: {ind.bollinger.percent_b:.2f}\\n"
            msg += f"  Bullish: {ind.bullish_count}/{ind.total_indicators}\\n"
        msg += f"\\nStatus: {'\\U0001F6A8 STRONG BUY' if alert.is_strong_buy else 'Belum memenuhi kriteria'}"
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
            ("detail", self.cmd_detail),
            ("topgainer", self.cmd_movers), ("toploser", self.cmd_movers),
            ("movers", self.cmd_movers),
            ("help", self.cmd_help),
        ]:
            self.app.add_handler(CommandHandler(cmd, fn))

    async def cmd_start(self, update: Update, ctx):
        if self.is_scanning:
            await update.message.reply_text("Bot sudah berjalan."); return
        self.is_scanning = True
        t = now_wib().strftime("%H:%M")
        mkt = "Buka" if is_market_hours() else "Tutup"
        src = self.screener.fetcher.source_name
        n = len(config.datasource.watchlist)

        msg = f"\\U0001F4C8  IHSG Alert Bot\\n"
        msg += "\\u2500" * 28 + "\\n\\n"
        msg += f"\\u23F0  {t} WIB  \\u2502  Pasar {mkt}\\n"
        msg += f"\\U0001F4E1  {src}\\n"
        msg += f"\\U0001F4CA  Monitoring {n} saham\\n\\n"
        msg += "Pola yang dipantau:\\n"
        msg += "  \\U0001F4A5  Breakout + Volume (aturan 3%)\\n"
        msg += "  \\u26A1  Breakaway Gap\\n"
        msg += "  \\U0001F3F4  Flag/Pennant Breakout\\n"
        msg += "  \\U0001F680  Runaway Day / Spike\\n\\n"
        msg += "Bot akan otomatis kirim alert saat\\nada saham yang masuk kriteria.\\n\\n"
        msg += "/scan  /detail BBCA  /movers  /stop"

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
            AlertFormatter.format_summary(alerts, len(config.datasource.watchlist)))
        for a in alerts[:5]:
            await update.message.reply_text(AlertFormatter.format_alert(a))
            await asyncio.sleep(0.5)

    async def cmd_movers(self, update: Update, ctx):
        await update.message.reply_text("\\U0001F4CA  Fetching market data...")
        gainers, losers = self.screener.fetch_market_movers(config.datasource.watchlist)
        msg = AlertFormatter.format_movers(gainers, losers)
        await update.message.reply_text(msg)

    async def cmd_status(self, update: Update, ctx):
        st = "Running" if self.is_scanning else "Stopped"
        t = now_wib().strftime("%H:%M")
        mkt = "Buka" if is_market_hours() else "Tutup"
        msg = f"Status: {st}  \\u2502  {t} WIB  \\u2502  Pasar {mkt}\\n"
        msg += f"Source: {self.screener.fetcher.source_name}\\n"
        msg += f"Monitoring: {len(config.datasource.watchlist)} saham\\n\\n"
        msg += "/start /stop /scan /detail /movers"
        await update.message.reply_text(msg)

    async def cmd_detail(self, update: Update, ctx):
        if not ctx.args:
            await update.message.reply_text("Ketik: /detail BBCA"); return
        t = ctx.args[0].upper()
        await update.message.reply_text(f"Analyzing {t}...")
        snap = self.screener.fetcher.fetch_snapshot(t)
        if not snap: await update.message.reply_text(f"Gagal fetch {t}"); return
        alert = self.screener.analyze(snap)
        if not alert: await update.message.reply_text(f"Data tidak cukup untuk {t}"); return
        await update.message.reply_text(AlertFormatter.format_detail(alert))

    async def cmd_help(self, update: Update, ctx):
        msg = "\\U0001F4C8  IHSG Alert Bot\\n"
        msg += "\\u2500" * 28 + "\\n\\n"
        msg += "/start   Mulai monitoring\\n"
        msg += "/stop    Hentikan bot\\n"
        msg += "/scan    Scan manual\\n"
        msg += "/movers  Top Gainer & Loser\\n"
        msg += "/detail BBCA  Analisis 1 saham\\n"
        msg += "/status  Status bot\\n"
        msg += "/help    Bantuan"
        await update.message.reply_text(msg)

    async def _loop(self, cid, ctx):
        logger.info("Auto-scan loop started")
        scan_count = 0
        while self.is_scanning:
            try:
                if not is_market_hours():
                    await asyncio.sleep(300); continue

                scan_count += 1
                logger.info(f"Auto-scan #{scan_count}")
                alerts = self.screener.scan_all(config.datasource.watchlist)

                if alerts:
                    logger.info(f"\\U0001F6A8 {len(alerts)} signals found!")
                    # Send each alert as push notification
                    for a in alerts[:5]:
                        try:
                            await ctx.bot.send_message(
                                chat_id=cid,
                                text=AlertFormatter.format_alert(a))
                        except Exception as e:
                            logger.error(f"Send error: {e}")
                        await asyncio.sleep(1)
                else:
                    # Silent log, no spam to user
                    if scan_count % 60 == 0:  # Log every ~5 min
                        logger.info("No signals, still monitoring...")

                await asyncio.sleep(config.datasource.scan_interval_seconds)

            except asyncio.CancelledError: break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(10)

        logger.info("Auto-scan loop stopped")

    def run(self):
        logger.info("Starting bot...")
        self.app.run_polling(drop_pending_updates=True)
''')
print("  [OK] telegram_bot.py")

# ═══════════════════════════════════════
# deploy_vps.sh — VPS setup script
# ═══════════════════════════════════════
with open(os.path.join(DIR, "deploy_vps.sh"), "w", encoding="utf-8", newline="\n") as f:
    f.write('''#!/bin/bash
# ══════════════════════════════════════════
# IHSG Alert Bot - VPS Deployment Script
# Jalankan di VPS (Ubuntu/Debian):
#   bash deploy_vps.sh
# ══════════════════════════════════════════

set -e
echo ""
echo "  IHSG Alert Bot - VPS Setup"
echo "  =========================="
echo ""

# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Python
sudo apt install python3 python3-pip python3-venv -y

# 3. Create project directory
mkdir -p ~/ihsg-bot
cd ~/ihsg-bot

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install python-telegram-bot yfinance requests websocket-client pandas numpy python-dotenv

# 6. Prompt for .env
echo ""
echo "  Masukkan credentials:"
read -p "  Telegram Bot Token: " BOT_TOKEN
read -p "  Telegram Chat ID: " CHAT_ID
read -p "  iTick API Key: " ITICK_KEY

cat > .env << EOF
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
ITICK_API_KEY=${ITICK_KEY}
STOCKBIT_USERNAME=
STOCKBIT_PASSWORD=
EOF
echo "  [OK] .env created"

# 7. Copy Python files (should already be here)
echo ""
echo "  Pastikan file .py sudah ada di ~/ihsg-bot/"
echo "  (config.py, indicators.py, data_fetcher.py,"
echo "   screener.py, telegram_bot.py, main.py)"
echo ""

# 8. Create systemd service
sudo tee /etc/systemd/system/ihsg-bot.service << EOF
[Unit]
Description=IHSG Strong Buy Alert Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/ihsg-bot
ExecStart=$HOME/ihsg-bot/venv/bin/python main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 9. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable ihsg-bot
sudo systemctl start ihsg-bot

echo ""
echo "  =========================="
echo "  DEPLOY COMPLETE!"
echo "  =========================="
echo ""
echo "  Bot is running as a system service."
echo "  Commands:"
echo "    sudo systemctl status ihsg-bot    # Check status"
echo "    sudo systemctl restart ihsg-bot   # Restart"
echo "    sudo systemctl stop ihsg-bot      # Stop"
echo "    journalctl -u ihsg-bot -f         # View logs"
echo ""
echo "  Bot will auto-restart if it crashes,"
echo "  and auto-start when VPS reboots."
echo ""
''')
print("  [OK] deploy_vps.sh")

print(f"""
  ==========================================
  UPGRADE v4 COMPLETE!
  ==========================================

  Perubahan:
  1. Hapus /watchlist /add /remove
  2. Tambah /movers (Top Gainer & Loser)
  3. Alert detail: breakdown lengkap per pola
  4. Push notification otomatis saat jam pasar
  5. deploy_vps.sh siap untuk VPS

  ──────────────────────────────────────────
  TEST LOKAL:   python main.py
  ──────────────────────────────────────────

  DEPLOY KE VPS (lihat panduan di bawah):
  1. Beli VPS (Vultr/DigitalOcean/Hetzner)
  2. Upload semua file ke VPS
  3. Jalankan: bash deploy_vps.sh
  ──────────────────────────────────────────
""")
