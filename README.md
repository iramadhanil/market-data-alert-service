# Market-Data Alert Service (IHSG Alert Bot)

A Python bot that scans Indonesian stocks during trading hours, looks for breakout patterns that come with unusual volume, and sends the result to Telegram. I built it in April 2026 for my own trading and ran it on a Linux VPS as a systemd service.

Built with help from an AI coding assistant. I uploaded it in October 2026 from my local copy of the project. The code in the root folder is the version I ran (v6), and `history/` keeps the installer script of every version.

## What it does

1. **Builds the stock list.** About 600 stocks in the Indonesia Sharia Stock Index (ISSI), fetched from Kontan.co.id, cached for 24 hours, with a static fallback list.
2. **Pulls market data.** Quotes and daily bars from the iTick REST API, with Yahoo Finance (`yfinance`) as a fallback.
3. **Scans on a schedule.** Every 2 minutes during Indonesia Stock Exchange hours (weekdays 09:00 to 11:30 and 13:30 to 15:00 Jakarta time), in batches.
4. **Checks five patterns.**
   - Volume breakout: close at least 3% above the 5-day moving average
   - Flag or pennant breakout after a pole of 5% or more
   - RSI(6) bounce from oversold
   - Breakaway or runaway gap
   - Runaway bar with a range at least twice the normal range
5. **Alerts only on volume.** A stock is sent as an alert when at least one pattern fires and today's volume is at least twice its 20-day average. Each alert gets a 0 to 100 strength score from the pattern, the volume ratio, the distance from the day's high and indicator agreement (RSI, Bollinger Bands, MACD, Stochastic, VWAP). A ticker is not repeated within 30 minutes.
6. **Talks through Telegram.** Commands: `/start`, `/stop`, `/scan`, `/movers`, `/status`, `/detail`, `/help`. Messages are in Indonesian.

The bot only produces signals. It never places orders, and nothing here is investment advice.

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point: loads the stock list and starts the Telegram bot |
| `config.py` | Thresholds and settings, secrets read from `.env` |
| `issi_loader.py` | Fetches and caches the ISSI stock list |
| `data_fetcher.py` | iTick and Yahoo Finance data sources |
| `screener.py` | Pattern detection and alert scoring |
| `indicators.py` | RSI, Bollinger Bands, MACD, Stochastic, VWAP |
| `telegram_bot.py` | Telegram commands, market-hours loop and message format |
| `deploy_vps.sh` | Sets up a Ubuntu/Debian VPS: virtual environment, `.env`, systemd service with automatic restart |
| `start_bot.bat`, `start_bot_hidden.vbs` | Start the bot on Windows (the hidden version is used for auto-start) |
| `history/` | Installer scripts for v1 to v6 (each one writes the bot files for that version) |

## Version history (April 2026)

| Version | Script | Main change |
|---|---|---|
| v1 | `create_bot.py` | First version: generates the config, indicators, data fetcher, screener and Telegram bot |
| v1 fix | `create_bot_fix.py` | Jakarta time zone, watchlist display, extra data source |
| v2 | `upgrade_v2.py` | iTick API for live Indonesian market data, auto-start on Windows boot |
| v3 | `upgrade_v3.py` | Four detection patterns (breakout, gap, flag, runaway) and a cleaner Telegram message |
| v4 | `upgrade_v4.py` | Automatic push alerts, top gainers and losers, detailed output per pattern, ready for a VPS |
| v5 | `upgrade_v5.py` | Scans the whole exchange (800+ stocks) in batches instead of a 40-stock watchlist |
| v6 | `upgrade_v6.py` | Stock list switched to the ISSI sharia index (about 600 stocks), fetched automatically with a fallback |

## Run it

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ITICK_API_KEY
python main.py
```

On a Ubuntu/Debian VPS, `bash deploy_vps.sh` installs everything and registers the `ihsg-bot` systemd service, which restarts on failure and starts again after a reboot.

## 概要（日本語）

インドネシア株（シャリア適合銘柄 約600社）を取引時間中に2分ごとにスキャンし、出来高を伴うブレイクアウトなどのパターンを検出してTelegramに通知するPythonボットです。2026年4月に自分のトレード用に作成し、LinuxのVPS上でsystemdサービスとして運用しました。シグナルの通知のみで、自動売買は行いません。
