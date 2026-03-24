import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== НАСТРОЙКИ ==========
TOKEN = "СЮДА_ТВОЙ_ТОКЕН"  # ← ЗАМЕНИ
ADMIN_ID = 355936751

DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_database.db')

# Состояния
ADD_NAME, DELETE_NAME = range(2)
ADMIN_ADD_EVENT, ADMIN_DELETE_EVENT = range(2, 4)
ADMIN_ADD_PROMOTER, ADMIN_DELETE_PROMOTER = range(4, 6)
ADMIN_RESET_BALANCE, ADMIN_VIEW_LISTS = range(6, 8)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            role TEXT,
            balance INTEGER DEFAULT 0
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            promoter_id INTEGER,
            event_id INTEGER,
            is_confirmed INTEGER DEFAULT 0,
            confirmed_at TEXT,
            FOREIGN KEY(event_id) REFERENCES events(id)
        )
    ''')
    
    cur.execute('INSERT OR IGNORE INTO users (telegram_id, role) VALUES (?, ?)', (ADMIN_ID, 'admin'))
    cur.execute('INSERT OR IGNORE INTO events (name, date, is_active) VALUES (?, ?, ?)', 
                ('Основное мероприятие', datetime.now().strftime("%Y-%m-%d"), 1))
    
    conn.commit()
    conn.close()

# ========== ВСПОМОГАТЕЛЬНЫЕ ==========
def get_rate(count):
    if count >= 60: return 150
    if count >= 30: return 130
    return 120

def get_monthly_count(promoter_id, event_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if event_id:
        cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ? AND event_id = ? AND is_confirmed = 1", 
                    (promoter_id, event_id))
    else:
        cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ? AND is_confirmed = 1", (promoter_id,))
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_promoter_balance(promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE id = ?", (promoter_id,))
    balance = cur.fetchone()[0]
    conn.close()
    return balance

def get_active_events():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, date FROM events WHERE is_active = 1 ORDER BY date")
    events = cur.fetchall()
    conn.close()
    return events

def get_all_promoters():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, telegram_id, username, balance FROM users WHERE role = 'promoter'")
    promoters = cur.fetchall()
    conn.close()
    return promoters

def get_promoter_lists(promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT l.full_name, e.name, l.is_confirmed, l.confirmed_at 
        FROM lists l
        JOIN events e ON l.event_id = e.id
        WHERE l.promoter_id = ?
        ORDER BY l.is_confirmed, l.id DESC
    ''', (promoter_id,))
    lists = cur.fetchall()
    conn.close()
    return lists

