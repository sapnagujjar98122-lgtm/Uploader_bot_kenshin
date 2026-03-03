import asyncio
import logging
import os
from typing import Dict, Optional
from pyrogram import Client
from pyrogram.types import Message
from config import Config

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self, app: Client, db):
        self.app   = app
        self.db    = db
        self.queue: asyncio.Queue = asyncio.Queue()
        self.current_size = 0

    def add(self, item: Dict):
        self.queue.put_nowait(item)
        self.current_size = self.queue.qsize()
        logger.info(f"Queue: +1 item, total={self.current_size + 1}")

    async def process_queue(self):
        logger.info("Queue worker started.")
        while True:
            item: Dict = await self.queue.get()
            try:
                await self._process(item)
            except Exception as e:
                logger.exception(f"Queue item failed: {e}")
                # Notify admin
                for aid in await self.db.get_admins():
                    try:
                        await self.app.send_message(aid,
                            f"❌ Upload failed: <code>{e}</code>", parse_mode="html")
                    except Exception:
                        pass
            finally:
                self.queue.task_done()

    async def _process(self, item: Dict):
        """
        item keys:
          file_path   – local path of the video file
          file_name   – renamed filename
          thumb_path  – local thumb path (optional)
          caption     – formatted caption text
          anime_name  – for logging
          season      – int
          episode     – int
          notif_chat  – chat_id to send progress updates
          notif_msg_id– message_id to edit
        """
        file_path   = item["file_path"]
        file_name   = item["file_name"]
        thumb_path  = item.get("thumb_path")
        caption     = item["caption"]
        notif_chat  = item.get("notif_chat")
        notif_mid   = item.get("notif_msg_id")

        async def _edit(text: str):
            if notif_chat and notif_mid:
                try:
                    await self.app.edit_message_text(notif_chat, notif_mid,
                        text, parse_mode="html")
                except Exception:
                    pass

        await _edit("⏳ <b>Uploading to storage group…</b>")

        # ── 1. Upload to storage group ────────────────────────
        storage_gid = await self.db.get("storage_group") or Config.STORAGE_GROUP
        if not storage_gid:
            raise ValueError("Storage group not set. Use /set_storage")

        file_size = os.path.getsize(file_path)
        progress_lock = asyncio.Lock()
        last_pct = [0]

        async def progress(current, total):
            pct = int(current * 100 / total)
            async with progress_lock:
                if pct - last_pct[0] >= 10:
                    last_pct[0] = pct
                    bar = "▓" * (pct // 10) + "░" * (10 - pct // 10)
                    await _edit(
                        f"📤 <b>Uploading…</b>\n"
                        f"[{bar}] <b>{pct}%</b>\n"
                        f"<code>{current/1024/1024:.1f} / {total/1024/1024:.1f} MB</code>"
                    )

        storage_msg: Message = await self.app.send_video(
            chat_id   = storage_gid,
            video     = file_path,
            file_name = file_name,
            thumb     = thumb_path,
            caption   = caption,
            parse_mode= "html",
            progress  = progress,
        )
        logger.info(f"Stored in group: msg_id={storage_msg.id}")

        # ── 2. Forward / copy to each target channel ──────────
        channels = await self.db.get_channels()
        sent_count = 0
        for ch in channels:
            try:
                await self.app.copy_message(
                    chat_id     = ch["cid"],
                    from_chat_id= storage_gid,
                    message_id  = storage_msg.id,
                    caption     = caption,
                    parse_mode  = "html",
                )
                sent_count += 1
                await asyncio.sleep(1)   # avoid flood
            except Exception as e:
                logger.warning(f"Failed to send to {ch['cid']}: {e}")

        # ── 3. Send sticker to all channels ───────────────────
        sticker_fid = await self.db.get("sticker_file_id")
        if sticker_fid:
            for ch in channels:
                try:
                    await self.app.send_sticker(ch["cid"], sticker_fid)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

        # ── 4. Delete local file after delay ──────────────────
        delay = await self.db.get("delete_after") or Config.DELETE_AFTER
        await asyncio.sleep(delay)
        for path in [file_path, thumb_path]:
            if path and os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted local file: {path}")

        # ── 5. Log + notify ───────────────────────────────────
        await self.db.log_upload({
            "anime": item.get("anime_name"), "s": item.get("season"),
            "ep": item.get("episode"), "channels": sent_count,
        })
        await _edit(
            f"✅ <b>Upload Complete!</b>\n"
            f"📺 <b>{item.get('anime_name')}</b> "
            f"S{item.get('season'):02d}E{item.get('episode'):02d}\n"
            f"📢 Sent to <b>{sent_count}</b> channel(s)"
        )
