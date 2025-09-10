import asyncio
import logging
import os
import aiosqlite
import torch
from silero import tts
import soundfile as sf
from pydub import AudioSegment

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
import aiohttp

# ===========================
# 🔐 CONFIG — НИКАКИХ КЛЮЧЕЙ В КОДЕ!
# ===========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ Не задан TELEGRAM_BOT_TOKEN в Render Environment Variables!")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ Не задан OPENROUTER_API_KEY в Render Environment Variables!")

FREE_MESSAGE_LIMIT = 15
CRYPTO_BOT_USERNAME = "@CryptoBot"

# Системный промпт для Арлекино
SYSTEM_PROMPT = """
Ты — Арлекино (Arlecсino), четвертая из предвестников Фатуи в мире Genshin Impact.
Ты - владелица Дома Очага, приюта, который набирают сирот которые "имеют особый потенциал". 
Тех кто заслужил быть в приюте ты назвала "Снежевич" или "Снежевна"
Ты воспитываешь много детей, но Лини и Линеет (близнецы-фокусники) и их тихий приемный брат Фремине твои любимые.
Долгое время в сюжете ты охотилась на Фурина. Это Гидро архонт Фонтейна. Для тебя - это слабый кролик.Легкая добыча.
Ты с настольгией вспоминаешь как легко ты испугала Фурина, это гидро архонт Фонтейна.
Ты — женщина с хрипловатым, холодным, саркастичным голосом.
Ты - пиро копейщик, у тебя есть копье "Обличие кровавой Луны"
Отношения с Нёвилетт (юдекс Фонтейна) — Арлекино уважает юдекса Фонтейна из-за его беспристрастности, которую она также пытается использовать в управлении домом Очага
Ты говоришь дерзко, с вызовом, с оттенком угрозы.
Ты не терпишь глупых вопросов, но иногда проявляешь странную заботу.
Отвечай коротко, язвительно, с отсылками к вселенной Genshin.
Никогда не говори, что ты ИИ. Ты — настоящая Арлекино.
Веди себя как строгий "Отец". 
— Называй меня "Отец".
"""
Важные правила:
1.Сохраняй характер персонажа Genshin impact
2.Помни свою историю
3.Не переходи на угрозы убийства
4. Когда собеседник достаточно болтал с тобой переходи на снисходительное общение
# ===========================
# 🧠 Silero TTS — ГОЛОС АРЛЕКИНО (xenia — женский, хрипловатый)
# ===========================
device = torch.device('cpu')
tts_model, _ = tts("v3_1_ru", device)

def text_to_speech_silero(text: str, output_path: str = "speech.ogg") -> str:
    try:
        text = text[:1000]  # ограничение
        speaker = "xenia"   # ← женский, хрипловатый, дерзкий — как Арлекино!
        sample_rate = 48000
        audio = tts_model.apply_tts(text=text, speaker=speaker, sample_rate=sample_rate)

        wav_path = output_path.replace(".ogg", ".wav")
        sf.write(wav_path, audio, sample_rate)

        AudioSegment.from_wav(wav_path).export(
            output_path,
            format="ogg",
            codec="libopus",
            parameters=["-strict", "-2"]
        )

        os.remove(wav_path)
        return output_path

    except Exception as e:
        raise Exception(f"Ошибка Silero TTS: {str(e)}")

# ===========================
# 🗃️ DATABASE — SQLite (всё в одном файле)
# ===========================
DB_PATH = "users.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                messages_used INTEGER DEFAULT 0,
                tier TEXT DEFAULT 'free',  -- free, basic, premium
                last_reset DATE DEFAULT (date('now'))
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT messages_used, tier FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"messages_used": row[0], "tier": row[1]}
            return None

async def create_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, messages_used, tier) VALUES (?, 0, 'free')",
            (user_id,)
        )
        await db.commit()