# ========== ГЛАВНОЕ МЕНЮ ==========
async def start(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    
    if not user:
        await update.message.reply_text(f"👋 Добро пожаловать!\nВаш ID: {user_id}\nОжидайте назначения роли.")
        await context.bot.send_message(ADMIN_ID, f"🔔 Новый пользователь: @{username} (ID: {user_id})")
        return
    
    role = user[0]
    
    if role == 'admin':
        await show_admin_menu(update, context)
    elif role == 'promoter':
        await show_promoter_menu(update, context)
    elif role == 'cashier':
        await update.message.reply_text("🔍 КАССИР\n\nПросто отправьте Фамилию Имя человека.")

# ========== МЕНЮ АДМИНИСТРАТОРА ==========
async def show_admin_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Список промоутеров", callback_data="admin_promoters")],
        [InlineKeyboardButton("📋 Списки промоутеров", callback_data="admin_view_lists")],
        [InlineKeyboardButton("💰 Сбросить баланс", callback_data="admin_reset_balance")],
        [InlineKeyboardButton("➕ Добавить промоутера", callback_data="admin_add_promoter")],
        [InlineKeyboardButton("❌ Удалить промоутера", callback_data="admin_delete_promoter")],
        [InlineKeyboardButton("📅 Мероприятия", callback_data="admin_events")],
        [InlineKeyboardButton("🔄 Сбросить месяц", callback_data="admin_reset_month")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "👑 *АДМИН-ПАНЕЛЬ*\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "👑 *АДМИН-ПАНЕЛЬ*\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ========== МЕНЮ ПРОМОУТЕРА ==========
async def show_promoter_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📋 Мои списки", callback_data="my_lists")],
        [InlineKeyboardButton("➕ Добавить человека", callback_data="add_person")],
        [InlineKeyboardButton("❌ Удалить человека", callback_data="delete_person")],
        [InlineKeyboardButton("💰 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🔧 *МЕНЮ ПРОМОУТЕРА*\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🔧 *МЕНЮ ПРОМОУТЕРА*\n\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ========== АДМИН: СТАТИСТИКА ==========
async def admin_stats(update, context):
    promoters = get_all_promoters()
    
    if not promoters:
        await update.callback_query.edit_message_text("📭 Нет зарегистрированных промоутеров")
        return
    
    events = get_active_events()
    
    text = "📊 *СТАТИСТИКА ПРОМОУТЕРОВ*\n\n"
    
    for pid, tg_id, username, balance in promoters:
        name = f"@{username}" if username else str(tg_id)
        monthly = get_monthly_count(pid)
        rate = get_rate(monthly)
        
        # Статистика по мероприятиям
        event_stats = ""
        for event in events:
            event_id, event_name, _ = event
            event_count = get_monthly_count(pid, event_id)
            if event_count > 0:
                event_stats += f"  • {event_name}: {event_count} чел.\n"
        
        text += f"👤 *{name}*\n"
        text += f"💰 Баланс: {balance} руб.\n"
        text += f"📊 За месяц: {monthly} чел. (ставка {rate} руб.)\n"
        if event_stats:
            text += f"📅 По мероприятиям:\n{event_stats}"
        text += "──────────────────\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]]
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ========== АДМИН: СПИСОК ПРОМОУТЕРОВ ==========
async def admin_promoters(update, context):
    promoters = get_all_promoters()
    
    if not promoters:
        await update.callback_query.edit_message_text("📭 Нет промоутеров")
        return
    
    text = "👥 *СПИСОК ПРОМОУТЕРОВ*\n\n"
    for pid, tg_id, username, balance in promoters:
        name = f"@{username}" if username else str(tg_id)
        monthly = get_monthly_count(pid)
        text += f"• {name}\n"
        text += f"  ID: {tg_id}\n"
        text += f"  Баланс: {balance} руб.\n"
        text += f"  За месяц: {monthly} чел.\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]]
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ========== АДМИН: ПРОСМОТР СПИСКОВ ПРОМОУТЕРА ==========
async def admin_view_lists(update, context):
    promoters = get_all_promoters()
    
    if not promoters:
        await update.callback_query.edit_message_text("📭 Нет промоутеров")
        return
    
    # Создаем кнопки для выбора промоутера
    keyboard = []
    for pid, tg_id, username, _ in promoters:
        name = f"@{username}" if username else str(tg_id)
        keyboard.append([InlineKeyboardButton(name, callback_data=f"admin_view_promoter_{pid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")])
    
    await update.callback_query.edit_message_text(
        "👥 *Выберите промоутера для просмотра списков:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_view_promoter_lists(update, context, promoter_id):
    lists = get_promoter_lists(promoter_id)
    
    if not lists:
        await update.callback_query.edit_message_text("📭 У этого промоутера нет людей в списках")
        return
    
    # Получаем инфо о промоутере
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, username FROM users WHERE id = ?", (promoter_id,))
    promoter = cur.fetchone()
    conn.close()
    
    name = f"@{promoter[1]}" if promoter[1] else str(promoter[0])
    
    text = f"📋 *СПИСОК ПРОМОУТЕРА {name}*\n\n"
    
    for full_name, event_name, is_confirmed, confirmed_at in lists:
        status = "✅ ПРИШЕЛ" if is_confirmed else "⏳ ОЖИДАЕТ"
        if is_confirmed and confirmed_at:
            date = confirmed_at[:10] if confirmed_at else ""
            text += f"• {full_name} [{event_name}] - {status} ({date})\n"
        else:
            text += f"• {full_name} [{event_name}] - {status}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_view_lists")]]
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ========== АДМИН: СБРОС БАЛАНСА ==========
async def admin_reset_balance(update, context):
    promoters = get_all_promoters()
    
    if not promoters:
        await update.callback_query.edit_message_text("📭 Нет промоутеров")
        return
    
    keyboard = []
    for pid, tg_id, username, _ in promoters:
        name = f"@{username}" if username else str(tg_id)
        keyboard.append([InlineKeyboardButton(name, callback_data=f"admin_reset_balance_{pid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")])
    
    await update.callback_query.edit_message_text(
        "💰 *Выберите промоутера для сброса баланса:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_reset_balance_confirm(update, context, promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = 0 WHERE id = ?", (promoter_id,))
    cur.execute("SELECT telegram_id, username FROM users WHERE id = ?", (promoter_id,))
    promoter = cur.fetchone()
    conn.commit()
    conn.close()
    
    name = f"@{promoter[1]}" if promoter[1] else str(promoter[0])
    
    await update.callback_query.edit_message_text(f"✅ Баланс промоутера {name} обнулен")
    
    # Уведомляем промоутера
    await context.bot.send_message(promoter[0], "💰 Ваш баланс был обнулен администратором.")

# ========== АДМИН: ДОБАВЛЕНИЕ ПРОМОУТЕРА ==========
async def admin_add_promoter(update, context):
    await update.callback_query.edit_message_text("✍️ Введите Telegram ID промоутера (число):")
    return ADMIN_ADD_PROMOTER

async def admin_add_promoter_process(update, context):
    try:
        tg_id = int(update.message.text.strip())
        
        # Получаем username
        try:
            chat = await context.bot.get_chat(tg_id)
            username = chat.username
        except:
            username = None
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (telegram_id, username, role, balance) VALUES (?, ?, ?, 0)",
                    (tg_id, username, 'promoter'))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Промоутер {tg_id} добавлен")
        await context.bot.send_message(tg_id, "✅ Вам назначена роль *промоутера*!\nНапишите /start для начала работы.", parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    
    await show_admin_menu(update, context)
    return -1

# ========== АДМИН: УДАЛЕНИЕ ПРОМОУТЕРА ==========
async def admin_delete_promoter(update, context):
    promoters = get_all_promoters()
    
    if not promoters:
        await update.callback_query.edit_message_text("📭 Нет промоутеров")
        return
    
    keyboard = []
    for pid, tg_id, username, _ in promoters:
        name = f"@{username}" if username else str(tg_id)
        keyboard.append([InlineKeyboardButton(name, callback_data=f"admin_delete_promoter_{pid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")])
    
    await update.callback_query.edit_message_text(
        "❌ *Выберите промоутера для удаления:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_delete_promoter_confirm(update, context, promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, username FROM users WHERE id = ?", (promoter_id,))
    promoter = cur.fetchone()
    cur.execute("DELETE FROM users WHERE id = ?", (promoter_id,))
    conn.commit()
    conn.close()
    
    name = f"@{promoter[1]}" if promoter[1] else str(promoter[0])
    await update.callback_query.edit_message_text(f"✅ Промоутер {name} удален")
    
    try:
        await context.bot.send_message(promoter[0], "❌ Ваша роль промоутера была удалена администратором.")
    except:
        pass

# ========== АДМИН: МЕРОПРИЯТИЯ ==========
async def admin_events(update, context):
    events = get_active_events()
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить мероприятие", callback_data="admin_add_event")],
        [InlineKeyboardButton("❌ Удалить мероприятие", callback_data="admin_delete_event")]
    ]
    
    text = "📅 *МЕРОПРИЯТИЯ*\n\n"
    if events:
        for event in events:
            text += f"• {event[1]} ({event[2]})\n"
    else:
        text += "Нет активных мероприятий\n"
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")])
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_add_event(update, context):
    await update.callback_query.edit_message_text("✍️ Введите название мероприятия:")
    return ADMIN_ADD_EVENT

async def admin_add_event_process(update, context):
    name = update.message.text.strip()
    context.user_data['temp_event_name'] = name
    await update.message.reply_text("📅 Введите дату мероприятия (в формате ГГГГ-ММ-ДД):")
    return ADMIN_ADD_EVENT + 1

async def admin_add_event_date(update, context):
    date = update.message.text.strip()
    name = context.user_data.get('temp_event_name')
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO events (name, date, is_active) VALUES (?, ?, 1)", (name, date))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Мероприятие '{name}' добавлено на {date}")
    await show_admin_menu(update, context)
    return -1

