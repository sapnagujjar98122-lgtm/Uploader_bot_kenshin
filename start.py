from pyrogram import Client, filters
from pyrogram.types import Message

HELP_TEXT = """
<b>🎌 KenshinAnime Bot — Help</b>

<b>━━ Upload ━━</b>
/upload <code>&lt;anime name&gt;</code> — Start upload flow
/queue — View current queue

<b>━━ Channel Management ━━</b>
/add_channel — Add a target channel
/list_channels — List all target channels
/remove_channel — Remove a channel
/set_storage — Set the storage group

<b>━━ Customization ━━</b>
/set_caption — Set custom caption template
/show_caption — View current caption
/reset_caption — Reset to default
/set_thumbnail — Set default thumbnail
/clear_thumbnail — Remove set thumbnail
/set_sticker — Set episode-end sticker
/clear_sticker — Remove sticker

<b>━━ Admin Management ━━</b>
/add_admin <code>&lt;user_id&gt;</code> — Add an admin
/remove_admin <code>&lt;user_id&gt;</code> — Remove an admin
/admins — List all admins

<b>━━ Users & Stats ━━</b>
/users — User stats
/stats — Upload stats
/broadcast — Broadcast to all users

<b>━━ Auto-Track ━━</b>
/track <code>&lt;anime name&gt;</code> — Auto-track for new episodes
/untrack — Remove auto-track
/tracklist — List tracked anime

<b>━━ Caption Variables ━━</b>
<code>{anime_name}</code> <code>{season}</code> <code>{episode}</code>
<code>{audio}</code> <code>{quality}</code>
"""

def register(app: Client, db):

    @app.on_message(filters.command("start") & filters.private)
    async def cmd_start(_, msg: Message):
        await db.add_user(msg.from_user.id,
                          msg.from_user.username,
                          msg.from_user.first_name)
        if not await db.is_admin(msg.from_user.id):
            await msg.reply("🚫 <b>Access Denied.</b> This bot is admin-only.",
                            parse_mode="html")
            return
        await msg.reply(
            "<b>🎌 KenshinAnime Bot v2.0</b>\n\n"
            "Anime upload & management bot.\n"
            "Use /help to see all commands.",
            parse_mode="html"
        )

    @app.on_message(filters.command("help"))
    async def cmd_help(_, msg: Message):
        if not await db.is_admin(msg.from_user.id):
            return
        await msg.reply(HELP_TEXT, parse_mode="html")
