import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "trades.sqlite3"

MOLIT_API_KEY = os.getenv("MOLIT_API_KEY")
APT_INFO_API_KEY = os.getenv("APT_INFO_API_KEY") or MOLIT_API_KEY

MOLIT_API_URL = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/"
    "getRTMSDataSvcAptTradeDev"
)

APT_LIST_API_URL = (
    "https://apis.data.go.kr/1613000/AptListService3/"
    "getSidoAptList3"
)

APT_BASIC_INFO_API_URL = (
    "https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/"
    "getAphusBassInfoV4"
)

BLD_REGISTRY_API_KEY = MOLIT_API_KEY
BLD_REGISTRY_API_BASE_URL = "http://apis.data.go.kr/1613000/BldRgstService_v2"

REQUEST_TIMEOUT_SECONDS = 20

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "").lower() in ("1", "true", "yes", "y")

SEOUL_GU_CODES = {
    "11110": "\uc885\ub85c\uad6c",
    "11140": "\uc911\uad6c",
    "11170": "\uc6a9\uc0b0\uad6c",
    "11200": "\uc131\ub3d9\uad6c",
    "11215": "\uad11\uc9c4\uad6c",
    "11230": "\ub3d9\ub300\ubb38\uad6c",
    "11260": "\uc911\ub791\uad6c",
    "11290": "\uc131\ubd81\uad6c",
    "11305": "\uac15\ubd81\uad6c",
    "11320": "\ub3c4\ubd09\uad6c",
    "11350": "\ub178\uc6d0\uad6c",
    "11380": "\uc740\ud3c9\uad6c",
    "11410": "\uc11c\ub300\ubb38\uad6c",
    "11440": "\ub9c8\ud3ec\uad6c",
    "11470": "\uc591\ucc9c\uad6c",
    "11500": "\uac15\uc11c\uad6c",
    "11530": "\uad6c\ub85c\uad6c",
    "11545": "\uae08\ucc9c\uad6c",
    "11560": "\uc601\ub4f1\ud3ec\uad6c",
    "11590": "\ub3d9\uc791\uad6c",
    "11620": "\uad00\uc545\uad6c",
    "11650": "\uc11c\ucd08\uad6c",
    "11680": "\uac15\ub0a8\uad6c",
    "11710": "\uc1a1\ud30c\uad6c",
    "11740": "\uac15\ub3d9\uad6c",
}
