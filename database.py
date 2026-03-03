import datetime
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

class Database:
    def __init__(self, uri: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[Config.DB_NAME]
        self.settings  = self.db["settings"]
        self.admins    = self.db["admins"]
        self.channels  = self.db["channels"]
        self.users     = self.db["users"]
        self.auto_track= self.db["auto_track"]
        self.logs      = self.db["upload_logs"]

    async def connect(self):
        await self.client.admin.command("ping")

    # ── Settings ──────────────────────────────────────────────
    async def get(self, key: str, default: Any = None) -> Any:
        doc = await self.settings.find_one({"k": key})
        return doc["v"] if doc else default

    async def set(self, key: str, value: Any):
        await self.settings.update_one({"k": key}, {"$set": {"v": value}}, upsert=True)

    # ── Admins ────────────────────────────────────────────────
    async def get_admins(self) -> List[int]:
        base = Config.ADMIN_IDS[:]
        db_admins = await self.admins.find({}).to_list(None)
        for a in db_admins:
            if a["uid"] not in base:
                base.append(a["uid"])
        return base

    async def add_admin(self, uid: int, by: int):
        await self.admins.update_one(
            {"uid": uid},
            {"$set": {"uid": uid, "by": by, "at": datetime.datetime.utcnow()}},
            upsert=True
        )

    async def remove_admin(self, uid: int):
        await self.admins.delete_one({"uid": uid})

    async def is_admin(self, uid: int) -> bool:
        if uid in Config.ADMIN_IDS:
            return True
        doc = await self.admins.find_one({"uid": uid})
        return doc is not None

    # ── Channels ──────────────────────────────────────────────
    async def get_channels(self) -> List[Dict]:
        return await self.channels.find({}).to_list(None)

    async def add_channel(self, cid: int, name: str, username: Optional[str] = None):
        await self.channels.update_one(
            {"cid": cid},
            {"$set": {"cid": cid, "name": name, "username": username,
                      "at": datetime.datetime.utcnow()}},
            upsert=True
        )

    async def remove_channel(self, cid: int):
        await self.channels.delete_one({"cid": cid})

    # ── Users ─────────────────────────────────────────────────
    async def add_user(self, uid: int, uname: Optional[str], name: str):
        await self.users.update_one(
            {"uid": uid},
            {"$set": {"uid": uid, "uname": uname, "name": name,
                      "seen": datetime.datetime.utcnow()}},
            upsert=True
        )

    async def get_all_users(self) -> List[Dict]:
        return await self.users.find({}).to_list(None)

    async def user_count(self) -> int:
        return await self.users.count_documents({})

    # ── Auto-track ────────────────────────────────────────────
    async def get_tracks(self) -> List[Dict]:
        return await self.auto_track.find({}).to_list(None)

    async def upsert_track(self, anime_id: int, anime_name: str, season: int, last_ep: int):
        await self.auto_track.update_one(
            {"aid": anime_id, "season": season},
            {"$set": {"aid": anime_id, "name": anime_name,
                      "season": season, "last_ep": last_ep,
                      "updated": datetime.datetime.utcnow()}},
            upsert=True
        )

    async def update_last_ep(self, anime_id: int, season: int, ep: int):
        await self.auto_track.update_one(
            {"aid": anime_id, "season": season},
            {"$set": {"last_ep": ep, "updated": datetime.datetime.utcnow()}}
        )

    async def remove_track(self, anime_id: int, season: int):
        await self.auto_track.delete_one({"aid": anime_id, "season": season})

    # ── Upload logs ───────────────────────────────────────────
    async def log_upload(self, data: Dict):
        data["at"] = datetime.datetime.utcnow()
        await self.logs.insert_one(data)

    async def upload_stats(self) -> Dict:
        total = await self.logs.count_documents({})
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today = await self.logs.count_documents({"at": {"$gte": today_start}})
        return {"total": total, "today": today}
