import os
import sqlite3
import logging
from datetime import datetime
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

# ========== НАСТРОЙКИ ==========
TOKEN = "8680724321:AAGmcU8I5Z1T9d8kHrqCS5qiZpmLpvPnLY0"  # ← ЗАМЕНИ НА СВОЙ ТОКЕН!
ADMIN_USERNAME = "ARSTION"

# Состояния для меню
ADD_NAME, DELETE_NAME = range(2)

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_database.db')

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            role TEXT,
            balance INTEGER DEFAULT 0,
            registered_at TEXT,
            custom_rate INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            promoter_id INTEGER,
            created_at TEXT,
            confirmed_at TEXT,
            is_confirmed BOOLEAN DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promoter_id INTEGER,
            amount INTEGER,
            created_at TEXT,
            list_item_id INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS monthly_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promoter_id INTEGER,
            year_month TEXT,
            confirmed_count INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            UNIQUE(promoter_id, year_month)
        )
    ''')
    conn.commit()
    conn.close()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_current_year_month():
    return datetime.now().strftime("%Y-%m")

def get_rate_for_count(confirmed_count):
    if confirmed_count >= 60:
        return 150
    elif confirmed_count >= 30:
        return 130
    else:
        return 120

def update_monthly_stats(promoter_id, confirmed_count_increment=1):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    year_month = get_current_year_month()
    cur.execute('''
        INSERT INTO monthly_stats (promoter_id, year_month, confirmed_count, total_earned)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(promoter_id, year_month) DO UPDATE SET
        confirmed_count = confirmed_count + ?
    ''', (promoter_id, year_month, confirmed_count_increment, 0, confirmed_count_increment))
    conn.commit()
    conn.close()

def get_promoter_monthly_stats(promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    year_month = get_current_year_month()
    cur.execute('''
        SELECT confirmed_count, total_earned 
        FROM monthly_stats 
        WHERE promoter_id = ? AND year_month = ?
    ''', (promoter_id, year_month))
    result = cur.fetchone()
    conn.close()
    if result:
        return result[0], result[1]
    return 0, 0

# ========== ДЕКОРАТОРЫ ==========
def role_required(required_role):
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
            result = cur.fetchone()
            conn.close()
            if not result:
                await update.message.reply_text("❌ Вы не зарегистрированы.")
                return
            if result[0] != required_role:
                await update.message.reply_text("⛔ У вас нет доступа.")
                return
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator

async def get_admin_id(context):
    try:
        admin = await context.bot.get_chat(f"@{ADMIN_USERNAME}")
        return admin.id
    except:
        return None

def admin_required(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        admin_id = await get_admin_id(context)
        if admin_id and user_id == admin_id:
            return await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("⛔ Только администратор.")
            return
    return wrapper

# ========== КОМАНДЫ ==========
async def start(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    
    if not user:
        await update.message.reply_text(
            "👋 Добро пожаловать!\nВаш аккаунт не активирован. Обратитесь к администратору.\n"
            f"Ваш ID: {user_id}"
        )
        admin_id = await get_admin_id(context)
        if admin_id:
            await context.bot.send_message(admin_id, f"🔔 Новый пользователь: @{username} (ID: {user_id})")
    else:
        role = user[0]
        if role == 'promoter':
            await show_promoter_menu(update, context)
        else:
            await show_cashier_menu(update, context)

async def show_promoter_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📋 Мои списки", callback_data='my_lists')],
        [InlineKeyboardButton("➕ Добавить человека", callback_data='add_person')],
        [InlineKeyboardButton("❌ Удалить человека", callback_data='delete_person')],
        [InlineKeyboardButton("💰 Моя статистика", callback_data='my_stats')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("🔧 Меню промоутера:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("🔧 Меню промоутера:", reply_markup=reply_markup)

async def show_cashier_menu(update, context):
    await update.message.reply_text(
        "🔍 Режим кассира\n\nПросто отправьте мне Фамилию Имя человека."
    )

async def promoter_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == 'my_lists':
        await show_my_lists(query, context)
    elif query.data == 'add_person':
        await query.edit_message_text("✍️ Введите Фамилию Имя:")
        return ADD_NAME
    elif query.data == 'delete_person':
        await query.edit_message_text("🗑 Введите Фамилию Имя для удаления:")
        return DELETE_NAME
    elif query.data == 'my_stats':
        await show_stats(query, context)

async def show_my_lists(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    if not promoter:
        await query.edit_message_text("Ошибка.")
        return
    cur.execute("SELECT full_name, is_confirmed FROM lists WHERE promoter_id = ?", (promoter[0],))
    people = cur.fetchall()
    conn.close()
    if not people:
        await query.edit_message_text("📭 Пусто.")
        return
    text = "📋 Ваш список:\n\n"
    for name, status in people:
        text += f"{'✅' if status else '⏳'} {name}\n"
    await query.edit_message_text(text)

async def show_stats(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, balance FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    if not promoter:
        await query.edit_message_text("Ошибка.")
        return
    promoter_id, balance = promoter
    monthly_confirmed, monthly_earned = get_promoter_monthly_stats(promoter_id)
    cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ?", (promoter_id,))
    total_added = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ? AND is_confirmed = 1", (promoter_id,))
    total_converted = cur.fetchone()[0]
    conn.close()
    conv_percent = (total_converted / total_added * 100) if total_added > 0 else 0
    current_rate = get_rate_for_count(monthly_confirmed)
    text = (
        f"💰 Баланс: {balance} руб.\n"
        f"📊 За этот месяц:\n• Подтверждено: {monthly_confirmed} чел.\n"
        f"• Ставка: {current_rate} руб./чел.\n"
        f"📈 Всего: {total_converted}/{total_added} ({conv_percent:.0f}%)"
    )
    await query.edit_message_text(text)

async def add_person_start(update, context):
    return ADD_NAME

async def add_person_get_name(update, context):
    full_name = update.message.text.strip()
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    if not promoter:
        await update.message.reply_text("Ошибка.")
        return ConversationHandler.END
    cur.execute("INSERT INTO lists (full_name, promoter_id, created_at, is_confirmed) VALUES (?, ?, ?, ?)",
                (full_name, promoter[0], datetime.now().isoformat(), 0))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {full_name} добавлен!")
    return ConversationHandler.END

async def delete_person_start(update, context):
    return DELETE_NAME

async def delete_person_get_name(update, context):
    full_name = update.message.text.strip()
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    if not promoter:
        await update.message.reply_text("Ошибка.")
        return ConversationHandler.END
    cur.execute("DELETE FROM lists WHERE full_name = ? AND promoter_id = ? AND is_confirmed = 0", 
                (full_name, promoter[0]))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🗑 {full_name} удален" if cur.rowcount > 0 else f"❌ {full_name} не найден")
    return ConversationHandler.END

@role_required('cashier')
async def check_person(update, context):
    full_name = update.message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT l.id, l.full_name, u.telegram_id, u.id 
        FROM lists l
        JOIN users u ON l.promoter_id = u.id
        WHERE l.full_name = ? AND l.is_confirmed = 0
    ''', (full_name,))
    result = cur.fetchone()
    conn.close()
    if not result:
        await update.message.reply_text("❌ Человека нет в списках.")
        return
    list_id, name, promoter_tg_id, promoter_db_id = result
    keyboard = [[InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{list_id}_{promoter_db_id}"),
                 InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    await update.message.reply_text(f"🔔 Найден: {name}\nПодтвердить?", reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text("❌ Отменено.")
        return
    _, list_id_str, promoter_db_id_str = query.data.split('_')
    list_id, promoter_db_id = int(list_id_str), int(promoter_db_id_str)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT is_confirmed FROM lists WHERE id = ?", (list_id,))
    if cur.fetchone()[0]:
        await query.edit_message_text("⚠️ Уже отмечен.")
        conn.close()
        return
    monthly_confirmed, _ = get_promoter_monthly_stats(promoter_db_id)
    rate = get_rate_for_count(monthly_confirmed)
    cur.execute("UPDATE lists SET is_confirmed = 1, confirmed_at = ? WHERE id = ?", 
                (datetime.now().isoformat(), list_id))
    cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (rate, promoter_db_id))
    cur.execute("INSERT INTO transactions (promoter_id, amount, created_at, list_item_id) VALUES (?, ?, ?, ?)",
                (promoter_db_id, rate, datetime.now().isoformat(), list_id))
    update_monthly_stats(promoter_db_id, 1)
    cur.execute('''UPDATE monthly_stats SET total_earned = total_earned + ? 
                   WHERE promoter_id = ? AND year_month = ?''', 
                (rate, promoter_db_id, get_current_year_month()))
    conn.commit()
    cur.execute("SELECT balance FROM users WHERE id = ?", (promoter_db_id,))
    new_balance = cur.fetchone()[0]
    conn.close()
    await query.edit_message_text(f"✅ Подтверждено! +{rate} руб.\nБаланс промоутера: {new_balance} руб.")
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM users WHERE id = ?", (promoter_db_id,))
    promoter_tg_id = cur.fetchone()
    conn.close()
    if promoter_tg_id:
        await context.bot.send_message(promoter_tg_id[0], f"🎉 Пришел {name}! +{rate} руб. Баланс: {new_balance} руб.")

@admin_required
async def set_role(update, context):
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Использование: /setrole <telegram_id> <promoter|cashier>")
            return
        tg_id, role = int(args[0]), args[1]
        if role not in ['promoter', 'cashier']:
            await update.message.reply_text("Роль: promoter или cashier")
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('''INSERT INTO users (telegram_id, role, registered_at) VALUES (?, ?, ?)
                       ON CONFLICT(telegram_id) DO UPDATE SET role = ?''', 
                    (tg_id, role, datetime.now().isoformat(), role))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Роль {role} назначена пользователю {tg_id}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

@admin_required
async def show_stats_all(update, context):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT u.telegram_id, u.username, u.balance, COALESCE(ms.confirmed_count, 0), COALESCE(ms.total_earned, 0)
        FROM users u
        LEFT JOIN monthly_stats ms ON u.id = ms.promoter_id AND ms.year_month = ?
        WHERE u.role = 'promoter'
        ORDER BY COALESCE(ms.confirmed_count, 0) DESC
    ''', (get_current_year_month(),))
    promoters = cur.fetchall()
    conn.close()
    if not promoters:
        await update.message.reply_text("Нет промоутеров.")
        return
    text = f"📊 Статистика за {get_current_year_month()}:\n\n"
    for tg_id, username, balance, confirmed, earned in promoters:
        text += f"@{username or tg_id}: {confirmed} чел., {earned} руб. (баланс: {balance} руб.)\n"
    await update.message.reply_text(text)

@admin_required
async def reset_month(update, context):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT u.id, u.telegram_id, u.username, ms.confirmed_count, ms.total_earned
        FROM users u
        LEFT JOIN monthly_stats ms ON u.id = ms.promoter_id AND ms.year_month = ?
        WHERE u.role = 'promoter'
    ''', (get_current_year_month(),))
    promoters = cur.fetchall()
    for p in promoters:
        if p[3]:
            try:
                await context.bot.send_message(p[1], f"📅 Итоги месяца: {p[3]} чел., {p[4]} руб. Начинаем новый месяц!")
            except:
                pass
    cur.execute("DELETE FROM monthly_stats WHERE year_month = ?", (get_current_year_month(),))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Месячная статистика обнулена.")

# ========== ЗАПУСК ==========
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CommandHandler("stats", show_stats_all))
    app.add_handler(CommandHandler("resetmonth", reset_month))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_person))
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(promoter_menu_callback, pattern='^(add_person|delete_person)$')],
        states={ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_person_get_name)],
                DELETE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_person_get_name)]},
        fallbacks=[]
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(promoter_menu_callback, pattern='^(my_lists|my_stats)$'))
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern='^(confirm_|cancel)'))
    print("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
