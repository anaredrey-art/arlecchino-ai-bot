import asyncio
import logging
import os
from datetime import date
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from yandex.cloud.ai.tts.v3 import tts_service_pb2, tts_service_pb2_grpc
import grpc
import aiohttp

from config import *
from database import *
from keyboards import *

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

# ======================
# YANDEX TTS
# ======================
async def text_to_speech_yandex(text: str, output_path: str = "speech.ogg") -> str:
    try:
        channel = grpc.secure_channel("tts.api.cloud.yandex.net:443", grpc.ssl_channel_credentials())
        stub = tts_service_pb2_grpc.SynthesizerStub(channel)

        request = tts_service_pb2.UtteranceSynthesisRequest(
            text=text[:1000],  # ограничение на 1000 символов
            output_audio_spec=tts_service_pb2.AudioFormatOptions(
                oggopus=tts_service_pb2.OggOpusAudio()
            ),
            voice=tts_service_pb2.VoiceSettings(
                name="filipp"  # мужской голос Арлекино
            ),
            language_code="ru-RU",
        )

        metadata = [("authorization", f"Api-Key {YANDEX_API_KEY}")]

        with open(output_path, "wb") as f:
            stream = stub.UtteranceSynthesis(request, metadata=metadata)
            for response in stream:
                f.write(response.audio_chunk)

        return output_path
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        raise

# ======================
# OPENROUTER AI
# ======================
async def get_ai_response(prompt: str, history: list = None) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://yourdomain.com",  # можно заменить
        "X-Title": "Arlecchino AI Bot",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "deepseek/deepseek-chat",  # или любой другой
                "messages": messages
            }
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"OpenRouter error: {error_text}")
                return "Судья занят. Попробуй позже."

            data = await resp.json()
            return data["choices"][0]["message"]["content"].strip()

# ======================
# ОСНОВНОЙ ХЭНДЛЕР
# ======================
@router.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    await create_user(user_id)
    await message.answer_photo(
        photo="https://i.imgur.com/XYZ1234.jpg",  # Замени на реальную ссылку на Арлекино
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
            "🟥 Ты исчерпал 15 бесплатных сообщений.\n\n"
            "Подпишись, чтобы продолжить общение со мной без ограничений — и получить доступ к изображениям/видео.",
            reply_markup=get_subscription_keyboard()
        )
        return

    # Инкремент счётчика
    await increment_message(user_id)

    # Получаем ответ от ИИ
    await message.answer("⏳ Арлекино думает...")
    ai_response = await get_ai_response(message.text)

    # Озвучиваем
    try:
        audio_file = await text_to_speech_yandex(ai_response)
        await message.answer_voice(
            voice=FSInputFile(audio_file),
            caption=f"🎙️ <b>Арлекино:</b>\n{ai_response[:1000]}"
        )
        os.remove(audio_file)
    except Exception as e:
        logger.error(f"Ошибка озвучки: {e}")
        await message.answer(f"🎙️ <b>Арлекино:</b>\n{ai_response}")

    # Если юзер на премиуме — можно добавить картинку/видео
    if user["tier"] == "premium":
        await message.answer_photo(
            photo="https://i.imgur.com/ARLECCHINO_ART.jpg",  # замени на свою
            caption="Это тебе — за верность Суду."
        )

# ======================
# КОЛЛБЭКИ
# ======================
@router.callback_query(F.data == "how_it_works")
async def how_it_works(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "💎 <b>Подписки:</b>\n\n"
        "🔹 <b>$2</b> — 100 сообщений в день\n"
        "🔹 <b>$5</b> — безлимит + картинки/видео от Арлекино\n\n"
        "Оплата принимается через @CryptoBot в Telegram.\n"
        "После оплаты — пришли мне чек или напиши /start — доступ активируется вручную (пока автоматики нет).",
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
        f"✉️ Сообщений использовано: {user['messages_used']}\n\n"
        "Хочешь улучшить тариф?",
        reply_markup=get_subscription_keyboard()
    )

@router.callback_query(F.data == "continue")
async def continue_chat(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🎭 Задай свой вопрос Арлекино. Я слушаю...",
        reply_markup=None
    )

# ======================
# ЗАПУСК
# ======================
async def main():
    await init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())