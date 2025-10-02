import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, MediaGroup
from aiogram.filters import CommandStart, Command
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
    # Обработка deep link
    args = message.get_args()
    if args:
        referee_id = args
        user_id = message.from_user.id
        async with aiosqlite.connect("users.db") as db:
            await db.execute("INSERT OR IGNORE INTO referrals (user_id, referee_id) VALUES (?, ?)", (user_id, referee_id))
            await db.commit()
    
    await start_command(message)

async def start_command(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Курьер"), KeyboardButton("Дроповод"), KeyboardButton("Реф. Система"))
    await message.answer("Какую именно должность Вы хотите занять?", reply_markup=markup)

@dp.message(lambda message: message.text in ["Курьер", "Дроповод"])
async def role_selected(message: types.Message):
    role = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, username, role, status) VALUES (?, ?, ?, ?)",
                        (user_id, username, role, "pending"))
        await db.commit()

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Заполнить анкету"), KeyboardButton("Назад"))

    if role == "Курьер":
        await message.answer("АНКЕТА КУРЬЕР!!!\n\n1. ФИО\n2. Дата рождения\n3. Город проживания, адрес (полный)\n4. В какие ближайшие города от места проживания можешь выезжать для работы?\n5. Скан паспорта (Основная страница + прописка) + последняя страница о ранее выданных паспортах (если имеется)\n6. Имеются ли карты Альфы и ОТП банка? (Необходимо для работы)\n7. Имеются ли судимости? (Активные, погашенные)\n8. Необходимо приложить видео к анкете, где вы выходите из квартиры показываете номер, спускаетесь во двор и показываете табличку дома (Видео необходимо в целях безопасности)\n9. Вы учитесь или работаете?\n10. Имеется ли телефон на базе Android? Если да, какая марка?", reply_markup=markup)
    else:
        await message.answer("АНКЕТА ДРОПОВОД!!!\n\n1. Имели ли вы опыт в данной профессии и данному направлению?\n2. Какое количество людей вы можете приводить за неделю?\n3. Примерный возрастной диапазон курьеров?\n4. Есть ли у вас депозит?\n5. Будете ли вы курировать курьеров или предоставите это нашей команде?\n6. Вы понимаете суть и ответственность работы с которой вам пришлось столкнуться?", reply_markup=markup)
    
    await message.answer("Отлично! Осталось только заполнить анкету", reply_markup=markup)

@dp.message(lambda message: message.text == "Назад")
async def go_back(message: types.Message):
    await start_command(message)

@dp.message(lambda message: message.text == "Реф. Система")
async def ref_system(message: types.Message):
    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    await message.answer(f"Ваша реферальная ссылка: {ref_link}")

@dp.message(lambda message: message.text == "Заполнить анкету")
async def start_application(message: types.Message):
    await message.answer("Отправьте анкету в одном сообщении (текст + фото/видео, если требуется).")

@dp.message(lambda message: message.content_type in ['text', 'photo', 'video'])
async def handle_application(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        if not result:
            await message.answer("Сначала выберите должность!")
            return
        role = result[0]
        await db.execute("UPDATE users SET application = ? WHERE user_id = ?", (message.text or "Файлы", user_id))
        await db.commit()

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"reject_{user_id}")
        ]
    ])

    media = MediaGroup()
    caption = f"Отправил заявку: @{username}\nДолжность: {role}\nКак заполнена анкета: {message.text or 'Файлы'}"
    
    if message.photo:
        for photo in message.photo:
            media.attach_photo(photo.file_id)
    if message.video:
        media.attach_video(message.video.file_id)
    
    if media.media:
        # Добавляем подпись к первому медиа-файлу
        media.media[0].caption = caption
        await bot.send_media_group(GROUP_ID, media=media)
        # Отправляем кнопки отдельным сообщением
        await bot.send_message(GROUP_ID, "Рассмотреть заявку:", reply_markup=markup)
    else:
        await bot.send_message(GROUP_ID, caption, reply_markup=markup)
    
    await message.answer("Ваша анкета принята в работу, ожидайте обратной связи")

@dp.callback_query(lambda callback: callback.data.startswith("approve_") or callback.data.startswith("reject_"))
async def process_application(callback_query: types.CallbackQuery):
    action, user_id = callback_query.data.split("_")
    user_id = int(user_id)
    async with aiosqlite.connect("users.db") as db:
        if action == "approve":
            await db.execute("UPDATE users SET status = ?, approved_date = ? WHERE user_id = ?",
                            ("approved", datetime.now().strftime("%d/%m/%Y"), user_id))
            await bot.send_message(user_id, f"Ваша анкета рассмотрена! Вы приняты, отпишитесь по данным контактам для дальнейшего сотрудничества — {ADMIN_CONTACT}")
        else:
            await db.execute("UPDATE users SET status = ? WHERE user_id = ?", ("rejected", user_id))
            await bot.send_message(user_id, "Ваша заявка рассмотрена! К сожалению, мы вынуждены вам отказать, сожалеем.")
        await db.commit()
    
    # Убираем кнопки после обработки
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except:
        pass  # Если не удалось убрать кнопки (например, для медиагруппы)
    
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
    if message.chat.id == GROUP_ID:
        return  # Игнорируем все сообщения в группе, кроме команд

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
