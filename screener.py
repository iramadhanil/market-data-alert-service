import logging
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
                name="Volume Breakout", emoji="\U0001F4A5",
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
                name="Flag Breakout", emoji="\U0001F3F4",
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
                name=f"RSI-{period} Bounce", emoji="\U0001F4C8",
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
                    name="Breakaway Gap", emoji="\u26A1",
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
                name="Runaway Bar", emoji="\U0001F680",
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
