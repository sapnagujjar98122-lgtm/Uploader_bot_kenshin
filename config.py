import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID          = int(os.getenv("API_ID", 0))
    API_HASH        = os.getenv("API_HASH", "")
    BOT_TOKEN       = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS       = [int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()]
    MONGO_URI       = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME         = os.getenv("DB_NAME", "kenshin_anime_bot")
    STORAGE_GROUP   = int(os.getenv("STORAGE_GROUP_ID", 0))
    DELETE_AFTER    = int(os.getenv("DELETE_AFTER", 10))
    AUTO_CHECK_INTERVAL = int(os.getenv("AUTO_CHECK_INTERVAL", 60))
    FILE_PREFIX     = os.getenv("FILE_PREFIX", "@KENSHIN_ANIME")
    DEFAULT_CAPTION = (
        "<b>📺 ᴀɴɪᴍᴇ : {anime_name}\n"
        "━━━━━━━━━━━━━━━━━━━⭒\n"
        "❖ Sᴇᴀsᴏɴ: {season}\n"
        "❖ ᴇᴘɪꜱᴏᴅᴇ: {episode}\n"
        "❖ ᴀᴜᴅɪᴏ: {audio}| #Official\n"
        "❖ Qᴜᴀʟɪᴛʏ: {quality}\n"
        "━━━━━━━━━━━━━━━━━━━⭒\n"
        "<blockquote>POWERED BY: [@KENSHIN_ANIME & @MANWHA_VERSE]</blockquote></b>"
    )