async def admin_delete_event(update, context):
    events = get_active_events()
    
    if not events:
        await update.callback_query.edit_message_text("📭 Нет мероприятий для удаления")
        return
    
    keyboard = []
    for event in events:
        keyboard.append([InlineKeyboardButton(f"{event[1]} ({event[2]})", callback_data=f"admin_delete_event_{event[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_events")])
    
    await update.callback_query.edit_message_text(
        "❌ *Выберите мероприятие для удаления:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_delete_event_confirm(update, context, event_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM events WHERE id = ?", (event_id,))
    event = cur.fetchone()
    cur.execute("UPDATE events SET is_active = 0 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    
    await update.callback_query.edit_message_text(f"✅ Мероприятие '{event[0]}' удалено")

# ========== АДМИН: СБРОС МЕСЯЦА ==========
async def admin_reset_month(update, context):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Получаем промоутеров для уведомления
    cur.execute("SELECT telegram_id, username FROM users WHERE role = 'promoter'")
    promoters = cur.fetchall()
    
    # Сбрасываем все подтверждения
    cur.execute("UPDATE lists SET is_confirmed = 0, confirmed_at = NULL")
    conn.commit()
    conn.close()
    
    # Уведомляем промоутеров
    for tg_id, username in promoters:
        try:
            await context.bot.send_message(tg_id, "📅 *НОВЫЙ МЕСЯЦ НАЧАЛСЯ!*\n\nСтатистика обнулена. Удачи! 🚀", parse_mode='Markdown')
        except:
            pass
    
    await update.callback_query.edit_message_text("✅ Месяц сброшен. Статистика обнулена.")

# ========== ПРОМОУТЕР: МОИ СПИСКИ ==========
async def my_lists(update, context):
    user_id = update.callback_query.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    
    if not promoter:
        await update.callback_query.edit_message_text("Ошибка")
        return
    
    promoter_id = promoter[0]
    lists = get_promoter_lists(promoter_id)
    
    if not lists:
        await update.callback_query.edit_message_text("📭 Ваш список пуст")
        return
    
    text = "📋 *ВАШ СПИСОК*\n\n"
    for full_name, event_name, is_confirmed, confirmed_at in lists:
        status = "✅" if is_confirmed else "⏳"
        text += f"{status} {full_name} [{event_name}]\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="promoter_menu")]]
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ========== ПРОМОУТЕР: СТАТИСТИКА ==========
async def my_stats(update, context):
    user_id = update.callback_query.from_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, balance FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    
    if not promoter:
        await update.callback_query.edit_message_text("Ошибка")
        return
    
    promoter_id, balance = promoter
    monthly = get_monthly_count(promoter_id)
    rate = get_rate(monthly)
    
    cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ?", (promoter_id,))
    total_added = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ? AND is_confirmed = 1", (promoter_id,))
    total_confirmed = cur.fetchone()[0]
    
    # Статистика по мероприятиям
    events = get_active_events()
    event_stats = ""
    for event in events:
        event_id, event_name, _ = event
        event_count = get_monthly_count(promoter_id, event_id)
        if event_count > 0:
            event_stats += f"• {event_name}: {event_count} чел.\n"
    
    conn.close()
    
    conv = round(total_confirmed / total_added * 100, 1) if total_added > 0 else 0
    
    text = (
        f"💰 *ВАШ БАЛАНС:* {balance} руб.\n\n"
        f"📊 *ЗА ЭТОТ МЕСЯЦ:*\n"
        f"• Пришло: {monthly} чел.\n"
        f"• Ставка: {rate} руб./чел.\n"
    )
    
    if event_stats:
        text += f"\n📅 *ПО МЕРОПРИЯТИЯМ:*\n{event_stats}"
    
    text += (
        f"\n📈 *ВСЕГО:*\n"
        f"• Добавлено: {total_added}\n"
        f"• Пришло: {total_confirmed}\n"
        f"• Конверсия: {conv}%"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="promoter_menu")]]
    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ========== ПРОМОУТЕР: ДОБАВЛЕНИЕ ==========
