from pymongo import MongoClient
from pymongo.errors import PyMongoError, ConnectionFailure
from datetime import datetime

DB_URL = "mongodb+srv://Malliofficial:malliofficial@cluster0.db7kygq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

class MongoDatabase:
    def __init__(self):
        try:
            self.client = MongoClient(DB_URL)
            self.db = self.client["Bypass_Bot"]
            self.users = self.db["users"]
            self.stats = self.db["stats"]
            self.setup()
        except ConnectionFailure as e:
            print(f"[MongoDB] Connection failed: {e}")
            raise

    def setup(self):
        """Ensure indexes are created."""
        try:
            self.users.create_index("user_id", unique=True)
            self.stats.create_index("user_id")
        except PyMongoError as e:
            print(f"[MongoDB] Setup error: {e}")

    async def add_user(self, user_id: int, username: str = None):
        """Add a new user to the database"""
        try:
            join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_doc = {
                "user_id": user_id,
                "username": username,
                "join_date": join_date,
                "is_premium": False
            }
            self.users.update_one(
                {"user_id": user_id},
                {"$setOnInsert": user_doc},
                upsert=True
            )
            return True
        except PyMongoError as e:
            print(f"[MongoDB] Error adding user: {e}")
            return False

    async def full_userbase(self):
        """Get list of all user IDs"""
        try:
            return [doc["user_id"] for doc in self.users.find({}, {"user_id": 1})]
        except PyMongoError as e:
            print(f"[MongoDB] Error fetching userbase: {e}")
            return []

    async def total_users_count(self):
        """Get total number of users"""
        try:
            return self.users.count_documents({})
        except PyMongoError as e:
            print(f"[MongoDB] Error getting user count: {e}")
            return 0


# Initialize database
db = MongoDatabase()

# Export functions
full_userbase = db.full_userbase
total_users_count = db.total_users_count
add_user = db.add_user
