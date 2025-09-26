# config.py
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot Configuration
API_ID = int(os.environ.get("API_ID", "23900056"))
API_HASH = os.environ.get("API_HASH", "db7e21e638bc2359907814f4ed8b48a8")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Web Server Configuration
PORT = int(os.environ.get("PORT", 8080))

# Owner Configuration
OWNER_ID = int(os.environ.get("OWNER_ID", "7901412493"))

# Channel Configuration
FORCE_SUB_CHANNEL1 = os.environ.get("FORCE_SUB_CHANNEL1", None)
FORCE_SUB_CHANNEL2 = os.environ.get("FORCE_SUB_CHANNEL2", None)
FORCE_SUB_CHANNEL3 = os.environ.get("FORCE_SUB_CHANNEL3", None)
FORCE_SUB_CHANNEL4 = os.environ.get("FORCE_SUB_CHANNEL4", None)

# Database Configuration
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1002533804227"))

# Bypass Configuration
BYPASS_API_ID = int(os.environ.get("BYPASS_API_ID", "2359907814"))
BYPASS_API_HASH = os.environ.get("BYPASS_API_HASH", "db7e21e638bc2359907814f4ed8b48a8")
BYPASS_SESSION_STRING = os.environ.get("BYPASS_SESSION_STRING")
BYPASS_BOT_USERNAME = "DD_Bypass_Bot"

# Target Group Configuration
TARGET_GROUP_ID = int(os.environ.get("TARGET_GROUP_ID", "-1002900244842"))

# Admin Configuration
# Comma-separated list of admin IDs in .env like:
# ADMIN_IDS=123456789,987654321,111222333
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", str(os.environ.get("ADMIN_IDS", "7901412493,865764383"))).split(",") if x.strip().isdigit()]

# Keep backward compatibility: if no ADMIN_IDS, fall back to single OWNER_ID
if not ADMIN_IDS and os.getenv("ADMIN_IDS"):
    ADMIN_IDS = [int(os.environ.get("ADMIN_IDS"))]

# Directories
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Check required environment variables
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in environment variables.")

if not BYPASS_SESSION_STRING:
    print("⚠️ WARNING: BYPASS_SESSION_STRING not found. Bypass functionality will be limited.")

print("✅ Configuration loaded successfully!")
print(f"📱 API_ID: {API_ID}")
print(f"🤖 Bot Token: {BOT_TOKEN[:20]}..." if BOT_TOKEN else "❌ Bot Token missing")
print(f"👑 Admin IDs: {ADMIN_IDS}")
print(f"📊 Target Group: {TARGET_GROUP_ID}")