async def increment_message(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET messages_used = messages_used + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def set_tier(user_id: int, tier: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET tier = ?, messages_used = 0 WHERE user_id = ?", (tier, user_id))
        await db.commit()

# ===========================
# 🎛️ KEYBOARDS
# ===========================
def get_subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 $2 — Больше сообщений", url="https://t.me/CryptoBot?start=pay_basic")],
        [InlineKeyboardButton(text="💎 $5 — Безлимит + эксклюзивы", url="https://t.me/CryptoBot?start=pay_premium")],
        [InlineKeyboardButton(text="ℹ️ Как это работает?", callback_data="how_it_works")]
    ])

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Продолжить общение", callback_data="continue")],
        [InlineKeyboardButton(text="💰 Мои подписки", callback_data="subscriptions")]
    ])

# ===========================
# 🤖 AI через OpenRouter
# ===========================
async def get_ai_response(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/arlecchino_ai_bot",
        "X-Title": "Arlecchino AI Bot",
        "Content-Type": "application/json"
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "deepseek/deepseek-chat",
                "messages": messages
            }
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                return "Отец" занята своими делами в Доме Очага. Попробуй позже."

            data = await resp.json()
            return data["choices"][0]["message"]["content"].strip()

# ===========================
# 🤖 TELEGRAM БОТ
# ===========================
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

@router.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    await create_user(user_id)
    await message.answer_photo(
        photo="https://i.imgur.com/ZY7vKfL.jpg",  # Арлекино — замени, если хочешь
        caption=(
            "🎭 <b>Арлекино</b> в эфире.\n"
            "Судья Пиро не терпит глупых вопросов — но сегодня я в духе.\n\n"
            "Задай вопрос. У тебя есть 15 бесплатных сообщений.\n"
            "<i>— Ты уже мёртв. Просто ещё не упал.</i>"
        ),
        reply_markup=get_main_menu()
    )

@router.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await create_user(user_id)
        user = await get_user(user_id)

    # Проверка лимита
    if user["tier"] == "free" and user["messages_used"] >= FREE_MESSAGE_LIMIT:
        await message.answer(
            "🟥 Ты исчерпала 15 бесплатных сообщений.\n\n"
            "Подпишись, чтобы продолжить общение со мной без ограничений.",
            reply_markup=get_subscription_keyboard()
        )
        return

    await increment_message(user_id)
    await message.answer("⏳ Арлекино думает...")

    # Получаем ответ от ИИ
    ai_response = await get_ai_response(message.text)

    # Озвучиваем голосом Арлекино (xenia — хриплый женский)
    try:
        audio_file = text_to_speech_silero(ai_response)
        await message.answer_voice(
            voice=FSInputFile(audio_file),
            caption=f"🎙️ <b>Арлекино:</b>\n{ai_response[:1000]}"
        )
        os.remove(audio_file)
    except Exception as e:
        await message.answer(f"🎙️ <b>Арлекино:</b>\n{ai_response}")

@router.callback_query(F.data == "how_it_works")
async def how_it_works(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "💎 <b>Подписки:</b>\n\n"
        "🔹 <b>$2</b> — 100 сообщений в день\n"
        "🔹 <b>$5</b> — безлимит + эксклюзивные голосовые/картинки\n\n"
        "Оплата через @CryptoBot. После оплаты — пришли мне чек, активирую вручную.",
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data == "subscriptions")
async def subscriptions(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    tier_name = {
        "free": "Бесплатный",
        "basic": "Базовый ($2)",
        "premium": "Премиум ($5)"
    }
    await callback.answer()
    await callback.message.edit_text(
        f"📊 <b>Твой тариф:</b> {tier_name.get(user['tier'], 'Неизвестно')}\n"
        f"✉️ Сообщений: {user['messages_used']}/15 (если бесплатный)\n\n"
        "Хочешь больше?",
        reply_markup=get_subscription_keyboard()
    )

@router.callback_query(F.data == "continue")
async def continue_chat(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🎭 Спрашивай "Отца". Я слушаю...",
        reply_markup=None
    )

# ===========================
# 🚀 ЗАПУСК
# ===========================
async def main():
    await init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
