import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
import aiosqlite
from datetime import datetime

# БОТ_ДЛЯ_НАЕМА_КУРЬЕРОВ_ЯНДЕКС_ЛАВКА_ПО_РЕФКЕ

BOT_TOKEN = "7402061159:AAEDj-aeYOmQR3_7ZjEG4VEVXv60DJyqSp8"
GROUP_ID = -1002906964391
ADMIN_CONTACT = "@tron_cur"
ADMIN_IDS = [8306814702, 7129548835]

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
            payment_link TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS referrals (
            user_id INTEGER,
            referee_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')
        await db.commit()

async def check_user_status(user_id: int) -> tuple:
    """Проверяет статус пользователя и возвращает (is_rejected, has_application)"""
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user:
            return user[0] == "rejected", bool(user[1])
        return False, False

@dp.message(CommandStart())
async def handle_start_command(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    is_rejected, has_application = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application:
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    # Обработка deep link
    args = message.text.split()
    if len(args) > 1:
        referee_id = args[1]
        async with aiosqlite.connect("users.db") as db:
            await db.execute("INSERT OR IGNORE INTO referrals (user_id, referee_id) VALUES (?, ?)", (user_id, referee_id))
            await db.commit()
    
    await start_command(message)

async def start_command(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    is_rejected, has_application = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application:
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    # Исправленный синтаксис клавиатуры для aiogram 3.x
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Курьер"), KeyboardButton(text="Дроповод")],
            [KeyboardButton(text="Доп. Вакансии"), KeyboardButton(text="Реф. Система")]
        ],
        resize_keyboard=True
    )
    await message.answer("Какую именно должность Вы хотите занять?", reply_markup=markup)

@dp.message(lambda message: message.text in ["Курьер", "Дроповод", "Доп. Вакансии"])
async def role_selected(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    is_rejected, has_application = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application:
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    role = message.text
    username = message.from_user.username or "NoUsername"
    
    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, username, role, status) VALUES (?, ?, ?, ?)",
                        (user_id, username, role, "pending"))
        await db.commit()

    # Исправленный синтаксис клавиатуры
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Заполнить анкету"), KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )

    if role == "Курьер":
        await message.answer(
            "АНКЕТА КУРЬЕР!!!\n\n1. ФИО\n2. Дата рождения\n3. Город проживания, адрес (полный)\n4. В какие ближайшие города от места проживания можешь выезжать для работы?\n5. Скан паспорта (Основная страница + прописка) + последняя страница о ранее выданных паспортах (если имеется)\n6. Имеются ли карты Альфы и ОТП банка? (Необходимо для работы)\n7. Имеются ли судимости? (Активные, погашенные)\n8. Необходимо приложить видео к анкете, где вы выходите из квартиры показываете номер, спускаетесь во двор и показываете табличку дома (Видео необходимо в целях безопасности)\n9. Вы учитесь или работаете?\n10. Имеется ли телефон на базе Android? Если да, какая марка?",
            reply_markup=markup
        )
    elif role == "Дроповод":
        await message.answer(
            "АНКЕТА ДРОПОВОД!!!\n\n1. Имели ли вы опыт в данной профессии и данному направлению?\n2. Какое количество людей вы можете приводить за неделю?\n3. Примерный возрастной диапазон курьеров?\n4. Есть ли у вас депозит?\n5. Будете ли вы курировать курьеров или предоставите это нашей команде?\n6. Вы понимаете суть и ответственность работы с которой вам пришлось столкнуться?",
            reply_markup=markup
        )
    else:  # Доп. Вакансии
        await message.answer(
            "АНКЕТА ДОП. ВАКАНСИИ!!!\n\n1. Где ранее работали и со скольки лет?\n2. Приходилось ли ранее нарушать закон Уголовно или административно?\n3. Есть ли вы в розыске?\n4. С чем имели дело в «темках»?\n5. Вы можете назвать себя ответственным человеком?\n6. Есть ли у вас проблемы со сном?\n7. Алкоголь, наркотики употребляете?\n8. Есть ли у вас проблемы психологического плана?\n9. Есть водительское удостоверение?\n10. Учитесь ли вы где-либо и состоите ли на воинском учете?",
            reply_markup=markup
        )
    
    await message.answer("Отлично! Осталось только заполнить анкету", reply_markup=markup)

