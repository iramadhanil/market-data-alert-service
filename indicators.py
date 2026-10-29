from dataclasses import dataclass
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
