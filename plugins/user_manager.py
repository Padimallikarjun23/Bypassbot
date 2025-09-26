# plugins/user_manager.py
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config import DATA_DIR, ADMIN_ID
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "bypass_bot")

# Try to use pymongo if MONGO_URI provided, otherwise fallback to file-based storage
try:
    if MONGO_URI:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        users_col = db["users"]
        USING_MONGO = True
    else:
        USING_MONGO = False
except Exception as e:
    print(f"[WARN] Could not initialize MongoDB client: {e}")
    USING_MONGO = False

class UserManager:
    def __init__(self):
        self.data_file = os.path.join(DATA_DIR, "user_data.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        if not USING_MONGO:
            self.user_data = self._load_data()
            if "admin_id" not in self.user_data:
                self.user_data["admin_id"] = ADMIN_ID
                self._save_data()

    # ---------------------- File fallback ----------------------
    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.data_file):
            default = {"users": {}, "admin_id": ADMIN_ID, "total_users": [], "banned_users": []}
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)
            return default
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"users": {}, "admin_id": ADMIN_ID, "total_users": [], "banned_users": []}

    def _save_data(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.user_data, f, indent=2, default=str)

    # ---------------------- Mongo operations ----------------------
    def _mongo_add_user(self, user_id: int, data: dict):
        users_col.update_one({"user_id": int(user_id)}, {"$set": {"user_id": int(user_id), **data}}, upsert=True)

    def _mongo_get_user(self, user_id: int) -> Optional[dict]:
        doc = users_col.find_one({"user_id": int(user_id)})
        return doc

    def _mongo_set_field(self, user_id: int, field: str, value):
        users_col.update_one({"user_id": int(user_id)}, {"$set": {field: value}}, upsert=True)

    # ---------------------- Public API ----------------------
    def add_user(self, user_id: int, username: Optional[str]=None):
        """Register a user (creates document/entry)."""
        payload = {
            "username": username or "",
            "join_date": datetime.utcnow().isoformat(),
            "is_premium": False
        }
        if USING_MONGO:
            self._mongo_add_user(user_id, payload)
        else:
            uid = str(user_id)
            if uid not in self.user_data["users"]:
                self.user_data["users"][uid] = payload
            if uid not in self.user_data["total_users"]:
                self.user_data["total_users"].append(uid)
            self._save_data()

    def is_admin(self, user_id: int) -> bool:
        if USING_MONGO:
            admin = os.getenv("ADMIN_ID")
            try:
                return int(admin) == int(user_id)
            except Exception:
                return False
        else:
            return int(self.user_data.get("admin_id", ADMIN_ID)) == int(user_id)

    def set_premium(self, user_id: int, days: int):
        expiry = datetime.utcnow() + timedelta(days=days)
        if USING_MONGO:
            self._mongo_set_field(user_id, "is_premium", True)
            self._mongo_set_field(user_id, "premium_expiry", expiry.isoformat())
        else:
            uid = str(user_id)
            self.user_data["users"].setdefault(uid, {})
            self.user_data["users"][uid]["is_premium"] = True
            self.user_data["users"][uid]["premium_expiry"] = expiry.isoformat()
            self._save_data()

    def is_premium(self, user_id: int) -> bool:
        if USING_MONGO:
            doc = self._mongo_get_user(user_id)
            if not doc: return False
            return bool(doc.get("is_premium", False))
        else:
            uid = str(user_id)
            return bool(self.user_data["users"].get(uid, {}).get("is_premium", False))

    def get_premium_expiry(self, user_id: int) -> Optional[datetime]:
        if USING_MONGO:
            doc = self._mongo_get_user(user_id)
            if not doc: return None
            exp = doc.get("premium_expiry")
            if exp:
                try:
                    return datetime.fromisoformat(exp)
                except Exception:
                    return None
            return None
        else:
            uid = str(user_id)
            exp = self.user_data["users"].get(uid, {}).get("premium_expiry")
            if exp:
                try:
                    return datetime.fromisoformat(exp)
                except Exception:
                    return None
            return None

    def get_total_users(self) -> int:
        if USING_MONGO:
            return users_col.count_documents({})
        else:
            return len(self.user_data.get("total_users", []))

    def ban_user(self, user_id: int):
        if USING_MONGO:
            users_col.update_one({"user_id": int(user_id)}, {"$set": {"banned": True}}, upsert=True)
        else:
            uid = str(user_id)
            if uid not in self.user_data.get("banned_users", []):
                self.user_data["banned_users"].append(uid)
                self._save_data()

    def unban_user(self, user_id: int):
        if USING_MONGO:
            users_col.update_one({"user_id": int(user_id)}, {"$unset": {"banned": ""}})
        else:
            uid = str(user_id)
            if uid in self.user_data.get("banned_users", []):
                self.user_data["banned_users"].remove(uid)
                self._save_data()

    def migrate_old_data(self):
        """If using Mongo and local JSON has users, migrate them once."""
        if not USING_MONGO:
            return
        # load existing json if present
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    local = json.load(f)
                users = local.get("users", {})
                for uid, info in users.items():
                    users_col.update_one({"user_id": int(uid)}, {"$set": {"user_id": int(uid), **info}}, upsert=True)
                print("[MIGRATE] Local JSON migrated to MongoDB")
        except Exception as e:
            print(f"[MIGRATE] Migration error: {e}")

# instantiate global manager
user_manager = UserManager()
# run migration if needed
try:
    user_manager.migrate_old_data()
except Exception:
    pass