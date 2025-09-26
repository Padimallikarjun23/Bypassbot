# plugins/user_manager.py
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
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
        admins_col = db["admins"]
        # Optional: Index for faster queries
        admins_col.create_index("user_id", unique=True)
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
            if "admin_ids" not in self.user_data:
                self.user_data["admin_ids"] = [str(ADMIN_ID)] if ADMIN_ID else []
                self._save_data()

    # ---------------------- File fallback ----------------------
    def _load_data(self) -> Dict[str, Any]:
        if not os.path.exists(self.data_file):
            default = {"users": {}, "total_users": [], "banned_users": [], "admin_ids": [str(ADMIN_ID)] if ADMIN_ID else []}
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)
            return default
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Migrate old single admin_id to admin_ids if necessary
            if "admin_id" in data and "admin_ids" not in data:
                admin_id = data.pop("admin_id")
                data["admin_ids"] = [str(admin_id)] if admin_id else []
            return data
        except Exception:
            return {"users": {}, "total_users": [], "banned_users": [], "admin_ids": [str(ADMIN_ID)] if ADMIN_ID else []}

    def _save_data(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.user_data, f, indent=2, default=str)
        except Exception as e:
            print(f"[WARN] Failed to save data: {e}")

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
            return admins_col.find_one({"user_id": int(user_id)}) is not None
        else:
            return str(user_id) in self.user_data.get("admin_ids", [])

    def add_admin(self, user_id: int):
        if USING_MONGO:
            admins_col.update_one({"user_id": int(user_id)}, {"$set": {"user_id": int(user_id)}}, upsert=True)
        else:
            uid = str(user_id)
            if uid not in self.user_data.get("admin_ids", []):
                self.user_data["admin_ids"].append(uid)
                self._save_data()

    def remove_admin(self, user_id: int):
        if USING_MONGO:
            admins_col.delete_one({"user_id": int(user_id)})
        else:
            uid = str(user_id)
            if uid in self.user_data.get("admin_ids", []):
                self.user_data["admin_ids"].remove(uid)
                self._save_data()

    def get_admins(self) -> List[int]:
        if USING_MONGO:
            return [doc["user_id"] for doc in admins_col.find({})]
        else:
            return [int(uid) for uid in self.user_data.get("admin_ids", [])]

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
            if not doc or not doc.get("is_premium", False):
                return False
            exp = doc.get("premium_expiry")
            if not exp:
                return False
            try:
                return datetime.fromisoformat(exp) > datetime.utcnow()
            except Exception:
                return False
        else:
            uid = str(user_id)
            user = self.user_data["users"].get(uid, {})
            if not user.get("is_premium", False):
                return False
            exp = user.get("premium_expiry")
            if not exp:
                return False
            try:
                return datetime.fromisoformat(exp) > datetime.utcnow()
            except Exception:
                return False

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
                # Migrate admins
                admin_ids = local.get("admin_ids", [])
                if "admin_id" in local:
                    old_admin = local.get("admin_id")
                    if old_admin and str(old_admin) not in admin_ids:
                        admin_ids.append(str(old_admin))
                for uid in admin_ids:
                    admins_col.update_one({"user_id": int(uid)}, {"$set": {"user_id": int(uid)}}, upsert=True)
                print("[MIGRATE] Local JSON migrated to MongoDB")
        except Exception as e:
            print(f"[MIGRATE] Migration error: {e}")
        # Also ensure initial ADMIN_ID is added if not present
        admin = os.getenv("ADMIN_ID")
        if admin:
            try:
                admin_id = int(admin)
                if admins_col.find_one({"user_id": admin_id}) is None:
                    admins_col.update_one({"user_id": admin_id}, {"$set": {"user_id": admin_id}}, upsert=True)
            except Exception:
                pass

# instantiate global manager
user_manager = UserManager()
# run migration if needed
try:
    user_manager.migrate_old_data()
except Exception:
    pass
