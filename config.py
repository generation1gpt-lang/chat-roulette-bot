import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")
REDIS_URL  = os.getenv("REDIS_URL",  "redis://localhost:6379/0")

# Настройки модерации
MAX_REPORTS_FOR_BAN = 3      # жалоб до бана
BAN_DURATION_HOURS  = 24     # часов бана