@dp.message(lambda message: message.text == "Назад")
async def go_back(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    is_rejected, has_application = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application:
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    await start_command(message)

@dp.message(lambda message: message.text == "Реф. Система")
async def ref_system(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    is_rejected, has_application = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application:
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    await message.answer(f"Ваша реферальная ссылка: {ref_link}")

@dp.message(lambda message: message.text == "Заполнить анкету")
async def start_application(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    is_rejected, has_application = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application:
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
            await message.answer("К сожалению, Вы получили отказ, поэтому больше не сможете пользоваться ботом, сожалеем.")
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

        # Получаем статистику пользователя
        cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referee_id = ?", (user_id,))
        referrals = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(amount) FROM payments WHERE user_id = ?", (user_id,))
        total_payments = (await cursor.fetchone())[0] or 0

    # Исправленный синтаксис инлайн-клавиатуры
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌", callback_data=f"reject_{user_id}")
            ]
        ]
    )

    caption = f"1. @{username} || TgID: {user_id}\n2. Выплачено: {total_payments} USDT\n3. Должность: {role}\n4. Приглашено: {referrals}\n\nКак заполнена анкета: {text_content or 'Только медиа'}"
    
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
    
    await message.answer("Ваша анкета принята в работу, ожидайте обратную связь!")

@dp.callback_query(lambda callback: callback.data.startswith("approve_") or callback.data.startswith("reject_"))
async def process_application(callback_query: types.CallbackQuery):
    data = callback_query.data
    if data.startswith("approve_"):
        user_id = int(data.split("_")[1])
        async with aiosqlite.connect("users.db") as db:
            await db.execute("UPDATE users SET status = ?, approved_date = ? WHERE user_id = ?",
                            ("approved", datetime.now().strftime("%d/%m/%Y"), user_id))
            await db.commit()
        await bot.send_message(user_id, "Ваша анкета рассмотрена! Вы приняты, ожидайте обратную связь от куратора.")
    elif data.startswith("reject_"):
        user_id = int(data.split("_")[1])
        async with aiosqlite.connect("users.db") as db:
            await db.execute("UPDATE users SET status = ? WHERE user_id = ?", ("rejected", user_id))
            await db.commit()
        await bot.send_message(user_id, "К сожалению, Вы получили отказ, Вы больше не сможете пользоваться ботом")
    
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
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Недостаточно прав для данной команды")
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
            f"2. Выплачено: {total_payments} USDT\n"
            f"3. Должность: {user[1]}\n"
            f"4. Приглашено: {referrals}"
        )

@dp.message(Command("zp"))
async def zp_command(message: types.Message):
    if message.chat.id != GROUP_ID:
        return
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Недостаточно прав для данной команды")
        return
    
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 3:
            raise ValueError("Недостаточно аргументов")
        
        username = parts[1].replace("@", "")
        amount = int(parts[2])
        payment_link = parts[3] if len(parts) > 3 else ""
        
        # Проверка ссылки (если предоставлена)
        if payment_link and not re.match(r"^https://t\.me/share/url\?url=", payment_link):
            await message.answer("Ошибка: ссылка должна быть в формате https://t.me/share/url?url=...")
            return
            
    except ValueError as e:
        await message.answer("Формат: /zp @username сумма [ссылка_на_чек]")
        return

    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        user = await cursor.fetchone()
        if not user:
            await message.answer("❌ человек отсутствует в боте")
            return
        
        user_id = user[0]
        await db.execute("INSERT INTO payments (user_id, amount, payment_link) VALUES (?, ?, ?)", 
                        (user_id, amount, payment_link or None))
        await db.commit()
        
        if payment_link:
            await bot.send_message(user_id, f"Вам отправлен чек на {amount} USDT: {payment_link}")
        
        await message.answer(f"✅ Чек на {amount} USDT отправлен @{username}")

@dp.message(Command("zpall"))
async def zpall_command(message: types.Message):
    if message.chat.id != GROUP_ID:
        return
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⚠️ Недостаточно прав для данной команды")
        return

    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("""
            SELECT u.username, p.amount
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            ORDER BY u.username
        """)
        payments = await cursor.fetchall()
        if not payments:
            await message.answer("Нет записей о выплатах")
            return

        user_payments = {}
        for username, amount in payments:
            if username not in user_payments:
                user_payments[username] = []
            user_payments[username].append(amount)

        total_usdt = sum(sum(amounts) for amounts in user_payments.values())
        report = ["#сверка"]
        for i, (username, amounts) in enumerate(user_payments.items(), 1):
            total = sum(amounts)
            amounts_str = "+".join(str(a) for a in amounts)
            report.append(f"{i}. @{username} — {amounts_str}={total} USDT")
        report.append(f"\nИтого: {total_usdt} USDT")
        
        await message.answer("\n".join(report))

@dp.message()
async def ignore_non_commands(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем статус пользователя
    is_rejected, has_application = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application:
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    if message.chat.id == GROUP_ID:
        return  # Игнорируем все не-команды в группе
    
    # Проверяем, выбрал ли пользователь должность
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user or not user[0]:
            await message.answer("⛔️ Пожалуйста, выберите должность")
            return

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
