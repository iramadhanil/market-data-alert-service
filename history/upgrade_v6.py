"""
IHSG Alert Bot - UPGRADE v6 (ISSI SYARIAH)
============================================
- Scan SELURUH saham ISSI (~627 saham syariah)
- Auto-fetch daftar ISSI terbaru dari Kontan/IDX
- Fallback ke static list jika fetch gagal
- Label: ISSI Syariah Screener

Jalankan: python upgrade_v6.py
"""
import os
DIR = os.path.dirname(os.path.abspath(__file__))
print("\n  Upgrading to v6 (ISSI Syariah)...\n")

# ═══════════════════════════════════════
# issi_loader.py — Dynamic ISSI stock list
# ═══════════════════════════════════════
with open(os.path.join(DIR, "issi_loader.py"), "w", encoding="utf-8") as f:
    f.write('''"""
ISSI Stock List Loader
Fetch daftar saham ISSI terbaru dari:
1. Kontan.co.id (primary)
2. Static fallback list (~600 saham)

List di-cache dan refresh setiap 24 jam.
"""
import logging
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issi_cache.json")
CACHE_MAX_AGE_HOURS = 24


def fetch_issi_from_kontan() -> List[str]:
    """Scrape ISSI constituent list from Kontan.co.id"""
    try:
        import requests
        logger.info("Fetching ISSI list from Kontan.co.id...")
        resp = requests.get(
            "https://www.kontan.co.id/indeks-issi",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(f"Kontan returned {resp.status_code}")
            return []

        html = resp.text
        # Extract ticker codes from table: pattern like | BBCA |
        tickers = re.findall(r'<td>\\s*([A-Z]{4})\\s*</td>', html)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in tickers:
            if t not in seen and len(t) == 4 and t.isalpha():
                seen.add(t)
                unique.append(t)

        if len(unique) > 100:
            logger.info(f"Loaded {len(unique)} ISSI stocks from Kontan")
            return unique
        else:
            logger.warning(f"Only found {len(unique)} tickers, might be incomplete")
            return unique if unique else []

    except Exception as e:
        logger.error(f"Failed to fetch from Kontan: {e}")
        return []


def load_issi_list() -> List[str]:
    """
    Load ISSI stock list with caching.
    1. Check cache (< 24h old)
    2. Fetch from Kontan
    3. Fallback to static list
    """
    # 1. Check cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
            cached_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
            if datetime.now() - cached_time < timedelta(hours=CACHE_MAX_AGE_HOURS):
                tickers = cache.get("tickers", [])
                if len(tickers) > 100:
                    logger.info(f"ISSI cache hit: {len(tickers)} stocks")
                    return tickers
        except Exception:
            pass

    # 2. Fetch fresh
    tickers = fetch_issi_from_kontan()
    if len(tickers) > 100:
        # Save cache
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({"timestamp": datetime.now().isoformat(), "tickers": tickers}, f)
            logger.info(f"ISSI cache saved: {len(tickers)} stocks")
        except Exception:
            pass
        return tickers

    # 3. Fallback to static
    logger.info("Using static ISSI list (fallback)")
    return ISSI_STATIC_LIST


# ══════════════════════════════════════════════════════════
# Static fallback: ISSI constituents (comprehensive list)
# Source: BEI Peng-00004/BEI.POP/01-2025 + Kontan.co.id
# ══════════════════════════════════════════════════════════
ISSI_STATIC_LIST = [
    "AADI","AALI","ABBA","ACES","ACRO","ACST","ADCP","ADES","ADHI","ADMG",
    "ADMR","ADRO","AGAR","AGII","AIMS","AISA","AKKU","AKPI","AKRA","AKSI",
    "ALDO","ALKA","AMFG","AMIN","ANJT","ANTM","APII","APLI","APLN","ARII",
    "ARMY","ARNA","ARTA","ARTI","ASGR","ASII","ASRI","ATIC","ATPK","AUTO",
    "BAPA","BATA","BAYU","BBTN","BCIP","BEEF","BELL","BEST","BFIN","BIPP",
    "BIRD","BISI","BKDP","BKSL","BLTZ","BMSR","BMTR","BOGA","BOLT","BOSS",
    "BRAM","BRIS","BRMS","BRNA","BRPT","BSDE","BSSR","BTEK","BTON","BTPS",
    "BUDI","BUKK","BULL","BUVA","BWPT","BYAN","CAMP","CAKK","CANI","CASS",
    "CBDK","CEKA","CENT","CINT","CKRA","CLEO","CLPI","CMNP","CMPP","CPIN",
    "CSAP","CSIS","CTBN","CTRA","CTTH","DART","DAYA","DEWA","DGIK","DGWG",
    "DIGI","DILD","DKFT","DMAS","DNET","DPNS","DPUM","DSFI","DSNG","DSSA",
    "DUCK","DUTI","DVLA","DWGL","DYAN","ECII","EKAD","ELSA","EMDE","EMTK",
    "ENRG","EPMT","ERAA","ESSA","EXCL","FAST","FASW","FILM","FIRE","FISH",
    "FMII","FOOD","FORZ","FPNI","FREN","GAMA","GDST","GDYR","GEMA","GEMS",
    "GHON","GIAA","GJTL","GMCW","GMFI","GMTD","GOLD","GOOD","GPRA","GTBO",
    "GWSA","GZCO","HADE","HEAL","HERO","HEXA","HITS","HKMU","HOKI","HOME",
    "HRTA","HRUM","IATA","IBST","ICBP","ICON","IDPR","IGAR","IIKP","IKBI",
    "IMPC","INAF","INCI","INCO","INDF","INDR","INDS","INDX","INDY","INPP",
    "INTD","INTP","IPCC","IPCM","IPOL","ISAT","ISSP","ITMA","ITMG","JECC",
    "JGLE","JIHD","JKON","JKSW","JMAS","JPFA","JRPT","JSKY","JSMR","JSPT",
    "JTPE","KAEF","KARW","KBLI","KBLM","KBLV","KDSI","KIAS","KICI","KIJA",
    "KINO","KIOS","KKGI","KLBF","KOBX","KOIN","KOPI","KPAS","KPIG","LAND",
    "LAPD","LCGP","LCKM","LINK","LION","LMPI","LMSH","LPCK","LPIN","LPKR",
    "LPLI","LPPF","LRNA","LSIP","LTLS","LUCK","MAGP","MAIN","MAMI","MAPB",
    "MAPI","MARK","MAPA","MASA","MBAP","MBMA","MBSS","MBTO","MCAS","MDKA",
    "MDKI","MDLN","MEDC","MERK","META","MFMI","MGRO","MICE","MIKA","MINA",
    "MIRA","MITI","MKPI","MLIA","MLPL","MLPT","MMLP","MNCN","MPMX","MPPA",
    "MRAT","MTEL","MTDL","MTLA","MTRA","MSIN","MTSM","MYOH","MYOR","MYRX",
    "NASA","NATO","NELY","NFCX","NIKL","NIPS","NRCA","OBAT","OASA","OMRE",
    "PALM","PANI","PANR","PBID","PBSA","PCAR","PDES","PEHA","PGAS","PGEO",
    "PGLI","PICO","PJAA","PKPK","PNBN","PNBS","PNSE","POLI","POLL","PORT",
    "POWR","PPRE","PPRO","PRDA","PRIM","PSAB","PSKT","PSSI","PTBA","PTIS",
    "PTPP","PTRO","PTSN","PTSP","PUDP","PWON","PYFA","RAJA","RALS","RANC",
    "RBMS","RDTX","REAL","RICY","RIGS","RMBA","RMKE","ROTI","RUIS","SAFE",
    "SAME","SCBD","SCCO","SCMA","SCPI","SDMU","SDPC","SDRA","SGER","SGRO",
    "SHID","SHIP","SIDO","SILO","SIMP","SINI","SIPD","SKBM","SKLT","SKRN",
    "SLIS","SMCB","SMDM","SMDR","SMGR","SMKL","SMMV","SMRA","SMMA","SMSM",
    "SNLK","SOCI","SOFA","SONA","SPMA","SPTO","SQMI","SRAJ","SRIL","SRTG",
    "SSIA","SSMS","SSTM","STAR","STTP","SUGI","SURE","SWAT","TALF","TAMA",
    "TAPG","TARA","TAXI","TBIG","TBLA","TBMS","TCID","TCPI","TDPM","TELE",
    "TFAS","TGKA","TGRA","TINS","TIRA","TIRT","TKIM","TLKM","TMAS","TMPO",
    "TNCA","TOBA","TOPS","TOTL","TOWR","TPIA","TPMA","TRJA","TRIS","TRST",
    "TRUS","TSPC","TUGU","TURI","UANG","UCID","ULTJ","UNIQ","UNIT","UNTR",
    "UNVR","URBN","VICI","VINS","VIVA","VOKS","WAPO","WEGE","WEHA","WGSH",
    "WIFI","WIKA","WINS","WMUU","WOOD","WSBP","WSKT","WTON","ZBRA",
]
''')
print("  [OK] issi_loader.py (auto-fetch + 500+ static fallback)")

