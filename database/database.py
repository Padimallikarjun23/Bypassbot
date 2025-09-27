import logging
from datetime import datetime
from pymongo import MongoClient
from config import MONGO_URI

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Initialize MongoDB connection"""
        try:
            self.client = MongoClient(MONGO_URI)
            self.db = self.client['bypassbot']
            self.users = self.db['users']
            self.stats = self.db['stats']
            logger.info("MongoDB connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def close(self):
        """Close MongoDB connection"""
        try:
            self.client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")

    async def add_user(self, user_id: int, username: str = None):
        """Add new user to MongoDB users collection"""
        try:
            user_id_str = str(user_id)  # Store as string for consistency
            user_doc = {
                '_id': user_id_str,
                'username': username,
                'join_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.users.update_one({'_id': user_id_str}, {'$setOnInsert': user_doc}, upsert=True)
            logger.debug(f"Added user {user_id} to database")
            return True
        except Exception as e:
            logger.error(f"Error adding user {user_id} to database: {e}")
            return False

    async def full_userbase(self):
        """Get list of all user IDs"""
        try:
            users = self.users.find({}, {'_id': 1})
            user_ids = [int(doc['_id']) for doc in users if doc['_id'].isdigit()]
            return user_ids
        except Exception as e:
            logger.error(f"Error getting userbase: {e}")
            return []

    async def total_users_count(self):
        """Get total number of users"""
        try:
            count = self.users.count_documents({})
            return count
        except Exception as e:
            logger.error(f"Error getting user count: {e}")
            return 0

    async def log_action(self, user_id: int, action: str):
        """Log user action in stats collection"""
        try:
            user_id_str = str(user_id)  # Store as string for consistency
            self.stats.insert_one({
                'user_id': user_id_str,
                'action': action,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.debug(f"Logged action '{action}' for user {user_id}")
        except Exception as e:
            logger.error(f"Error logging action for user {user_id}: {e}")

# Initialize database
db = Database()

# Export functions
add_user = db.add_user
full_userbase = db.full_userbase
total_users_count = db.total_users_count
log_action = db.log_action
