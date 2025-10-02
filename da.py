import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InputMediaPhoto, InputMediaVideo  # MediaGroup заменен на InputMedia
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
import aiosqlite
from datetime import datetime

BOT_TOKEN = "7402061159:AAEDj-aeYOmQR3_7ZjEG4VEVXv60DJyqSp8"
GROUP_ID = -1002906964391
ADMIN_CONTACT = "@tron_cur"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def init_db():
    async with aiosqlite.connect("users.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            application TEXT,
            status TEXT,
            approved_date TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS payments (
            user_id INTEGER,
            amount INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS referrals (
            user_id INTEGER,
            referee_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')
        await db.commit()

@dp.message(CommandStart())
async def handle_start_command(message: types.Message):
    user_id = message.from_user.id
    # Получаем аргументы из deep link
    args = message.text.split()
    referee_id = None
    if len(args) > 1:
        referee_id = args[1]
    
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[1]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
        if referee_id:
            await db.execute("INSERT OR IGNORE INTO referrals (user_id, referee_id) VALUES (?, ?)", (user_id, referee_id))
            await db.commit()
    await start_command(message)

async def start_command(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[1]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton(text="Курьер"), KeyboardButton(text="Дроповод"), KeyboardButton(text="Реф. Система"))
    await message.answer("Какую именно должность Вы хотите занять?", reply_markup=markup)

@dp.message(lambda message: message.text in ["Курьер", "Дроповод"])
async def role_selected(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[1]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
    
    role = message.text
    username = message.from_user.username or "NoUsername"
    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, username, role, status) VALUES (?, ?, ?, ?)",
                        (user_id, username, role, "pending"))
        await db.commit()

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton(text="Заполнить анкету"), KeyboardButton(text="Назад"))

    if role == "Курьер":
        await message.answer(
            "АНКЕТА КУРЬЕР!!!\n\n1. ФИО\n2. Дата рождения\n3. Город проживания, адрес (полный)\n4. В какие ближайшие города от места проживания можешь выезжать для работы?\n5. Скан паспорта (Основная страница + прописка) + последняя страница о ранее выданных паспортах (если имеется)\n6. Имеются ли карты Альфы и ОТП банка? (Необходимо для работы)\n7. Имеются ли судимости? (Активные, погашенные)\n8. Необходимо приложить видео к анкете, где вы выходите из квартиры показываете номер, спускаетесь во двор и показываете табличку дома (Видео необходимо в целях безопасности)\n9. Вы учитесь или работаете?\n10. Имеется ли телефон на базе Android? Если да, какая марка?",
            reply_markup=markup
        )
    else:
        await message.answer(
            "АНКЕТА ДРОПОВОД!!!\n\n1. Имели ли вы опыт в данной профессии и данному направлению?\n2. Какое количество людей вы можете приводить за неделю?\n3. Примерный возрастной диапазон курьеров?\n4. Есть ли у вас депозит?\n5. Будете ли вы курировать курьеров или предоставите это нашей команде?\n6. Вы понимаете суть и ответственность работы с которой вам пришлось столкнуться?",
            reply_markup=markup
        )
    
    await message.answer("Отлично! Осталось только заполнить анкету", reply_markup=markup)

@dp.message(lambda message: message.text == "Назад")
async def go_back(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[1]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
    await start_command(message)

@dp.message(lambda message: message.text == "Реф. Система")
async def ref_system(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[1]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
    
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    await message.answer(f"Ваша реферальная ссылка: {ref_link}")

@dp.message(lambda message: message.text == "Заполнить анкету")
async def start_application(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[1]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
    await message.answer("Отправьте анкету в одном сообщении (текст + фото/видео, если требуется).")

@dp.message(lambda message: message.content_type in ['text', 'photo', 'video'])
async def handle_application(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, role, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[2]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
        if not user or not user[1]:
            await message.answer("⛔️ Пожалуйста, выберите должность")
            return
        
        role = user[1]
        username = message.from_user.username or "NoUsername"
        text_content = message.text or ""
        await db.execute("UPDATE users SET application = ? WHERE user_id = ?", (text_content or "Медиа", user_id))
        await db.commit()

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"reject_{user_id}")
        ]
    ])

    caption = f"Отправил заявку: @{username}\nДолжность: {role}\nКак заполнена анкета: {text_content or 'Только медиа'}"
    
    # Отправляем медиа или текст в группу
    try:
        if message.photo:
            # Берем фото с самым высоким качеством (последний элемент в списке)
            photo = message.photo[-1]
            await bot.send_photo(
                GROUP_ID, 
                photo.file_id,
                caption=caption,
                reply_markup=markup
            )
        elif message.video:
            await bot.send_video(
                GROUP_ID,
                message.video.file_id,
                caption=caption,
                reply_markup=markup
            )
        else:
            await bot.send_message(
                GROUP_ID,
                caption,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Ошибка отправки в группу: {e}")
        await message.answer("Произошла ошибка при отправке анкеты. Попробуйте позже.")
        return
    
    await message.answer("Ваша анкета принята в работу, ожидайте обратной связи")

@dp.callback_query(lambda callback: callback.data.startswith("approve_") or callback.data.startswith("reject_"))
async def process_application(callback_query: types.CallbackQuery):
    data = callback_query.data
    if data.startswith("approve_"):
        user_id = int(data.split("_")[1])
        async with aiosqlite.connect("users.db") as db:
            await db.execute("UPDATE users SET status = ?, approved_date = ? WHERE user_id = ?",
                            ("approved", datetime.now().strftime("%d/%m/%Y"), user_id))
            await db.commit()
        await bot.send_message(user_id, f"Ваша анкета рассмотрена! Вы приняты, отпишитесь по данным контактам для дальнейшего сотрудничества — {ADMIN_CONTACT}")
    elif data.startswith("reject_"):
        user_id = int(data.split("_")[1])
        async with aiosqlite.connect("users.db") as db:
            await db.execute("UPDATE users SET status = ? WHERE user_id = ?", ("rejected", user_id))
            await db.commit()
        await bot.send_message(user_id, "Вы получили отказ, Вы больше не сможете пользоваться ботом")
    
    # Убираем кнопки после обработки
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
    
    await callback_query.answer()

@dp.message(Command("info"))
async def info_command(message: types.Message):
    if message.chat.id != GROUP_ID:
        return
    try:
        username = message.text.split()[1].replace("@", "")
    except IndexError:
        await message.answer("Укажите username: /info @username")
        return

    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT user_id, role, status FROM users WHERE username = ?", (username,))
        user = await cursor.fetchone()
        if not user:
            await message.answer("❌ человек отсутствует в боте")
            return
        if user[2] == "rejected":
            await message.answer("❌ заявка пользователя была отклонена")
            return

        cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referee_id = ?", (user[0],))
        referrals = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(amount) FROM payments WHERE user_id = ?", (user[0],))
        total_payments = (await cursor.fetchone())[0] or 0

        await message.answer(
            f"1. @{username} || TgID: {user[0]}\n"
            f"2. Всего выплачено: {total_payments} USDT\n"
            f"3. Должность: {user[1]}\n"
            f"4. Приглашено: {referrals}"
        )

@dp.message(Command("zp"))
async def zp_command(message: types.Message):
    if message.chat.id != GROUP_ID:
        return
    try:
        _, username, amount = message.text.split()
        username = username.replace("@", "")
        amount = int(amount)
    except ValueError:
        await message.answer("Формат: /zp @username сумма")
        return

    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        user = await cursor.fetchone()
        if not user:
            await message.answer("❌ человек отсутствует в боте")
            return
        await db.execute("INSERT INTO payments (user_id, amount) VALUES (?, ?)", (user[0], amount))
        await db.commit()
        await message.answer(f"✅ Успешно добавлена выплата {amount} USDT для @{username}")

@dp.message()
async def ignore_non_commands(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, role, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user and user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user and user[2]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return
        if message.chat.id == GROUP_ID:
            return  # Игнорируем все не-команды в группе
        if not user or not user[1]:
            await message.answer("⛔️ Пожалуйста, выберите должность")
            return

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
