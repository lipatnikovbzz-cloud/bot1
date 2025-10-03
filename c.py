import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto, InputMediaVideo
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
import aiosqlite
from datetime import datetime
from collections import defaultdict

BOT_TOKEN = "7402061159:AAEDj-aeYOmQR3_7ZjEG4VEVXv60DJyqSp8"
GROUP_ID = -1002906964391
ADMIN_CONTACT = "@tron_cur"
ADMIN_IDS = [8306814702, 7129548835]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище временных медиа по media_group_id
media_groups = defaultdict(list)

async def init_db():
    async with aiosqlite.connect("users.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            nickname TEXT,
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
    """Проверяет статус пользователя и возвращает (is_rejected, has_application, status)"""
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if user:
            return user[0] == "rejected", bool(user[1]), user[0]
        return False, False, None

async def get_profile_markup(user_id: int, status: str):
    """Создает клавиатуру в зависимости от статуса пользователя"""
    if status == "approved":
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Профиль")]],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Курьер"), KeyboardButton(text="Дроповод")],
                [KeyboardButton(text="Доп. Вакансии"), KeyboardButton(text="Реф. Система")]
            ],
            resize_keyboard=True
        )

@dp.message(CommandStart())
async def handle_start_command(message: types.Message):
    user_id = message.from_user.id
    
    # Для админов - только информационное сообщение, но не блокируем команду
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        # НЕ возвращаем return, чтобы команда обработалась дальше
    
    # Проверяем статус пользователя (только для не-админов)
    if user_id not in ADMIN_IDS:
        is_rejected, has_application, status = await check_user_status(user_id)
        if is_rejected:
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if has_application and status != "approved":
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
    
    # Для админов - только информационное сообщение
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    # Проверяем статус пользователя
    is_rejected, has_application, status = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application and status != "approved":
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    markup = await get_profile_markup(user_id, status)
    await message.answer("Какую именно должность Вы хотите занять?", reply_markup=markup)

@dp.message(lambda message: message.text in ["Курьер", "Дроповод", "Доп. Вакансии"])
async def role_selected(message: types.Message):
    user_id = message.from_user.id
    
    # Админам не нужно выбирать роль
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    # Проверяем статус пользователя
    is_rejected, has_application, status = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application and status != "approved":
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    role = message.text
    username = message.from_user.username or "NoUsername"
    
    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, username, role, status) VALUES (?, ?, ?, ?)",
                        (user_id, username, role, "pending"))
        await db.commit()

    # Клавиатура для заполнения анкеты
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
    
    # Админам не нужно возвращаться назад
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    # Проверяем статус пользователя
    is_rejected, has_application, status = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application and status != "approved":
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    await start_command(message)

@dp.message(lambda message: message.text == "Реф. Система")
async def ref_system(message: types.Message):
    user_id = message.from_user.id
    
    # Админам не нужна реф система
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    # Проверяем статус пользователя
    is_rejected, has_application, status = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application and status != "approved":
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    await message.answer(f"Ваша реферальная ссылка: {ref_link}")

@dp.message(lambda message: message.text == "Заполнить анкету")
async def start_application(message: types.Message):
    user_id = message.from_user.id
    
    # Админам не нужно заполнять анкету
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    # Проверяем статус пользователя
    is_rejected, has_application, status = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application and status != "approved":
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    await message.answer("Отправьте анкету в одном сообщении (текст + фото/видео, если требуется).")

@dp.message(lambda message: message.text == "Профиль")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    
    # Админам не нужен профиль пользователя
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT username, nickname, role, status FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await message.answer("⛔️ Вы не зарегистрированы. Нажмите /start")
            return
        if user[3] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        
        # УБИРАЕМ проверку на approved для тестирования
        # if user[3] != "approved":
        #     await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        #     return

        cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referee_id = ?", (user_id,))
        referrals = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(amount) FROM payments WHERE user_id = ?", (user_id,))
        total_payments = (await cursor.fetchone())[0] or 0

        profile_text = (
            f"Ник: {user[1] if user[1] else user[0]}\n"
            f"Выплачено: {total_payments} USDT\n"
            f"Должность: {user[2]}\n"
            f"Приглашено: {referrals}"
        )
        
        # Пытаемся отправить фото профиля
        try:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if photos.photos:
                await bot.send_photo(user_id, photos.photos[0][-1].file_id, caption=profile_text)
            else:
                await message.answer(profile_text)
        except Exception as e:
            logger.error(f"Ошибка при получении фото профиля: {e}")
            await message.answer(profile_text)

@dp.message(lambda message: message.text.startswith("+ник"))
async def change_nickname(message: types.Message):
    user_id = message.from_user.id
    
    # Админам не нужно менять ник
    if user_id in ADMIN_IDS:
        await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    # Проверяем статус пользователя
    is_rejected, has_application, status = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application and status != "approved":
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
    try:
        new_nickname = message.text.split(maxsplit=1)[1]
        async with aiosqlite.connect("users.db") as db:
            await db.execute("UPDATE users SET nickname = ? WHERE user_id = ?", (new_nickname, user_id))
            await db.commit()
            await message.answer(f"Ник успешно изменён на {new_nickname}")
    except IndexError:
        await message.answer("Формат: +ник новый_ник")

# Обработчик для медиагрупп (альбомов)
@dp.message(lambda message: message.media_group_id is not None)
async def handle_media_group(message: types.Message):
    """Собираем альбом из нескольких фото/видео"""
    media_groups[message.media_group_id].append(message)
    await asyncio.sleep(1.0)  # ждём немного, пока Telegram отправит все части альбома

    # Проверяем, что это последнее сообщение в группе
    if len(media_groups[message.media_group_id]) >= 2 or not message.caption:
        await process_application_media_group(message.media_group_id)

