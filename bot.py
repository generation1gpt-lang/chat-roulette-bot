import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.redis import RedisStorage

from config import BOT_TOKEN, REDIS_URL
from matcher import Matcher
from keyboards import main_kb, report_kb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = RedisStorage.from_url(REDIS_URL)
dp = Dispatcher(storage=storage)
matcher = Matcher(REDIS_URL)


# ─── /start ───────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    await matcher.register_user(msg.from_user.id)
    await msg.answer(
        "👋 Привет! Это анонимный чат-рулетка.\n\n"
        "Нажми <b>Найти собеседника</b> — и я соединю тебя с рандомным человеком.\n"
        "Никто не узнает кто ты. Общайся свободно 🎲",
        parse_mode="HTML",
        reply_markup=main_kb()
    )


# ─── Поиск / стоп ─────────────────────────────────────────────────────────────

@dp.message(F.text == "🎲 Найти собеседника")
async def find_partner(msg: Message):
    user_id = msg.from_user.id

    if await matcher.is_banned(user_id):
        await msg.answer("🚫 Ты временно заблокирован за нарушение правил.")
        return

    if await matcher.get_partner(user_id):
        await msg.answer("Ты уже в чате. Нажми Стоп чтобы выйти.", reply_markup=main_kb(in_chat=True))
        return

    # Добавляем в очередь и пробуем найти пару
    partner_id = await matcher.enqueue(user_id)

    if partner_id:
        # Нашли пару — создаём сессию
        await matcher.create_session(user_id, partner_id)
        await bot.send_message(user_id,    "✅ Собеседник найден! Начинайте общаться.\n/next — новый | /stop — выйти", reply_markup=main_kb(in_chat=True))
        await bot.send_message(partner_id, "✅ Собеседник найден! Начинайте общаться.\n/next — новый | /stop — выйти", reply_markup=main_kb(in_chat=True))
    else:
        await msg.answer("🔍 Ищу собеседника... Подожди немного.", reply_markup=main_kb(searching=True))


@dp.message(F.text == "⏭ Следующий")
@dp.message(Command("next"))
async def next_partner(msg: Message):
    user_id = msg.from_user.id
    await _end_session(user_id, reason="next")
    # Сразу ищем нового
    await find_partner(msg)


@dp.message(F.text == "🛑 Остановить поиск")
@dp.message(F.text == "🚪 Выйти из чата")
@dp.message(Command("stop"))
async def stop_chat(msg: Message):
    await _end_session(msg.from_user.id, reason="stop")
    await msg.answer("Сессия завершена. Нажми кнопку когда захочешь снова.", reply_markup=main_kb())


async def _end_session(user_id: int, reason: str = "stop"):
    partner_id = await matcher.get_partner(user_id)
    await matcher.end_session(user_id)

    if partner_id:
        if reason == "next":
            text = "Собеседник перешёл к следующему. Нажми кнопку чтобы найти нового 👇"
        else:
            text = "Собеседник покинул чат. Нажми кнопку чтобы найти нового 👇"
        try:
            await bot.send_message(partner_id, text, reply_markup=main_kb())
            # Показываем кнопку жалобы партнёру
            await bot.send_message(partner_id, "Хочешь пожаловаться на собеседника?", reply_markup=report_kb(user_id))
        except Exception:
            pass


# ─── Пересылка сообщений ──────────────────────────────────────────────────────

@dp.message(F.text & ~F.text.startswith("/"))
async def relay_text(msg: Message):
    await _relay(msg)

@dp.message(F.photo)
async def relay_photo(msg: Message):
    await _relay(msg)

@dp.message(F.sticker)
async def relay_sticker(msg: Message):
    await _relay(msg)

@dp.message(F.voice)
async def relay_voice(msg: Message):
    await _relay(msg)

@dp.message(F.video_note)
async def relay_video_note(msg: Message):
    await _relay(msg)

async def _relay(msg: Message):
    user_id = msg.from_user.id
    partner_id = await matcher.get_partner(user_id)

    if not partner_id:
        await msg.answer("Ты не в чате. Нажми «Найти собеседника».", reply_markup=main_kb())
        return

    # Счётчик сообщений для модерации
    await matcher.increment_message_count(user_id)

    try:
        await bot.copy_message(
            chat_id=partner_id,
            from_chat_id=msg.chat.id,
            message_id=msg.message_id
        )
    except Exception as e:
        logger.error(f"Relay error: {e}")
        await _end_session(user_id, reason="error")
        await msg.answer("Собеседник недоступен. Начни новый поиск.", reply_markup=main_kb())


# ─── Жалобы ───────────────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("report:"))
async def handle_report(call: CallbackQuery):
    _, reported_id = call.data.split(":")
    reported_id = int(reported_id)
    reporter_id = call.from_user.id

    count = await matcher.add_report(reported_id, reporter_id)
    await call.message.edit_reply_markup()

    if count >= 3:
        await matcher.ban_user(reported_id, hours=24)
        logger.info(f"User {reported_id} banned after {count} reports")

    await call.answer("Жалоба отправлена. Спасибо!", show_alert=False)


@dp.callback_query(F.data == "report:skip")
async def skip_report(call: CallbackQuery):
    await call.message.edit_reply_markup()
    await call.answer()


# ─── Запуск ───────────────────────────────────────────────────────────────────

async def main():
    logger.info("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