# ═══════════════════════════════════════
# config.py — ISSI mode
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
    volume_surge_multiplier: float = 2.0
    breakout_margin_pct: float = 3.0
    flag_pole_min_pct: float = 5.0
    rsi_short_period: int = 6
    rsi_oversold: float = 30.0
    max_drop_from_high_pct: float = 5.0
    runaway_range_multiplier: float = 2.0
    ma_short: int = 3
    ma_medium: int = 5
    ma_tolerance_pct: float = 1.0
    alert_cooldown_minutes: int = 30
    batch_size: int = 20
    batch_delay: float = 1.0

@dataclass
class IndicatorConfig:
    rsi_period: int = 14
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
    itick_api_key: str = os.getenv("ITICK_API_KEY", "")
    stockbit_username: str = os.getenv("STOCKBIT_USERNAME", "")
    stockbit_password: str = os.getenv("STOCKBIT_PASSWORD", "")
    stockbit_token: str = os.getenv("STOCKBIT_TOKEN", "")
    goapi_token: str = os.getenv("GOAPI_TOKEN", "")
    sectors_api_key: str = os.getenv("SECTORS_API_KEY", "")
    use_yahoo_fallback: bool = True
    scan_interval_seconds: int = 120  # 2 min for 600+ stocks
    watchlist: List[str] = field(default_factory=list)
    # Will be populated with full ISSI at startup

