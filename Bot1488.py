import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram import F
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

@dp.message(CommandStart(deep_link=True))
async def handle_deep_link(message: types.Message):
    # Получаем аргументы из deep link
    args = message.get_args()
    if args:
        referee_id = args
        user_id = message.from_user.id
        async with aiosqlite.connect("users.db") as db:
            await db.execute("INSERT OR IGNORE INTO referrals (user_id, referee_id) VALUES (?, ?)", (user_id, referee_id))
            await db.commit()
    await start_command(message)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Курьер"), KeyboardButton("Дроповод"), KeyboardButton("Реф. Система"))
    await message.answer("Какую именно должность Вы хотите занять?", reply_markup=markup)

@dp.message(F.text.in_(["Курьер", "Дроповод"]))
async def role_selected(message: types.Message):
    role = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, username, role, status) VALUES (?, ?, ?, ?)",
                        (user_id, username, role, "pending"))
        await db.commit()

    if role == "Курьер":
        await message.answer("АНКЕТА КУРЬЕР!!!\n\n1. ФИО\n2. Дата рождения\n3. Город проживания, адрес (полный)\n4. В какие ближайшие города от места проживания можешь выезжать для работы?\n5. Скан паспорта (Основная страница + прописка) + последняя страница о ранее выданных паспортах (если имеется)\n6. Имеются ли карты Альфы и ОТП банка? (Необходимо для работы)\n7. Имеются ли судимости? (Активные, погашенные)\n8. Необходимо приложить видео к анкете, где вы выходите из квартиры показываете номер, спускаетесь во двор и показываете табличку дома (Видео необходимо в целях безопасности)\n9. Вы учитесь или работаете?\n10. Имеется ли телефон на базе Android? Если да, какая марка?")
    else:
        await message.answer("АНКЕТА ДРОПОВОД!!!\n\n1. Имели ли вы опыт в данной профессии и данному направлению?\n2. Какое количество людей вы можете приводить за неделю?\n3. Примерный возрастной диапазон курьеров?\n4. Есть ли у вас депозит?\n5. Будете ли вы курировать курьеров или предоставите это нашей команде?\n6. Вы понимаете суть и ответственность работы с которой вам пришлось столкнуться?")
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Заполнить анкету"))
    await message.answer("Отлично! Осталось только заполнить анкету", reply_markup=markup)

@dp.message(F.text == "Реф. Система")
async def ref_system(message: types.Message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await message.answer(f"Ваша реферальная ссылка: {ref_link}")

@dp.message(F.text == "Заполнить анкету")
async def start_application(message: types.Message):
    await message.answer("Отправьте анкету в одном сообщении (текст + фото/видео, если требуется).")

@dp.message(F.content_type.in_({types.ContentType.TEXT, types.ContentType.PHOTO, types.ContentType.VIDEO}))
async def handle_application(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        user_data = await cursor.fetchone()
        if not user_data:
            await message.answer("Сначала выберите должность!")
            return
        
        role = user_data[0]
        application_text = message.text or "Файлы"
        await db.execute("UPDATE users SET application = ? WHERE user_id = ?", (application_text, user_id))
        await db.commit()

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"reject_{user_id}")
        ]
    ])

    content = []
    if message.text:
        content.append(message.text)
    if message.photo:
        content.append(f"[Фото]")
    if message.video:
        content.append(f"[Видео]")

    application_content = '\n'.join(content) if content else "Файлы"
    
    # Отправляем сообщение в группу
    try:
        if message.photo:
            # Отправляем фото с подписью
            photo = message.photo[-1]
            await bot.send_photo(
                GROUP_ID, 
                photo.file_id,
                caption=f"{application_content}\nОтправил заявку: @{username}\nДолжность: {role}\nКак заполнена анкета: {application_text}",
                reply_markup=markup
            )
        elif message.video:
            # Отправляем видео с подписью
            await bot.send_video(
                GROUP_ID,
                message.video.file_id,
                caption=f"{application_content}\nОтправил заявку: @{username}\nДолжность: {role}\nКак заполнена анкета: {application_text}",
                reply_markup=markup
            )
        else:
            # Отправляем только текст
            await bot.send_message(
                GROUP_ID, 
                f"{application_content}\nОтправил заявку: @{username}\nДолжность: {role}\nКак заполнена анкета: {application_text}",
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Ошибка отправки в группу: {e}")
        await message.answer("Произошла ошибка при отправке анкеты. Попробуйте позже.")
        return

    await message.answer("Ваша анкета принята в работу, ожидайте обратной связи")

@dp.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
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
    await callback_query.message.edit_reply_markup(reply_markup=None)
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
        cursor = await db.execute("SELECT user_id, role, status, approved_date FROM users WHERE username = ?", (username,))
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
            f"Должность: {user[1]}\n"
            f"Стаж работы: работает с {user[3] or 'не одобрен'}\n"
            f"Рефералы: {referrals}\n"
            f"Выплачено всего: {total_payments} USDT\n"
            f"Telegram ID: {user[0]}"
        )

@dp.message(F.text.startswith("+выплата"))
async def add_payment(message: types.Message):
    if message.chat.id != GROUP_ID:
        return
    try:
        _, username, amount = message.text.split()
        username = username.replace("@", "")
        amount = int(amount)
    except ValueError:
        await message.answer("Формат: +выплата @username сумма")
        return

    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        user = await cursor.fetchone()
        if not user:
            await message.answer("❌ человек отсутствует в боте")
            return
        await db.execute("INSERT INTO payments (user_id, amount) VALUES (?, ?)", (user[0], amount))
        await db.commit()
        await message.answer(f"Выплата {amount} USDT добавлена для @{username}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
