"""
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
        tickers = re.findall(r'<td>\s*([A-Z]{4})\s*</td>', html)
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
