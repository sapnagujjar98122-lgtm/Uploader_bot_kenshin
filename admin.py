import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config

logger = logging.getLogger(__name__)

def admin_filter(db):
    async def _f(_, __, msg: Message):
        return await db.is_admin(msg.from_user.id)
    return filters.create(_f)

def register(app: Client, db):
    af = admin_filter(db)

    # ── Add / Remove admin ────────────────────────────────────
    @app.on_message(filters.command("add_admin") & af)
    async def cmd_add_admin(_, msg: Message):
        if len(msg.command) < 2 or not msg.command[1].isdigit():
            await msg.reply("Usage: /add_admin <user_id>")
            return
        uid = int(msg.command[1])
        await db.add_admin(uid, msg.from_user.id)
        await msg.reply(f"✅ Admin <code>{uid}</code> added.", parse_mode="html")

    @app.on_message(filters.command("remove_admin") & af)
    async def cmd_remove_admin(_, msg: Message):
        if len(msg.command) < 2 or not msg.command[1].isdigit():
            await msg.reply("Usage: /remove_admin <user_id>")
            return
        uid = int(msg.command[1])
        if uid in Config.ADMIN_IDS:
            await msg.reply("❌ Cannot remove a root admin set in .env")
            return
        await db.remove_admin(uid)
        await msg.reply(f"✅ Admin <code>{uid}</code> removed.", parse_mode="html")

    @app.on_message(filters.command("admins") & af)
    async def cmd_admins(_, msg: Message):
        admins = await db.get_admins()
        lines = [f"• <code>{a}</code>" for a in admins]
        await msg.reply(
            f"<b>👮 Admins ({len(admins)})</b>\n" + "\n".join(lines),
            parse_mode="html"
        )

    # ── Caption management ────────────────────────────────────
    @app.on_message(filters.command("set_caption") & af)
    async def cmd_set_caption(_, msg: Message):
        text = msg.text.split(None, 1)
        if len(text) < 2:
            await msg.reply(
                "Send your caption template after the command.\n\n"
                "Available variables:\n"
                "<code>{anime_name} {season} {episode} {audio} {quality}</code>",
                parse_mode="html"
            )
            return
        template = text[1]
        await db.set("caption_template", template)
        await msg.reply("✅ Caption template saved!", parse_mode="html")

    @app.on_message(filters.command("show_caption") & af)
    async def cmd_show_caption(_, msg: Message):
        tpl = await db.get("caption_template") or Config.DEFAULT_CAPTION
        await msg.reply(
            f"<b>Current Caption Template:</b>\n\n{tpl}",
            parse_mode="html"
        )

    @app.on_message(filters.command("reset_caption") & af)
    async def cmd_reset_caption(_, msg: Message):
        await db.set("caption_template", Config.DEFAULT_CAPTION)
        await msg.reply("✅ Caption reset to default.", parse_mode="html")

    # ── Thumbnail management ──────────────────────────────────
    @app.on_message(filters.command("set_thumbnail") & af)
    async def cmd_set_thumbnail(_, msg: Message):
        if msg.reply_to_message and msg.reply_to_message.photo:
            fid = msg.reply_to_message.photo.file_id
            await db.set("thumbnail_file_id", fid)
            await msg.reply("✅ Thumbnail saved!", parse_mode="html")
        else:
            await msg.reply("Reply to a photo with /set_thumbnail")

    @app.on_message(filters.command("clear_thumbnail") & af)
    async def cmd_clear_thumbnail(_, msg: Message):
        await db.set("thumbnail_file_id", None)
        await msg.reply("✅ Thumbnail cleared.", parse_mode="html")

    # ── Sticker management ────────────────────────────────────
    @app.on_message(filters.command("set_sticker") & af)
    async def cmd_set_sticker(_, msg: Message):
        if msg.reply_to_message and msg.reply_to_message.sticker:
            fid = msg.reply_to_message.sticker.file_id
            await db.set("sticker_file_id", fid)
            await msg.reply("✅ Sticker set! It will be sent after each episode upload.")
        else:
            await msg.reply("Reply to a sticker with /set_sticker")

    @app.on_message(filters.command("clear_sticker") & af)
    async def cmd_clear_sticker(_, msg: Message):
        await db.set("sticker_file_id", None)
        await msg.reply("✅ Sticker cleared.", parse_mode="html")

    # ── Storage group ─────────────────────────────────────────
    @app.on_message(filters.command("set_storage") & af)
    async def cmd_set_storage(_, msg: Message):
        if len(msg.command) < 2:
            await msg.reply(
                "Usage: /set_storage <group_id>\n\n"
                "Forward any message from your storage group to get its ID."
            )
            return
        try:
            gid = int(msg.command[1])
            await db.set("storage_group", gid)
            await msg.reply(f"✅ Storage group set to <code>{gid}</code>", parse_mode="html")
        except ValueError:
            await msg.reply("❌ Invalid group ID.")

    # ── Queue info ────────────────────────────────────────────
    @app.on_message(filters.command("queue") & af)
    async def cmd_queue(_, msg: Message):
        from main import app as _app
        # We pass queue_mgr via closure won't work here — handled in upload.py
        await msg.reply("Use /queue only via the upload module. (See upload.py)")

    # ── Users & stats ─────────────────────────────────────────
    @app.on_message(filters.command("users") & af)
    async def cmd_users(_, msg: Message):
        count = await db.user_count()
        users = await db.get_all_users()
        # Show last 10
        lines = []
        for u in users[-10:]:
            uname = f"@{u['uname']}" if u.get("uname") else "no username"
            lines.append(f"• <code>{u['uid']}</code> {uname} — {u['name']}")
        text = (
            f"<b>👥 Total Users: {count}</b>\n\n"
            + ("\n".join(lines) if lines else "No users yet.")
        )
        await msg.reply(text, parse_mode="html")

    @app.on_message(filters.command("stats") & af)
    async def cmd_stats(_, msg: Message):
        stats = await db.upload_stats()
        user_count = await db.user_count()
        channels = await db.get_channels()
        tracks = await db.get_tracks()
        await msg.reply(
            f"<b>📊 Bot Statistics</b>\n\n"
            f"👥 Users: <b>{user_count}</b>\n"
            f"📢 Channels: <b>{len(channels)}</b>\n"
            f"📤 Total Uploads: <b>{stats['total']}</b>\n"
            f"📅 Uploads Today: <b>{stats['today']}</b>\n"
            f"🔄 Auto-tracked Anime: <b>{len(tracks)}</b>",
            parse_mode="html"
        )

    # ── File prefix ───────────────────────────────────────────
    @app.on_message(filters.command("set_prefix") & af)
    async def cmd_set_prefix(_, msg: Message):
        text = msg.text.split(None, 1)
        if len(text) < 2:
            await msg.reply("Usage: /set_prefix @YourChannel")
            return
        await db.set("file_prefix", text[1].strip())
        await msg.reply(f"✅ File prefix set to: <code>{text[1].strip()}</code>",
                        parse_mode="html")

    # ── Auto-track commands ───────────────────────────────────
    @app.on_message(filters.command("tracklist") & af)
    async def cmd_tracklist(_, msg: Message):
        tracks = await db.get_tracks()
        if not tracks:
            await msg.reply("No anime being tracked.")
            return
        lines = []
        for t in tracks:
            lines.append(
                f"• <b>{t['name']}</b> S{t['season']:02d} "
                f"(last ep: {t['last_ep']})"
            )
        await msg.reply(
            f"<b>🔄 Auto-tracked ({len(tracks)})</b>\n\n" + "\n".join(lines),
            parse_mode="html"
        )

    @app.on_message(filters.command("delete_after") & af)
    async def cmd_delete_after(_, msg: Message):
        if len(msg.command) < 2 or not msg.command[1].isdigit():
            current = await db.get("delete_after") or Config.DELETE_AFTER
            await msg.reply(f"Current delete delay: <b>{current}s</b>\n"
                            f"Usage: /delete_after <seconds>", parse_mode="html")
            return
        secs = int(msg.command[1])
        await db.set("delete_after", secs)
        await msg.reply(f"✅ Files will be deleted after <b>{secs}s</b>",
                        parse_mode="html")
