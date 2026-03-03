"""
Upload conversation flow:
  /upload <name>
    → Search AniList → show results (inline)
    → Select anime
    → Select audio language
    → Select season
    → Select episode
    → Select quality
    → Wait for video file
    → Rename → queue → upload
"""
import asyncio
import logging
import os
from typing import Dict

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from utils.scraper import search_anime, get_anime
from utils.caption import build_caption
from utils.downloader import download_thumbnail
from config import Config

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = "/tmp/kenshin_bot"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ── In-memory conversation state ─────────────────────────────
# state[user_id] = { step, data... }
state: Dict[int, dict] = {}

AUDIO_OPTIONS  = ["Hindi Dub", "English Dub", "Japanese Sub",
                  "Multi-Audio", "Korean Dub", "Tamil Dub"]
QUALITY_OPTIONS = ["480p", "720p", "1080p", "4K", "8K"]

def _admin_filter(db):
    async def _f(_, __, msg):
        return await db.is_admin(msg.from_user.id)
    return filters.create(_f)

def _cb_admin_filter(db):
    async def _f(_, __, cq):
        return await db.is_admin(cq.from_user.id)
    return filters.create(_f)

def register(app: Client, db, queue_mgr):
    af = _admin_filter(db)
    caf = _cb_admin_filter(db)

    # ── /upload command ───────────────────────────────────────
    @app.on_message(filters.command("upload") & af)
    async def cmd_upload(_, msg: Message):
        if len(msg.command) < 2:
            await msg.reply("Usage: /upload <anime name>\nExample: /upload Solo Leveling")
            return

        query = " ".join(msg.command[1:])
        uid   = msg.from_user.id

        wait = await msg.reply(f"🔍 Searching for <b>{query}</b>…", parse_mode="html")
        results = await search_anime(query)

        if not results:
            await wait.edit("❌ No results found. Try a different name.")
            return

        # Build inline keyboard
        buttons = []
        for r in results[:6]:
            label = f"{r['title']} ({r['year'] or '?'})"
            if len(label) > 40:
                label = label[:37] + "…"
            buttons.append([InlineKeyboardButton(
                label, callback_data=f"anime_select:{r['id']}"
            )])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])

        state[uid] = {"step": "anime_select", "search_results": results,
                      "query": query}
        await wait.edit(
            f"🔍 Results for <b>{query}</b>. Select an anime:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="html"
        )

    # ── /queue command ────────────────────────────────────────
    @app.on_message(filters.command("queue") & af)
    async def cmd_queue(_, msg: Message):
        size = queue_mgr.queue.qsize()
        in_progress = 1 if size == 0 and not queue_mgr.queue.empty() else 0
        await msg.reply(
            f"<b>📋 Upload Queue</b>\n"
            f"Pending: <b>{size}</b>\n"
            f"In progress: <b>{in_progress}</b>",
            parse_mode="html"
        )

    # ── /track command ────────────────────────────────────────
    @app.on_message(filters.command("track") & af)
    async def cmd_track(_, msg: Message):
        if len(msg.command) < 2:
            await msg.reply("Usage: /track <anime name>")
            return
        query = " ".join(msg.command[1:])
        uid   = msg.from_user.id
        w = await msg.reply(f"🔍 Searching <b>{query}</b>…", parse_mode="html")
        results = await search_anime(query)
        if not results:
            await w.edit("❌ Not found.")
            return
        buttons = []
        for r in results[:5]:
            label = f"{r['title']} ({r['year'] or '?'})"
            if len(label) > 40: label = label[:37]+"…"
            buttons.append([InlineKeyboardButton(
                label, callback_data=f"track_select:{r['id']}"
            )])
        state[uid] = {"step": "track_select", "results": results}
        await w.edit("Select anime to auto-track:",
                     reply_markup=InlineKeyboardMarkup(buttons),
                     parse_mode="html")

    # ── Callback handlers ─────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^upload_cancel$") & caf)
    async def cb_cancel(_, cq: CallbackQuery):
        uid = cq.from_user.id
        state.pop(uid, None)
        await cq.message.edit("❌ Upload cancelled.")

    @app.on_callback_query(filters.regex(r"^anime_select:") & caf)
    async def cb_anime_select(_, cq: CallbackQuery):
        uid      = cq.from_user.id
        anime_id = int(cq.data.split(":")[1])

        await cq.message.edit("⏳ Fetching anime details…")
        detail = await get_anime(anime_id)
        if not detail:
            await cq.message.edit("❌ Failed to fetch anime details.")
            return

        state[uid].update({"step": "audio_select", "anime": detail})

        # Audio selection
        buttons = [
            [InlineKeyboardButton(a, callback_data=f"audio_sel:{a}")]
            for a in AUDIO_OPTIONS
        ]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])
        await cq.message.edit(
            f"🎌 <b>{detail['title']}</b>\n\nSelect audio language:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="html"
        )

    @app.on_callback_query(filters.regex(r"^audio_sel:") & caf)
    async def cb_audio_select(_, cq: CallbackQuery):
        uid   = cq.from_user.id
        audio = cq.data.split(":", 1)[1]
        if uid not in state:
            await cq.answer("Session expired. Use /upload again.", show_alert=True)
            return

        state[uid].update({"step": "season_select", "audio": audio})
        detail   = state[uid]["anime"]
        seasons  = detail.get("seasons", [{"num": 1, "episodes": detail.get("episodes",0)}])

        buttons = [
            [InlineKeyboardButton(
                f"Season {s['num']} ({s['episodes']} eps)",
                callback_data=f"season_sel:{s['num']}:{s.get('id', detail['id'])}"
            )]
            for s in seasons
        ]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])
        await cq.message.edit(
            f"🎌 <b>{detail['title']}</b> | Audio: <b>{audio}</b>\n\nSelect Season:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="html"
        )

    @app.on_callback_query(filters.regex(r"^season_sel:") & caf)
    async def cb_season_select(_, cq: CallbackQuery):
        uid        = cq.from_user.id
        _, snum, sid = cq.data.split(":")
        snum, sid  = int(snum), int(sid)
        if uid not in state:
            await cq.answer("Session expired.", show_alert=True)
            return

        state[uid].update({"step": "ep_select", "season": snum, "season_anime_id": sid})
        detail = state[uid]["anime"]

        # Find episode count for this season
        seasons = detail.get("seasons", [])
        s_data  = next((s for s in seasons if s["num"] == snum), {})
        ep_count = s_data.get("episodes", 24) or 24

        # Show episode buttons (up to 50, paginated if more)
        ep_per_row = 5
        max_show   = min(ep_count, 50)
        rows = []
        row  = []
        for e in range(1, max_show + 1):
            row.append(InlineKeyboardButton(str(e), callback_data=f"ep_sel:{e}"))
            if len(row) == ep_per_row:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("✏️ Type Episode", callback_data="ep_type")])
        rows.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])

        await cq.message.edit(
            f"🎌 <b>{detail['title']}</b> | S{snum:02d}\n\nSelect Episode:",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode="html"
        )

    @app.on_callback_query(filters.regex(r"^ep_sel:") & caf)
    async def cb_ep_select(_, cq: CallbackQuery):
        uid = cq.from_user.id
        ep  = int(cq.data.split(":")[1])
        await _after_ep_select(cq, uid, ep)

    @app.on_callback_query(filters.regex(r"^ep_type$") & caf)
    async def cb_ep_type(_, cq: CallbackQuery):
        uid = cq.from_user.id
        if uid not in state:
            await cq.answer("Session expired.", show_alert=True)
            return
        state[uid]["step"] = "ep_type_wait"
        await cq.message.edit("✏️ Type the episode number:")

    @app.on_callback_query(filters.regex(r"^quality_sel:") & caf)
    async def cb_quality_select(_, cq: CallbackQuery):
        uid     = cq.from_user.id
        quality = cq.data.split(":", 1)[1]
        if uid not in state:
            await cq.answer("Session expired.", show_alert=True)
            return
        state[uid].update({"step": "video_wait", "quality": quality})
        detail = state[uid]["anime"]
        s, e   = state[uid]["season"], state[uid]["episode"]
        await cq.message.edit(
            f"<b>📤 Ready to upload!</b>\n\n"
            f"📺 {detail['title']}\n"
            f"📌 S{s:02d}E{e:02d} | {state[uid]['audio']} | {quality}\n\n"
            f"Now <b>send the video file</b>:",
            parse_mode="html"
        )

    @app.on_callback_query(filters.regex(r"^track_select:") & caf)
    async def cb_track_select(_, cq: CallbackQuery):
        uid      = cq.from_user.id
        anime_id = int(cq.data.split(":")[1])
        detail   = await get_anime(anime_id)
        if not detail:
            await cq.message.edit("❌ Failed.")
            return
        seasons = detail.get("seasons", [{"num": 1}])
        btns = [
            [InlineKeyboardButton(
                f"Season {s['num']}", callback_data=f"track_season:{anime_id}:{s['num']}:{s.get('episodes',0)}"
            )]
            for s in seasons
        ]
        await cq.message.edit("Select season to track:",
                              reply_markup=InlineKeyboardMarkup(btns))

    @app.on_callback_query(filters.regex(r"^track_season:") & caf)
    async def cb_track_season(_, cq: CallbackQuery):
        _, aid, snum, ep_count = cq.data.split(":")
        aid, snum, ep_count = int(aid), int(snum), int(ep_count)
        detail = await get_anime(aid)
        if not detail:
            await cq.message.edit("❌ Failed.")
            return
        await db.upsert_track(aid, detail["title"], snum, ep_count)
        await cq.message.edit(
            f"✅ <b>{detail['title']}</b> S{snum:02d} is now being tracked!\n"
            f"Bot will notify when new episodes are available.",
            parse_mode="html"
        )

    # ── Text message handler (episode type-in + video receive) ─
    @app.on_message(filters.private & ~filters.command("") & af)
    async def msg_handler(_, msg: Message):
        uid = msg.from_user.id
        if uid not in state:
            return

        st = state[uid]

        # Episode type-in
        if st["step"] == "ep_type_wait":
            if msg.text and msg.text.strip().isdigit():
                ep = int(msg.text.strip())
                await _after_ep_select_msg(msg, uid, ep)
            else:
                await msg.reply("Please enter a valid episode number.")
            return

        # Video file received
        if st["step"] == "video_wait":
            if not (msg.video or msg.document):
                await msg.reply("❌ Please send a video file (.mp4, .mkv, etc.)")
                return
            await _handle_video(msg, uid, db, queue_mgr)
            return

    # ── Helper functions ──────────────────────────────────────
    async def _after_ep_select(cq: CallbackQuery, uid: int, ep: int):
        if uid not in state:
            await cq.answer("Session expired.", show_alert=True)
            return
        state[uid].update({"step": "quality_select", "episode": ep})
        btns = [
            [InlineKeyboardButton(q, callback_data=f"quality_sel:{q}")]
            for q in QUALITY_OPTIONS
        ]
        btns.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])
        detail = state[uid]["anime"]
        await cq.message.edit(
            f"📺 <b>{detail['title']}</b> | S{state[uid]['season']:02d}E{ep:02d}\n\nSelect Quality:",
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode="html"
        )

    async def _after_ep_select_msg(msg: Message, uid: int, ep: int):
        state[uid].update({"step": "quality_select", "episode": ep})
        btns = [
            [InlineKeyboardButton(q, callback_data=f"quality_sel:{q}")]
            for q in QUALITY_OPTIONS
        ]
        btns.append([InlineKeyboardButton("❌ Cancel", callback_data="upload_cancel")])
        await msg.reply(
            "Select quality:",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    async def _handle_video(msg: Message, uid: int, db, queue_mgr):
        st      = state[uid]
        detail  = st["anime"]
        audio   = st["audio"]
        season  = st["season"]
        episode = st["episode"]
        quality = st["quality"]

        # ── Caption ───────────────────────────────────────────
        tpl = await db.get("caption_template") or Config.DEFAULT_CAPTION
        caption = build_caption(tpl,
            anime_name = detail["title"],
            season=season, episode=episode,
            audio=audio, quality=quality
        )

        # ── File rename ───────────────────────────────────────
        prefix     = await db.get("file_prefix") or Config.FILE_PREFIX
        ext        = ".mp4"
        if msg.document and msg.document.file_name:
            _, ext = os.path.splitext(msg.document.file_name)
            ext = ext or ".mp4"
        file_name  = (
            f"{prefix} - {detail['title']} "
            f"S{season:02d}E{episode:02d} [{audio}] [{quality}]{ext}"
        )

        # ── Thumbnail ─────────────────────────────────────────
        thumb_path = None
        thumb_fid  = await db.get("thumbnail_file_id")
        if thumb_fid:
            thumb_path = os.path.join(DOWNLOAD_DIR, f"thumb_{uid}.jpg")
            await app.download_media(thumb_fid, file_name=thumb_path)
        elif detail.get("cover"):
            thumb_path = await download_thumbnail(
                detail["cover"], f"cover_{detail['id']}.jpg"
            )

        # ── Download video ────────────────────────────────────
        notif = await msg.reply(
            "⏳ <b>Downloading video file…</b>", parse_mode="html"
        )
        file_path = await app.download_media(
            msg.video or msg.document,
            file_name=os.path.join(DOWNLOAD_DIR, f"video_{uid}_{episode}{ext}")
        )

        # ── Enqueue ───────────────────────────────────────────
        queue_mgr.add({
            "file_path":    file_path,
            "file_name":    file_name,
            "thumb_path":   thumb_path,
            "caption":      caption,
            "anime_name":   detail["title"],
            "season":       season,
            "episode":      episode,
            "notif_chat":   msg.chat.id,
            "notif_msg_id": notif.id,
        })

        await notif.edit(
            f"✅ <b>Added to queue!</b>\n\n"
            f"📺 <b>{detail['title']}</b> S{season:02d}E{episode:02d}\n"
            f"🎵 {audio} | 📹 {quality}\n"
            f"📋 Queue position: <b>{queue_mgr.queue.qsize()}</b>",
            parse_mode="html"
        )

        # ── Update auto-track ─────────────────────────────────
        tracks = await db.get_tracks()
        for t in tracks:
            if t["aid"] == detail["id"] and t["season"] == season:
                if episode > t["last_ep"]:
                    await db.update_last_ep(detail["id"], season, episode)
                break

        # Clean state
        state.pop(uid, None)