async def add_person(update, context):
    events = get_active_events()
    
    if not events:
        await update.callback_query.edit_message_text("❌ Нет активных мероприятий")
        return
    
    keyboard = []
    for event in events:
        keyboard.append([InlineKeyboardButton(event[1], callback_data=f"add_event_{event[0]}")])
    
    await update.callback_query.edit_message_text(
        "📅 *Выберите мероприятие:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def add_person_event(update, context, event_id):
    context.user_data['add_event_id'] = event_id
    await update.callback_query.edit_message_text("✍️ Введите Фамилию и Имя человека:")
    return ADD_NAME

async def add_person_process(update, context):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    event_id = context.user_data.get('add_event_id')
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    
    if not promoter:
        await update.message.reply_text("Ошибка")
        return -1
    
    cur.execute("SELECT id FROM lists WHERE full_name = ? AND promoter_id = ? AND event_id = ?", 
                (name, promoter[0], event_id))
    if cur.fetchone():
        await update.message.reply_text(f"⚠️ {name} уже есть в списке на это мероприятие")
    else:
        cur.execute("INSERT INTO lists (full_name, promoter_id, event_id, is_confirmed) VALUES (?, ?, ?, 0)",
                    (name, promoter[0], event_id))
        conn.commit()
        await update.message.reply_text(f"✅ {name} добавлен на мероприятие")
    
    conn.close()
    
    await show_promoter_menu(update, context)
    return -1

# ========== ПРОМОУТЕР: УДАЛЕНИЕ ==========
async def delete_person(update, context):
    events = get_active_events()
    
    if not events:
        await update.callback_query.edit_message_text("❌ Нет активных мероприятий")
        return
    
    keyboard = []
    for event in events:
        keyboard.append([InlineKeyboardButton(event[1], callback_data=f"delete_event_{event[0]}")])
    
    await update.callback_query.edit_message_text(
        "📅 *Выберите мероприятие:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def delete_person_event(update, context, event_id):
    context.user_data['delete_event_id'] = event_id
    await update.callback_query.edit_message_text("🗑 Введите Фамилию Имя человека для удаления:")
    return DELETE_NAME

async def delete_person_process(update, context):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    event_id = context.user_data.get('delete_event_id')
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    
    if not promoter:
        await update.message.reply_text("Ошибка")
        return -1
    
    cur.execute("DELETE FROM lists WHERE full_name = ? AND promoter_id = ? AND event_id = ? AND is_confirmed = 0",
                (name, promoter[0], event_id))
    conn.commit()
    
    if cur.rowcount > 0:
        await update.message.reply_text(f"🗑 {name} удален")
    else:
        await update.message.reply_text(f"❌ {name} не найден (возможно, уже пришел)")
    
    conn.close()
    
    await show_promoter_menu(update, context)
    return -1

# ========== КАССИР ==========
async def check_person(update, context):
    name = update.message.text.strip()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT l.id, l.full_name, u.id, u.telegram_id, e.name
        FROM lists l
        JOIN users u ON l.promoter_id = u.id
        JOIN events e ON l.event_id = e.id
        WHERE l.full_name = ? AND l.is_confirmed = 0
    ''', (name,))
    result = cur.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ ЧЕЛОВЕКА НЕТ В СПИСКАХ")
        return
    
    list_id, full_name, promoter_id, promoter_tg, event_name = result
    
    context.user_data['pending_confirm'] = {
        'list_id': list_id,
        'name': full_name,
        'promoter_id': promoter_id,
        'promoter_tg': promoter_tg,
        'event_name': event_name
    }
    
    keyboard = [[
        InlineKeyboardButton("✅ ПОДТВЕРДИТЬ", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ ОТМЕНА", callback_data="confirm_no")
    ]]
    await update.message.reply_text(
        f"🔔 НАЙДЕН: {full_name}\n📅 Мероприятие: {event_name}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_no":
        await query.edit_message_text("❌ ОТМЕНЕНО")
        if 'pending_confirm' in context.user_data:
            del context.user_data['pending_confirm']
        return
    
    if query.data == "confirm_yes":
        pending = context.user_data.get('pending_confirm')
        if not pending:
            await query.edit_message_text("❌ ОШИБКА")
            return
        
        list_id = pending['list_id']
        name = pending['name']
        promoter_id = pending['promoter_id']
        promoter_tg = pending['promoter_tg']
        event_name = pending['event_name']
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("SELECT is_confirmed FROM lists WHERE id = ?", (list_id,))
        if cur.fetchone()[0] == 1:
            await query.edit_message_text("⚠️ УЖЕ ОТМЕЧЕН")
            conn.close()
            return
        
        monthly = get_monthly_count(promoter_id)
        rate = get_rate(monthly)
        
        cur.execute("UPDATE lists SET is_confirmed = 1, confirmed_at = ? WHERE id = ?", 
                    (datetime.now().isoformat(), list_id))
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (rate, promoter_id))
        
        cur.execute("SELECT balance FROM users WHERE id = ?", (promoter_id,))
        new_balance = cur.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        await query.edit_message_text(f"✅ ПОДТВЕРЖДЕНО!\n\n👤 {name}\n📅 {event_name}\n✅ Отмечен как пришедший")
        
        if promoter_tg:
            await context.bot.send_message(
                promoter_tg,
                f"🎉 *ПРИШЕЛ ГОСТЬ!*\n\n"
                f"👤 {name}\n"
                f"📅 {event_name}\n"
                f"💰 +{rate} руб.\n"
                f"💰 Новый баланс: {new_balance} руб.",
                parse_mode='Markdown'
            )
        
        del context.user_data['pending_confirm']

# ========== ОБРАБОТЧИК КНОПОК ==========
async def handle_callback(update, context):
    query = update.callback_query
    data = query.data
    
    if data == "back_to_start":
        await start(update, context)
        return
    
    if data == "admin_menu":
        await show_admin_menu(update, context)
        return
    
    if data == "promoter_menu":
        await show_promoter_menu(update, context)
        return
    
    # Админские кнопки
    if data == "admin_stats":
        await admin_stats(update, context)
    elif data == "admin_promoters":
        await admin_promoters(update, context)
    elif data == "admin_view_lists":
        await admin_view_lists(update, context)
    elif data == "admin_reset_balance":
        await admin_reset_balance(update, context)
    elif data == "admin_add_promoter":
        await admin_add_promoter(update, context)
        return ADMIN_ADD_PROMOTER
    elif data == "admin_delete_promoter":
        await admin_delete_promoter(update, context)
    elif data == "admin_events":
        await admin_events(update, context)
    elif data == "admin_add_event":
        await admin_add_event(update, context)
        return ADMIN_ADD_EVENT
    elif data == "admin_delete_event":
        await admin_delete_event(update, context)
    elif data == "admin_reset_month":
        await admin_reset_month(update, context)
    
    # Промоутерские кнопки
    elif data == "my_lists":
        await my_lists(update, context)
    elif data == "add_person":
        await add_person(update, context)
    elif data == "delete_person":
        await delete_person(update, context)
    elif data == "my_stats":
        await my_stats(update, context)
    
    # Обработка выбора промоутера для просмотра списков
    elif data.startswith("admin_view_promoter_"):
        promoter_id = int(data.split("_")[3])
        await admin_view_promoter_lists(update, context, promoter_id)
    
    # Обработка сброса баланса
    elif data.startswith("admin_reset_balance_"):
        promoter_id = int(data.split("_")[3])
        await admin_reset_balance_confirm(update, context, promoter_id)
    
    # Обработка удаления промоутера
    elif data.startswith("admin_delete_promoter_"):
        promoter_id = int(data.split("_")[3])
        await admin_delete_promoter_confirm(update, context, promoter_id)
    
    # Обработка удаления мероприятия
    elif data.startswith("admin_delete_event_"):
        event_id = int(data.split("_")[3])
        await admin_delete_event_confirm(update, context, event_id)
    
    # Обработка выбора мероприятия для добавления/удаления человека
    elif data.startswith("add_event_"):
        event_id = int(data.split("_")[2])
        await add_person_event(update, context, event_id)
        return ADD_NAME
    elif data.startswith("delete_event_"):
        event_id = int(data.split("_")[2])
        await delete_person_event(update, context, event_id)
        return DELETE_NAME
    
    return -1

# ========== ЗАПУСК ==========
def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    
    # Обработчики
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(?!confirm_).*"))
    app.add_handler(CallbackQueryHandler(confirm_handler, pattern="^(confirm_yes|confirm_no)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_person))
    
    # ConversationHandler для админа и промоутера
    from telegram.ext import ConversationHandler
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_add_promoter, pattern="^admin_add_promoter$"),
            CallbackQueryHandler(admin_add_event, pattern="^admin_add_event$"),
            CallbackQueryHandler(add_person, pattern="^add_person$"),
            CallbackQueryHandler(delete_person, pattern="^delete_person$"),
        ],
        states={
            ADMIN_ADD_PROMOTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_promoter_process)],
            ADMIN_ADD_EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_event_process)],
            ADMIN_ADD_EVENT + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_event_date)],
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_person_process)],
            DELETE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_person_process)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv_handler)
    
    print("✅ БОТ ЗАПУЩЕН!")
    app.run_polling()

if __name__ == '__main__':
    main()