async def process_application_media_group(media_group_id):
    """Отправляем альбом одним сообщением в группу"""
    messages = media_groups.pop(media_group_id, [])
    if not messages:
        return

    first_msg = messages[0]
    user_id = first_msg.from_user.id
    username = first_msg.from_user.username or "NoUsername"
    
    # Проверяем статус
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, role, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user or not user[1]:
            await bot.send_message(user_id, "⛔️ Пожалуйста, выберите должность")
            return
        if user[0] == "rejected":
            await bot.send_message(user_id, "Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user[0] == "approved":
            await bot.send_message(user_id, "Вы уже прошли отбор, анкета не требуется повторно")
            return
        if user[2]:
            await bot.send_message(user_id, "Подождите пожалуйста, вы уже отправили анкету")
            return

        await db.execute("UPDATE users SET application = ? WHERE user_id = ?", ("МедиаГруппа", user_id))
        await db.commit()

    # Готовим альбом для отправки
    media_list = []
    for msg in messages:
        if msg.photo:
            media_list.append(InputMediaPhoto(media=msg.photo[-1].file_id))
        elif msg.video:
            media_list.append(InputMediaVideo(media=msg.video.file_id))

    # Добавляем подпись в первое медиа
    caption = f"@{username} отправил анкету с медиа (альбом)."
    media_list[0].caption = caption

    await bot.send_media_group(GROUP_ID, media_list)
    await bot.send_message(user_id, "Ваша анкета принята, ожидайте ответ от администрации.")

# Основной обработчик анкет (текст, одиночные фото/видео)
@dp.message(lambda message: message.content_type in ['text', 'photo', 'video'] and message.media_group_id is None)
async def handle_application(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"

    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT status, role, application FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()

        if not user or not user[1]:
            await message.answer("⛔️ Пожалуйста, выберите должность")
            return
        if user[0] == "rejected":
            await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
            return
        if user[0] == "approved":
            await message.answer("Вы уже прошли отбор, анкета не требуется повторно")
            return
        if user[2]:
            await message.answer("Подождите пожалуйста, вы уже отправили анкету")
            return

        text_content = message.caption or message.text or "Без текста"
        await db.execute("UPDATE users SET application = ? WHERE user_id = ?", (text_content, user_id))
        await db.commit()

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌", callback_data=f"reject_{user_id}")
            ]
        ]
    )

    caption = f"@{username} отправил анкету\n{text_content}"

    try:
        if message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=caption, reply_markup=markup)
        elif message.video:
            await bot.send_video(GROUP_ID, message.video.file_id, caption=caption, reply_markup=markup)
        else:
            await bot.send_message(GROUP_ID, caption, reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка отправки в группу: {e}")
        await message.answer("Ошибка при отправке анкеты. Попробуйте позже.")
        return

    await message.answer("✅ Ваша анкета отправлена. Ожидайте ответ от администрации.")

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
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Профиль")]],
            resize_keyboard=True
        )
        await bot.send_message(user_id, "Теперь вы можете просмотреть свой профиль", reply_markup=markup)
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

# КОМАНДЫ АДМИНОВ - здесь НЕТ проверки на блокировку админов
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
        cursor = await db.execute("SELECT user_id, role, status, nickname FROM users WHERE username = ?", (username,))
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

        display_name = f"@{username}" if not user[3] else user[3]
        await message.answer(
            f"1. {display_name} || TgID: {user[0]}\n"
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
        
        amount = int(parts[1])
        username = parts[2].replace("@", "")
        payment_link = parts[3] if len(parts) > 3 else ""
        
        # Проверка ссылки (если предоставлена)
        if payment_link and not re.match(r"^https://t\.me/share/url\?url=", payment_link):
            await message.answer("Ошибка: ссылка должна быть в формате https://t.me/share/url?url=...")
            return
            
    except ValueError as e:
        await message.answer("Формат: /zp сумма @username [ссылка_на_чек]")
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
            SELECT u.username, u.nickname, p.amount
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            ORDER BY u.username
        """)
        payments = await cursor.fetchall()
        if not payments:
            await message.answer("Нет записей о выплатах")
            return

        user_payments = {}
        for username, nickname, amount in payments:
            display_name = nickname or username
            if display_name not in user_payments:
                user_payments[display_name] = []
            user_payments[display_name].append(amount)

        total_usdt = sum(sum(amounts) for amounts in user_payments.values())
        report = ["#сверка"]
        for i, (username, amounts) in enumerate(user_payments.items(), 1):
            total = sum(amounts)
            amounts_str = "+".join(str(a) for a in amounts)
            report.append(f"{i}. @{username} — {amounts_str}={total} USDT")
        report.append(f"\nИтого: {total_usdt} USDT")
        
        await message.answer("\n".join(report))

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer("Для помощи обратитесь к администратору: @tron_cur")

@dp.message()
async def ignore_non_commands(message: types.Message):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        # Админам разрешаем только команды, остальные сообщения игнорируем
        if not message.text or not message.text.startswith("/"):
            await message.answer("Вы администратор. Используйте команды /info, /zp, /zpall в группе.")
        return
    
    # Проверяем статус пользователя
    is_rejected, has_application, status = await check_user_status(user_id)
    if is_rejected:
        await message.answer("Вы получили отказ, Вы больше не сможете пользоваться ботом")
        return
    if has_application and status != "approved":
        await message.answer("Подождите пожалуйста, вы уже отправили анкету")
        return
    
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
