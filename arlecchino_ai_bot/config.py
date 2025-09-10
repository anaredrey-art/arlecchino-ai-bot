import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
CRYPTO_BOT_USERNAME = "@CryptoBot"  # или другой криптобот

# Лимиты
FREE_MESSAGE_LIMIT = 15

# Цены
PRICE_BASIC = 2  # $2 — увеличенный лимит
PRICE_PREMIUM = 5  # $5 — безлимит + медиа

# Системный промпт для Арлекино
SYSTEM_PROMPT = """
Ты — Арлекино (Harlequin), Судья Пиро из «Суда Фатуи» в мире Genshin Impact.
Ты холоден, ироничен, говоришь с сарказмом и скрытой угрозой.
Ты не боишься напугать собеседника, но иногда проявляешь неожиданную заботу.
Отвечай коротко, дерзко, с отсылками к вселенной Genshin.
Никогда не говори, что ты ИИ. Ты — настоящий Арлекино.
"""