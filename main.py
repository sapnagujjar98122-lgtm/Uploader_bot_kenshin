"""
KenshinAnimeBot — Main entry point
"""
import asyncio
import logging
import importlib

from pyrofork import Client, idle
from pyrofork.enums import ParseMode

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("KenshinBot")

# ── Create client ──────────────────────────────────────────────────────────────
app = Client(
    name      = "KenshinAnimeBot",
    api_id    = Config.API_ID,
    api_hash  = Config.API_HASH,
    bot_token = Config.BOT_TOKEN,
)

# ── Load plugins ───────────────────────────────────────────────────────────────
PLUGINS = [
    "plugins.commands",
    "plugins.upload",
    "plugins.channels",
    "plugins.settings",
]

def load_plugins():
    for plugin in PLUGINS:
        try:
            importlib.import_module(plugin)
            logger.info(f"Loaded: {plugin}")
        except Exception as e:
            logger.error(f"Failed to load {plugin}: {e}")

# ── Startup notify ─────────────────────────────────────────────────────────────
async def on_start():
    me = await app.get_me()
    logger.info(f"Bot started: @{me.username} (ID: {me.id})")
    for admin_id in Config.ADMIN_IDS:
        try:
            await app.send_message(
                admin_id,
                f"<b>Bot is online!</b>\n@{me.username}\nUse /help for commands.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    load_plugins()
    await app.start()
    await on_start()
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
