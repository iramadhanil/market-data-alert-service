import asyncio
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

        msg = "\u2501" * 28 + "\n"
        msg += f"\U0001F6A8  SYARIAH ALERT  \u2502  {s.ticker}\n"
        msg += "\u2501" * 28 + "\n\n"

        msg += f"Rp {s.close:,.0f}  ({chg}%)\n"
        msg += f"Vol {fmt_rp(s.volume)}  \u2502  {s.volume_surge_ratio:.1f}x avg\n\n"

        # ── Patterns with FULL details ──
        for p in a.patterns:
            bar = "\u2588" * (p.strength // 10) + "\u2591" * (10 - p.strength // 10)
            msg += f"{p.emoji}  {p.name}  {bar} {p.strength}\n"
            msg += f"   {p.description}\n"

            # Detailed breakdown
            d = p.details
            if p.name == "Breakout + Volume":
                msg += f"   \u251C Close: Rp {d.get('close',0):,.0f}\n"
                msg += f"   \u251C MA5:   Rp {d.get('ma5',0):,.0f}\n"
                msg += f"   \u251C Di atas MA: {d.get('pct_above_ma',0)}%\n"
                msg += f"   \u251C Volume: {fmt_rp(d.get('volume',0))}\n"
                msg += f"   \u251C Avg Vol: {fmt_rp(d.get('avg_volume',0))}\n"
                msg += f"   \u2514 Rasio: {d.get('vol_ratio',0)}x\n"

            elif p.name == "Breakaway Gap":
                msg += f"   \u251C High kemarin: Rp {d.get('prev_high',0):,.0f}\n"
                msg += f"   \u251C Low hari ini: Rp {d.get('curr_low',0):,.0f}\n"
                msg += f"   \u251C Gap: Rp {d.get('gap_size_rp',0):,} ({d.get('gap_pct',0)}%)\n"
                msg += f"   \u251C Volume: {fmt_rp(d.get('volume',0))}\n"
                msg += f"   \u2514 Rasio: {d.get('vol_ratio',0)}x\n"

            elif p.name == "Flag/Pennant Breakout":
                msg += f"   \u251C Pole: Rp {d.get('pole_start',0):,.0f} \u2192 {d.get('pole_end',0):,.0f} (+{d.get('pole_gain_pct',0)}%)\n"
                msg += f"   \u251C Vol menyusut: {d.get('vol_shrink_pct',0)}% dari avg\n"
                msg += f"   \u251C Breakout: Rp {d.get('breakout_price',0):,.0f} > {d.get('consol_high',0):,.0f}\n"
                msg += f"   \u2514 Vol breakout: {fmt_rp(d.get('breakout_vol',0))}\n"

            elif p.name == "Runaway Day":
                msg += f"   \u251C Open: Rp {d.get('open',0):,.0f}  (Low +{d.get('open_to_low',0)})\n"
                msg += f"   \u251C High: Rp {d.get('high',0):,.0f}  (Close -{d.get('high_to_close',0)})\n"
                msg += f"   \u251C Range: Rp {d.get('curr_range',0):,} ({d.get('range_ratio',0)}x normal)\n"
                msg += f"   \u2514 Volume: {fmt_rp(d.get('volume',0))} ({d.get('volume',0)//d.get('avg_volume',1) if d.get('avg_volume',0)>0 else 0}x avg)\n"

            msg += "\n"

        # Score
        bar = "\u2588" * (a.overall_strength // 10) + "\u2591" * (10 - a.overall_strength // 10)
        msg += f"Skor  {bar}  {a.overall_strength}/100  ({a.confidence})\n\n"

        # OHLC compact
        msg += f"O {s.open:>10,.0f}   H {s.high:>10,.0f}\n"
        msg += f"L {s.low:>10,.0f}   C {s.close:>10,.0f}\n\n"

        # Indicators
        ind = a.indicators
        if ind:
            parts = []
            if ind.rsi: parts.append(f"RSI {ind.rsi.value:.0f}")
            if ind.macd: parts.append(f"MACD {ind.macd.histogram:+.1f}")
            if ind.bollinger: parts.append(f"BB {ind.bollinger.percent_b:.2f}")
            if ind.stochastic: parts.append(f"Stoch {ind.stochastic.k:.0f}")
            if ind.vwap:
                parts.append(f"VWAP {'\u25B2' if ind.vwap.is_above else '\u25BC'}")
            if parts:
                msg += " \u2502 ".join(parts) + "\n"
                msg += f"Bullish: {ind.bullish_count}/{ind.total_indicators}\n\n"

        # Footer
        t = now_wib().strftime("%H:%M:%S")
        msg += "\u2500" * 28 + "\n"
        msg += f"{t} WIB  \u2502  DYOR, bukan rekomendasi."
        return msg

    @staticmethod
    def format_summary(alerts, total):
        t = now_wib().strftime("%H:%M:%S")
        dot = "\U0001F7E2" if is_market_hours() else "\U0001F534"
        msg = f"{dot}  Scan  \u2502  {t} WIB\n"
        msg += f"Scanned {total} saham\n\n"
        if not alerts:
            msg += "Belum ada sinyal. Bot terus memantau."
            return msg
        msg += f"\U0001F6A8 {len(alerts)} sinyal ditemukan:\n\n"
        for i, a in enumerate(alerts, 1):
            s = a.snapshot
            chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"
            pats = " ".join(p.emoji for p in a.patterns)
            msg += f"{i}. {s.ticker}  Rp {s.close:,.0f}  ({chg}%)\n"
            msg += f"   {pats}  Vol {s.volume_surge_ratio:.1f}x  Skor {a.overall_strength}\n\n"
        msg += "/detail TICKER untuk analisis lengkap"
        return msg

    @staticmethod
    def format_movers(gainers, losers, count=10):
        t = now_wib().strftime("%H:%M")
        msg = f"\U0001F4CA  Market Movers  \u2502  {t} WIB\n"
        msg += "\u2500" * 28 + "\n\n"

        msg += "\U0001F7E2  TOP GAINER\n"
        for i, s in enumerate(gainers[:count], 1):
            msg += f"  {i:>2}. {s.ticker:<5} Rp {s.close:>8,.0f}  +{s.change_pct:.1f}%  Vol {fmt_rp(s.volume)}\n"

        msg += f"\n\U0001F534  TOP LOSER\n"
        for i, s in enumerate(losers[:count], 1):
            msg += f"  {i:>2}. {s.ticker:<5} Rp {s.close:>8,.0f}  {s.change_pct:.1f}%  Vol {fmt_rp(s.volume)}\n"

        msg += f"\n/detail TICKER untuk analisis"
        return msg

    @staticmethod
    def format_detail(alert):
        if alert.is_strong_buy:
            return AlertFormatter.format_alert(alert)
        s = alert.snapshot
        chg = f"+{s.change_pct:.1f}" if s.change_pct >= 0 else f"{s.change_pct:.1f}"
        msg = f"\U0001F50D  {s.ticker}  Rp {s.close:,.0f}  ({chg}%)\n"
        msg += "\u2500" * 28 + "\n\n"
        msg += f"Volume: {s.volume:,} ({s.volume_surge_ratio:.1f}x avg)\n"
        msg += f"Drop dari High: {s.drop_from_high_pct:.1f}%\n"
        msg += f"MA3: {s.ma3:,.0f}  MA5: {s.ma5:,.0f}\n\n"
        if alert.patterns:
            msg += "Pola terdeteksi:\n"
            for p in alert.patterns:
                msg += f"  {p.emoji} {p.name}: {p.description}\n"
                for k, v in p.details.items():
                    if k != "rule":
                        msg += f"     {k}: {v}\n"
        else:
            msg += "Tidak ada pola terdeteksi.\n"
            msg += "Syarat: Vol>=2x + salah satu pola (Breakout/Gap/Flag/Runaway)\n"
        vs = alert.volume_signal
        if vs: msg += f"\nVolume: {'\u2713' if vs.passed else '\u2717'} {vs.description}\n"
        ind = alert.indicators
        if ind:
            msg += "\nIndikator:\n"
            if ind.rsi: msg += f"  RSI: {ind.rsi.value:.1f} ({ind.rsi.signal})\n"
            if ind.macd: msg += f"  MACD: {ind.macd.histogram:+.1f} ({ind.macd.signal})\n"
            if ind.bollinger: msg += f"  BB %B: {ind.bollinger.percent_b:.2f}\n"
            msg += f"  Bullish: {ind.bullish_count}/{ind.total_indicators}\n"
        msg += f"\nStatus: {'\U0001F6A8 SYARIAH ALERT' if alert.is_strong_buy else 'Belum memenuhi kriteria'}"
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

        msg = f"\U0001F4C8  ISSI Syariah Screener\n"
        msg += "\u2500" * 28 + "\n\n"
        msg += f"\u23F0  {t} WIB  \u2502  Pasar {mkt}\n"
        msg += f"\U0001F4E1  {src}\n"
        msg += f"\U0001F4CA  Monitoring {n} saham\n\n"
        msg += "Pola yang dipantau:\n"
        msg += "  \U0001F4A5  Volume Breakout (aturan 3%)\n"
        msg += "  \u26A1  Breakaway Gap\n"
        msg += "  \U0001F3F4  Flag/Pennant Breakout\n"
        msg += "  \U0001F4C8  RSI-6 Bounce (oversold recovery)\n  \U0001F680  Runaway Bar / Spike\n\n"
        msg += "Bot akan otomatis kirim alert saat\nada saham yang masuk kriteria.\n\n"
        msg += "/scan  /detail BBCA  /movers  /stop"

        await update.message.reply_text(msg)
        self._task = asyncio.create_task(self._loop(update.effective_chat.id, ctx))

    async def cmd_stop(self, update: Update, ctx):
        self.is_scanning = False
        if self._task: self._task.cancel()
        await update.message.reply_text("\U0001F6D1  Bot stopped.")

    async def cmd_scan(self, update: Update, ctx):
        t = now_wib().strftime("%H:%M:%S")
        await update.message.reply_text(f"\U0001F50D  Scanning... ({t} WIB)")
        alerts = self.screener.scan_all(config.datasource.watchlist)
        await update.message.reply_text(
            AlertFormatter.format_summary(alerts, len(config.datasource.watchlist)))
        for a in alerts[:5]:
            await update.message.reply_text(AlertFormatter.format_alert(a))
            await asyncio.sleep(0.5)

    async def cmd_movers(self, update: Update, ctx):
        await update.message.reply_text("\U0001F4CA  Fetching market data...")
        gainers, losers = self.screener.fetch_market_movers(config.datasource.watchlist)
        msg = AlertFormatter.format_movers(gainers, losers)
        await update.message.reply_text(msg)

    async def cmd_status(self, update: Update, ctx):
        st = "Running" if self.is_scanning else "Stopped"
        t = now_wib().strftime("%H:%M")
        mkt = "Buka" if is_market_hours() else "Tutup"
        msg = f"Status: {st}  \u2502  {t} WIB  \u2502  Pasar {mkt}\n"
        msg += f"Source: {self.screener.fetcher.source_name}\n"
        msg += f"Monitoring: {len(config.datasource.watchlist)} saham\n\n"
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
        msg = "\U0001F4C8  ISSI Syariah Screener\n"
        msg += "\u2500" * 28 + "\n\n"
        msg += "/start   Mulai monitoring\n"
        msg += "/stop    Hentikan bot\n"
        msg += "/scan    Scan manual\n"
        msg += "/movers  Top Gainer & Loser\n"
        msg += "/detail BBCA  Analisis 1 saham\n"
        msg += "/status  Status bot\n"
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
                    logger.info(f"\U0001F6A8 {len(alerts)} signals found!")
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
