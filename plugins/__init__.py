# plugins/__init__.py
import asyncio
from pymongo.errors import ConnectionError as MongoConnectionError
from pyrogram.errors import PyrogramError

async def init_plugins():
    """Initialize all plugins and tasks"""
    try:
        # Initialize MongoDB
        from database import db
        print("[INFO] MongoDB connection initialized")

        # Initialize bypass handler tasks
        from bypass_handler import start_tasks, check_premium_expiry
        await start_tasks()
        print("[INFO] Bypass handler tasks started")

        # Start premium expiry checker
        asyncio.create_task(check_premium_expiry())
        print("[INFO] Premium expiry checker started")

        print("[INFO] All plugins initialized successfully")
    except MongoConnectionError as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        raise  # Re-raise to prevent bot from running without DB
    except PyrogramError as e:
        print(f"[ERROR] Pyrogram error during plugin initialization: {e}")
        raise  # Re-raise to ensure client issues are addressed
    except Exception as e:
        print(f"[ERROR] Failed to initialize plugins: {e}")
        raise
