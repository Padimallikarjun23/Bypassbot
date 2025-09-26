# plugins/user_manager.py
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config import DATA_DIR
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "bypass_bot")

# Static admins from .env (comma-separated)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

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
            if "admins" not in self.user_data:
                self.user_data["admins"] = ADMIN_IDS[:]  # init with static admins
                self._save_data()

    # ---------------------- File fallback ----------------------
    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.data_file):
            default = {
                "users": {},
                "admins": ADMIN_IDS[:],
                "total_users": [],
                "banned_users": []
            }
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)
            return default
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"users": {}, "admins": ADMIN_IDS[:], "total_users": [], "banned_users": []}

    def _save_data(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.user_data, f, indent=2, default=str)

    # ---------------------- Mongo operations ----------------------
    def _mongo_add_user(self, user_id: int, data: dict):
        users_col.update_one({"user_id": int(user_id)}, {"$set": {"user_id": int(user_id), **data}}, upsert=True)

    def _mongo_get_user(self, user_id: int) -> Optional[dict]:
        return users_col.find_one({"user_id": int(user_id)})

    def _mongo_set_field(self, user_id: int, field: str, value):
        users_col.update_one({"user_id": int(user_id)}, {"$set": {field: value}}, upsert=True)

    # ---------------------- Admin Management ----------------------
    def get_admins(self) -> List[int]:
        if USING_MONGO:
            docs = users_col.find({"is_admin": True})
            db_admins = [doc["user_id"] for doc in docs]
            return list(set(ADMIN_IDS + db_admins))
        else:
            return list(set(ADMIN_IDS + self.user_data.get("admins", [])))

    def add_admin(self, user_id: int) -> bool:
        if USING_MONGO:
            if users_col.find_one({"user_id": user_id, "is_admin": True}):
                return False
            users_col.update_one({"user_id": user_id}, {"$set": {"is_admin": True}}, upsert=True)
            return True
        else:
            admins = self.user_data.setdefault("admins", [])
            if user_id in admins:
                return False
            admins.append(user_id)
            self._save_data()
            return True

    def remove_admin(self, user_id: int) -> bool:
        if USING_MONGO:
            if not users_col.find_one({"user_id": user_id, "is_admin": True}):
                return False
            users_col.update_one({"user_id": user_id}, {"$unset": {"is_admin": ""}})
            return True
        else:
            admins = self.user_data.setdefault("admins", [])
            if user_id not in admins:
                return False
            admins.remove(user_id)
            self._save_data()
            return True

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.get_admins()

    # ---------------------- Public API ----------------------
    def add_user(self, user_id: int, username: Optional[str]=None):
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
        if not USING_MONGO:
            return
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


# Instantiate global manager
user_manager = UserManager()
try:
    user_manager.migrate_old_data()
except Exception:
    pass
