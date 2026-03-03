import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# State: uid -> waiting for broadcast content
_waiting: set = set()

def _af(db):
    async def _f(_, __, msg): return await db.is_admin(msg.from_user.id)
    return filters.create(_f)

def register(app: Client, db):
    af = _af(db)

    @app.on_message(filters.command("broadcast") & af)
    async def cmd_broadcast(_, msg: Message):
        _waiting.add(msg.from_user.id)
        await msg.reply(
            "📣 <b>Broadcast Mode</b>\n\n"
            "Send the message/media you want to broadcast to all users.\n"
            "Supports: text, photo, video, sticker, document.\n\n"
            "Send /cancel_bc to abort.",
            parse_mode="html"
        )

    @app.on_message(filters.command("cancel_bc") & af)
    async def cmd_cancel_bc(_, msg: Message):
        _waiting.discard(msg.from_user.id)
        await msg.reply("✅ Broadcast cancelled.")

    @app.on_message(filters.private & af & ~filters.command(""))
    async def handle_broadcast_content(_, msg: Message):
        uid = msg.from_user.id
        if uid not in _waiting:
            return
        _waiting.discard(uid)

        users   = await db.get_all_users()
        total   = len(users)
        success = 0
        failed  = 0

        status_msg = await msg.reply(
            f"📣 Broadcasting to <b>{total}</b> users…", parse_mode="html"
        )

        for user in users:
            try:
                await msg.copy(user["uid"])
                success += 1
            except Exception:
                failed += 1
            if (success + failed) % 20 == 0:
                try:
                    await status_msg.edit(
                        f"📣 Broadcasting…\n"
                        f"✅ {success} / ❌ {failed} / 📊 {total}",
                        parse_mode="html"
                    )
                except Exception:
                    pass
            await asyncio.sleep(0.05)  # flood control

        await status_msg.edit(
            f"<b>📣 Broadcast Complete!</b>\n\n"
            f"✅ Success: <b>{success}</b>\n"
            f"❌ Failed:  <b>{failed}</b>\n"
            f"📊 Total:   <b>{total}</b>",
            parse_mode="html"
        )
