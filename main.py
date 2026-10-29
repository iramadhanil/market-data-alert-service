import logging, sys
from datetime import datetime
from config import config

def main():
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)])
    logger = logging.getLogger(__name__)

    print()
    print("  ====================================")
    print("  ISSI SYARIAH SCREENER BOT")
    print("  ====================================")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not config.telegram.bot_token:
        print("  ERROR: TELEGRAM_BOT_TOKEN not set!"); sys.exit(1)

    # Load ISSI stock list
    from issi_loader import load_issi_list
    issi_stocks = load_issi_list()
    config.datasource.watchlist = issi_stocks
    print(f"  Saham ISSI: {len(issi_stocks)} tickers")
    print(f"  Scan interval: {config.datasource.scan_interval_seconds}s")
    print()

    from data_fetcher import DataFetcher
    from screener import ScreenerEngine
    from telegram_bot import IHSGAlertBot

    fetcher = DataFetcher()
    screener = ScreenerEngine(fetcher)
    bot = IHSGAlertBot(screener)

    print("  Bot running! /start di Telegram.")
    print("  Ctrl+C to stop.\n")

    try: bot.run()
    except KeyboardInterrupt: print("\n  Stopped.")

if __name__ == "__main__": main()
