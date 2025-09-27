import pymongo
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from config import MONGO_URI, ADMIN_ID

class UserManager:
    def __init__(self):
        self.client = pymongo.MongoClient(MONGO_URI)
        self.db = self.client['bypassbot']
        self.users = self.db['users']  # Total users
        self.sudoers = self.db['sudoers']  # Sudo admins
        self.banned = self.db['banned']  # Banned users
        self.premium = self.db['premium']  # Premium users with expiry
        self.usage = self.db['usage']  # Daily usage

        # Ensure owner is in sudoers
        owner_doc = {'_id': 'owner', 'user_id': str(ADMIN_ID)}
        self.sudoers.update_one({'_id': 'owner'}, {'$set': owner_doc}, upsert=True)

    def add_user(self, user_id: int) -> bool:
        """Add user to total users list"""
        uid = str(user_id)
        result = self.users.update_one({'_id': uid}, {'$setOnInsert': {'_id': uid}}, upsert=True)
        return result.matched_count == 0  # True if new user

    def is_premium(self, user_id: int) -> bool:
        """Check if user is premium"""
        uid = str(user_id)
        doc = self.premium.find_one({'_id': uid})
        if doc and doc.get('expiry', 0) > datetime.now().timestamp():
            return True
        elif doc:
            self.remove_premium_user(user_id)  # Clean up expired premium
        return False

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin (owner or sudo)"""
        return self.is_sudo(user_id) or str(user_id) == str(ADMIN_ID)

    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        uid = str(user_id)
        return self.banned.find_one({'_id': uid}) is not None

    def ban_user(self, user_id: int) -> bool:
        """Ban a user"""
        uid = str(user_id)
        result = self.banned.update_one({'_id': uid}, {'$setOnInsert': {'_id': uid}}, upsert=True)
        return result.matched_count == 0

    def unban_user(self, user_id: int) -> bool:
        """Unban a user"""
        uid = str(user_id)
        result = self.banned.delete_one({'_id': uid})
        return result.deleted_count > 0

    def add_premium_user(self, user_id: int, days: int = 30) -> bool:
        """Add or extend premium user"""
        try:
            uid = str(user_id).strip()
            if not uid or not uid.isdigit():
                print(f"[ERROR] Invalid user ID format: {uid}")
                return False

            now = datetime.now().timestamp()
            if self.is_premium(user_id):
                # Extend existing premium
                current_expiry = self.premium.find_one({'_id': uid}).get('expiry', now)
                if current_expiry < now:
                    current_expiry = now
                new_expiry = current_expiry + (days * 24 * 3600)
                self.premium.update_one({'_id': uid}, {'$set': {'expiry': new_expiry}})
                print(f"[DEBUG] Extended premium for user {uid} until {datetime.fromtimestamp(new_expiry)}")
            else:
                # Add new premium
                expiry = now + (days * 24 * 3600)
                self.premium.insert_one({'_id': uid, 'expiry': expiry})
                print(f"[DEBUG] Added new premium user {uid} until {datetime.fromtimestamp(expiry)}")

            self.add_user(user_id)  # Ensure user is in users collection
            return True

        except Exception as e:
            print(f"[ERROR] Failed to add premium user {user_id}: {str(e)}")
            return False

    def remove_premium_user(self, user_id: int) -> bool:
        """Remove premium user"""
        try:
            uid = str(user_id).strip()
            if not uid or not uid.isdigit():
                print(f"[DEBUG] Invalid user ID format: {uid}")
                return False

            result = self.premium.delete_one({'_id': uid})
            print(f"[DEBUG] Successfully removed premium for user {uid}")
            return result.deleted_count > 0

        except Exception as e:
            print(f"[ERROR] Failed to remove premium user {uid}: {str(e)}")
            return False

    def check_premium_expiry(self):
        now = datetime.now().timestamp()
        expired = []
        for doc in self.premium.find({'expiry': {'$lt': now}}):
            expired.append(doc['_id'])
            self.remove_premium_user(doc['_id'])
            print(f"[DEBUG] Expired premium for user {doc['_id']}")
        return expired

    def get_daily_usage(self, user_id: int) -> int:
        """Get user's daily usage count"""
        uid = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        doc = self.usage.find_one({'_id': uid})
        if doc:
            # Clean old dates to keep document size small
            current_usage = {k: v for k, v in doc.items() if k == '_id' or k == today}
            self.usage.update_one({'_id': uid}, {'$set': current_usage})
            return doc.get(today, 0)
        return 0

    def increment_usage(self, user_id: int) -> int:
        """Increment user's daily usage"""
        uid = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        current = self.get_daily_usage(user_id)
        self.usage.update_one(
            {'_id': uid},
            {'$set': {today: current + 1}},
            upsert=True
        )
        return current + 1

    def get_stats(self) -> Dict[str, int]:
        """Get bot statistics"""
        return {
            "total_users": self.users.count_documents({}),
            "premium_users": self.premium.count_documents({}),
            "banned_users": self.banned.count_documents({})
        }

    def get_premium_expiry(self, user_id: int) -> Optional[datetime]:
        """Get premium expiry date"""
        uid = str(user_id)
        doc = self.premium.find_one({'_id': uid})
        if doc:
            return datetime.fromtimestamp(doc['expiry'])
        return None

    def add_sudo(self, user_id: int) -> bool:
        """Add a sudo admin"""
        uid = str(user_id)
        if uid == str(ADMIN_ID):
            return False  # Owner can't be added as sudo
        result = self.sudoers.update_one({'_id': uid}, {'$setOnInsert': {'_id': uid}}, upsert=True)
        return result.matched_count == 0

    def remove_sudo(self, user_id: int) -> bool:
        """Remove a sudo admin"""
        uid = str(user_id)
        if uid == str(ADMIN_ID):
            return False
        result = self.sudoers.delete_one({'_id': uid})
        return result.deleted_count > 0

    def is_sudo(self, user_id: int) -> bool:
        """Check if user is a sudo admin"""
        uid = str(user_id)
        return self.sudoers.find_one({'_id': uid}) is not None

    def get_sudoers(self) -> List[str]:
        """Get list of sudo admin IDs"""
        return [doc['_id'] for doc in self.sudoers.find({}) if doc['_id'] != 'owner']

    def get_all_users(self) -> List[str]:
        """Get list of all user IDs"""
        return [doc['_id'] for doc in self.users.find({})]

user_manager = UserManager()
