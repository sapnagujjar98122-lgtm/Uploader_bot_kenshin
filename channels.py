import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

def _af(db):
    async def _f(_, __, msg): return await db.is_admin(msg.from_user.id)
    return filters.create(_f)

# State: waiting for forwarded message
_adding: set = set()

def register(app: Client, db):
    af = _af(db)

    @app.on_message(filters.command("add_channel") & af)
    async def cmd_add_channel(_, msg: Message):
        _adding.add(msg.from_user.id)
        await msg.reply(
            "📢 <b>Add Target Channel</b>\n\n"
            "1️⃣ Add me as <b>admin</b> to your channel.\n"
            "2️⃣ Forward any message from that channel here.\n\n"
            "Send /cancel to abort.",
            parse_mode="html"
        )

    @app.on_message(filters.command("cancel") & af)
    async def cmd_cancel(_, msg: Message):
        _adding.discard(msg.from_user.id)
        await msg.reply("✅ Cancelled.")

    @app.on_message(filters.forwarded & af)
    async def handle_forward(_, msg: Message):
        uid = msg.from_user.id
        if uid not in _adding:
            return
        _adding.discard(uid)

        # Extract origin channel info
        origin = msg.forward_origin
        if not origin or not hasattr(origin, "chat"):
            await msg.reply("❌ Could not detect channel. Forward a message FROM a channel.")
            return

        chat = origin.chat
        cid  = chat.id
        name = chat.title or "Unknown"
        uname= chat.username

        # Verify bot can post in channel
        try:
            test = await app.send_message(cid, "✅ Channel linked to KenshinAnime Bot!")
            await test.delete()
        except Exception as e:
            await msg.reply(
                f"❌ <b>Can't post in channel!</b>\n"
                f"Make sure I'm an admin with 'Post Messages' permission.\n\n"
                f"Error: <code>{e}</code>",
                parse_mode="html"
            )
            return

        await db.add_channel(cid, name, uname)
        await msg.reply(
            f"✅ <b>Channel Added!</b>\n\n"
            f"📢 {name}\n"
            f"🆔 <code>{cid}</code>"
            + (f"\n🔗 @{uname}" if uname else ""),
            parse_mode="html"
        )

    @app.on_message(filters.command("list_channels") & af)
    async def cmd_list_channels(_, msg: Message):
        channels = await db.get_channels()
        if not channels:
            await msg.reply("No target channels set. Use /add_channel")
            return
        lines = []
        for i, ch in enumerate(channels, 1):
            uname = f"@{ch['username']}" if ch.get("username") else "private"
            lines.append(
                f"{i}. <b>{ch['name']}</b> {uname}\n"
                f"   ID: <code>{ch['cid']}</code>"
            )
        await msg.reply(
            f"<b>📢 Target Channels ({len(channels)})</b>\n\n" + "\n\n".join(lines),
            parse_mode="html"
        )

    @app.on_message(filters.command("remove_channel") & af)
    async def cmd_remove_channel(_, msg: Message):
        channels = await db.get_channels()
        if not channels:
            await msg.reply("No channels to remove.")
            return
        buttons = []
        for ch in channels:
            uname = f"@{ch['username']}" if ch.get("username") else ch["name"]
            buttons.append([InlineKeyboardButton(
                f"🗑 {uname}", callback_data=f"rm_ch:{ch['cid']}"
            )])
        await msg.reply(
            "Select channel to remove:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    @app.on_callback_query(filters.regex(r"^rm_ch:"))
    async def cb_remove_channel(_, cq):
        if not await db.is_admin(cq.from_user.id):
            await cq.answer("Access denied.", show_alert=True)
            return
        cid = int(cq.data.split(":")[1])
        await db.remove_channel(cid)
        await cq.message.edit(f"✅ Channel <code>{cid}</code> removed.", parse_mode="html")
