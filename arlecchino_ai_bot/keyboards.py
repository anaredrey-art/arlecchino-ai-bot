from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 $2 — Больше сообщений", url="https://t.me/CryptoBot?start=pay_basic")],
        [InlineKeyboardButton(text="💎 $5 — Безлимит + медиа", url="https://t.me/CryptoBot?start=pay_premium")],
        [InlineKeyboardButton(text="ℹ️ Как это работает?", callback_data="how_it_works")]
    ])

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Продолжить общение", callback_data="continue")],
        [InlineKeyboardButton(text="💰 Мои подписки", callback_data="subscriptions")]
    ])