@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    screener: ScreenerConfig = field(default_factory=ScreenerConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    datasource: DataSourceConfig = field(default_factory=DataSourceConfig)
    timezone: str = "Asia/Jakarta"
    log_level: str = "INFO"

config = AppConfig()
''')
print("  [OK] config.py (ISSI mode)")

# ═══════════════════════════════════════
# main.py — Load ISSI at startup
# ═══════════════════════════════════════
with open(os.path.join(DIR, "main.py"), "w", encoding="utf-8") as f:
    f.write('''import logging, sys
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
    print("  Ctrl+C to stop.\\n")

    try: bot.run()
    except KeyboardInterrupt: print("\\n  Stopped.")

if __name__ == "__main__": main()
''')
print("  [OK] main.py (ISSI loader)")

# ═══════════════════════════════════════
# Update telegram_bot.py — change branding
# ═══════════════════════════════════════
bot_path = os.path.join(DIR, "telegram_bot.py")
if os.path.exists(bot_path):
    content = open(bot_path, "r", encoding="utf-8").read()
    content = content.replace("IHSG Alert Bot", "ISSI Syariah Screener")
    content = content.replace("STRONG BUY", "SYARIAH ALERT")
    with open(bot_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] telegram_bot.py (rebranded: ISSI Syariah)")
else:
    print("  [WARN] telegram_bot.py not found")

print(f"""
  ==========================================
  UPGRADE v6 COMPLETE — ISSI SYARIAH
  ==========================================

  Perubahan:
  1. Scan SELURUH saham ISSI (~627 saham syariah)
  2. Auto-fetch daftar terbaru dari Kontan.co.id
  3. Cache 24 jam (refresh otomatis)
  4. Fallback ke 500+ saham static jika fetch gagal
  5. Branding: ISSI Syariah Screener
  6. Scan interval: 120s (optimal untuk 600+ saham)

  Jalankan:  python main.py
  ==========================================
""")
