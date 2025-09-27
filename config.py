import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot Configuration
API_ID = os.environ.get("API_ID", "23900056")
API_HASH = os.environ.get("API_HASH", "db7e21e638bc2359907814f4ed8b48a8")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Bypass Bot Configuration
BYPASS_API_ID = os.environ.get("BYPASS_API_ID", "2359907814")
BYPASS_API_HASH = os.environ.get("BYPASS_API_HASH", "db7e21e638bc2359907814f4ed8b48a8")
BYPASS_SESSION_STRING = os.environ.get("BYPASS_SESSION_STRING")
BYPASS_BOT_USERNAME = os.environ.get("BYPASS_BOT_USERNAME", "@DD_Bypass_Bot")

# Admin Configuration
ADMIN_ID = os.environ.get("ADMIN_ID", "7901412493")
OWNER_ID = os.environ.get("OWNER_ID", "7901412493")  # Kept for backward compatibility

# Sudo Users Configuration
# Define sudo users as a comma-separated list in the environment variable or default list
SUDO_USERS = os.environ.get("SUDO_USERS", "7901412493,865764383").split(",")
SUDO_USERS = [uid.strip() for uid in SUDO_USERS if uid.strip().isdigit()]

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Malliofficial:malliofficial@cluster0.db7kygq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Target Group Configuration
TARGET_GROUP_ID = os.environ.get("TARGET_GROUP_ID", "-1002900244842")

# Channel Configuration (for force-subscribe)
FORCE_SUB_CHANNEL1 = os.environ.get("FORCE_SUB_CHANNEL1")
FORCE_SUB_CHANNEL2 = os.environ.get("FORCE_SUB_CHANNEL2")
FORCE_SUB_CHANNEL3 = os.environ.get("FORCE_SUB_CHANNEL3")
FORCE_SUB_CHANNEL4 = os.environ.get("FORCE_SUB_CHANNEL4")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1002533804227")

# Web Server Configuration (if needed for deployment)
PORT = int(os.environ.get("PORT", 8080))

# Initialize MongoDB for sudo users
def initialize_sudo_users():
    """Initialize sudo users in MongoDB at startup"""
    try:
        client = MongoClient(MONGO_URI)
        db = client['bypassbot']
        sudoers = db['sudoers']
        
        # Ensure OWNER_ID is in sudoers as 'owner'
        owner_doc = {'_id': 'owner', 'user_id': str(OWNER_ID)}
        sudoers.update_one({'_id': 'owner'}, {'$set': owner_doc}, upsert=True)
        
        # Add SUDO_USERS to MongoDB
        for user_id in SUDO_USERS:
            if user_id != str(OWNER_ID):  # Skip owner to avoid duplicate
                sudoers.update_one(
                    {'_id': user_id},
                    {'$setOnInsert': {'_id': user_id}},
                    upsert=True
                )
                logger.info(f"Added sudo user {user_id} to MongoDB")
        
        client.close()
    except Exception as e:
        logger.error(f"Error initializing sudo users: {e}")

# Check required environment variables
required_vars = [
    ("BOT_TOKEN", BOT_TOKEN),
    ("MONGO_URI", MONGO_URI),
    ("ADMIN_ID", ADMIN_ID),
    ("TARGET_GROUP_ID", TARGET_GROUP_ID)
]

for var_name, var_value in required_vars:
    if not var_value:
        raise ValueError(f"❌ {var_name} not found in environment variables.")

if not BYPASS_SESSION_STRING:
    logger.warning("⚠️ BYPASS_SESSION_STRING not found. Bypass functionality will be limited.")

# Initialize sudo users
initialize_sudo_users()

# Log configuration details
logger.info("✅ Configuration loaded successfully!")
logger.info(f"📱 API_ID: {API_ID}")
logger.info(f"🤖 Bot Token: {BOT_TOKEN[:20]}..." if BOT_TOKEN else "❌ Bot Token missing")
logger.info(f"👑 Admin ID: {ADMIN_ID}")
logger.info(f"👑 Sudo Users: {', '.join(SUDO_USERS) if SUDO_USERS else 'None'}")
logger.info(f"📊 Target Group: {TARGET_GROUP_ID}")
logger.info(f"📡 MongoDB URI: {'Set' if MONGO_URI else 'Not set'}")
logger.info(f"🔗 Bypass Bot: {BYPASS_BOT_USERNAME}")
