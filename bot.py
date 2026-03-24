import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== НАСТРОЙКИ ==========
TOKEN = "8680724321:AAGmcU8I5Z1T9d8kHrqCS5qiZpmLpvPnLY0"  # ← ЗАМЕНИ НА СВОЙ
ADMIN_ID = 355936751

DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_database.db')

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
            is_confirmed INTEGER DEFAULT 0
        )
    ''')
    cur.execute('INSERT OR IGNORE INTO users (telegram_id, role) VALUES (?, ?)', (ADMIN_ID, 'admin'))
    cur.execute('INSERT OR IGNORE INTO events (name, date) VALUES (?, ?)', 
                ('Основное мероприятие', datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def get_rate(count):
    if count >= 60: return 150
    if count >= 30: return 130
    return 120

def get_monthly_count(promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ? AND is_confirmed = 1", (promoter_id,))
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_all_promoters():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, telegram_id, username, balance FROM users WHERE role = 'promoter'")
    result = cur.fetchall()
    conn.close()
    return result

def get_all_cashiers():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, telegram_id, username FROM users WHERE role = 'cashier'")
    result = cur.fetchall()
    conn.close()
    return result

def get_active_events():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM events WHERE is_active = 1")
    result = cur.fetchall()
    conn.close()
    return result

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
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("👥 Промоутеры", callback_data="promoters")],
            [InlineKeyboardButton("💳 Кассиры", callback_data="cashiers")],
            [InlineKeyboardButton("📅 Мероприятия", callback_data="events")],
            [InlineKeyboardButton("🔄 Сброс месяца", callback_data="reset_month")]
        ]
        await update.message.reply_text("👑 *АДМИН ПАНЕЛЬ*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif role == 'promoter':
        keyboard = [
            [InlineKeyboardButton("📋 Списки", callback_data="my_lists")],
            [InlineKeyboardButton("➕ Добавить", callback_data="add_person")],
            [InlineKeyboardButton("❌ Удалить", callback_data="delete_person")],
            [InlineKeyboardButton("💰 Статистика", callback_data="my_stats")]
        ]
        await update.message.reply_text("🔧 *МЕНЮ ПРОМОУТЕРА*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif role == 'cashier':
        await update.message.reply_text("🔍 *КАССИР*\n\nОтправьте Фамилию Имя человека.", parse_mode='Markdown')

# ========== АДМИН: СТАТИСТИКА ==========
async def admin_stats(update, context):
    promoters = get_all_promoters()
    if not promoters:
        await update.callback_query.edit_message_text("📭 Нет промоутеров")
        return
    
    text = "📊 *СТАТИСТИКА*\n\n"
    for pid, tg_id, username, balance in promoters:
        name = f"@{username}" if username else str(tg_id)
        monthly = get_monthly_count(pid)
        text += f"👤 {name}\n💰 {balance} руб. | 📊 {monthly} чел.\n\n"
    
    await update.callback_query.edit_message_text(text, parse_mode='Markdown')

# ========== АДМИН: ПРОМОУТЕРЫ ==========
async def admin_promoters(update, context):
    promoters = get_all_promoters()
    if not promoters:
        await update.callback_query.edit_message_text("📭 Нет промоутеров")
        return
    
    keyboard = []
    for pid, tg_id, username, balance in promoters:
        name = f"@{username}" if username else str(tg_id)
        keyboard.append([InlineKeyboardButton(f"{name} (баланс: {balance} руб.)", callback_data=f"view_promoter_{pid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    
    await update.callback_query.edit_message_text("👥 *Выберите промоутера:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def view_promoter(update, context, promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, username, balance FROM users WHERE id = ?", (promoter_id,))
    promoter = cur.fetchone()
    cur.execute("SELECT full_name, is_confirmed FROM lists WHERE promoter_id = ?", (promoter_id,))
    people = cur.fetchall()
    conn.close()
    
    name = f"@{promoter[1]}" if promoter[1] else str(promoter[0])
    balance = promoter[2]
    monthly = get_monthly_count(promoter_id)
    
    text = f"👤 *{name}*\n💰 Баланс: {balance} руб.\n📊 За месяц: {monthly} чел.\n\n"
    
    if people:
        text += "*СПИСОК:*\n"
        for full_name, status in people:
            icon = "✅" if status else "⏳"
            text += f"{icon} {full_name}\n"
    else:
        text += "Список пуст"
    
    keyboard = [
        [InlineKeyboardButton("🗑 Удалить промоутера", callback_data=f"del_promoter_{promoter_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="promoters")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def delete_promoter(update, context, promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, username FROM users WHERE id = ?", (promoter_id,))
    promoter = cur.fetchone()
    cur.execute("DELETE FROM users WHERE id = ?", (promoter_id,))
    cur.execute("DELETE FROM lists WHERE promoter_id = ?", (promoter_id,))
    conn.commit()
    conn.close()
    
    name = f"@{promoter[1]}" if promoter[1] else str(promoter[0])
    await update.callback_query.edit_message_text(f"✅ Промоутер {name} удален")
    
    try:
        await context.bot.send_message(promoter[0], "❌ Ваша роль промоутера удалена.")
    except:
        pass

# ========== АДМИН: КАССИРЫ ==========
async def admin_cashiers(update, context):
    cashiers = get_all_cashiers()
    if not cashiers:
        await update.callback_query.edit_message_text("📭 Нет кассиров")
        return
    
    keyboard = []
    for cid, tg_id, username in cashiers:
        name = f"@{username}" if username else str(tg_id)
        keyboard.append([InlineKeyboardButton(name, callback_data=f"del_cashier_{cid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    
    await update.callback_query.edit_message_text("💳 *Список кассиров*\n\nНажмите на кассира для удаления:", 
                                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def delete_cashier(update, context, cashier_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, username FROM users WHERE id = ?", (cashier_id,))
    cashier = cur.fetchone()
    cur.execute("DELETE FROM users WHERE id = ?", (cashier_id,))
    conn.commit()
    conn.close()
    
    name = f"@{cashier[1]}" if cashier[1] else str(cashier[0])
    await update.callback_query.edit_message_text(f"✅ Кассир {name} удален")
    
    try:
        await context.bot.send_message(cashier[0], "❌ Ваша роль кассира удалена.")
    except:
        pass

# ========== АДМИН: МЕРОПРИЯТИЯ ==========
async def admin_events(update, context):
    events = get_active_events()
    text = "📅 *МЕРОПРИЯТИЯ*\n\n"
    for eid, name in events:
        text += f"• {name}\n"
    if not events:
        text += "Нет мероприятий"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить", callback_data="add_event")],
        [InlineKeyboardButton("❌ Удалить", callback_data="del_event")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def add_event_start(update, context):
    await update.callback_query.edit_message_text("✍️ Введите название мероприятия:")
    context.user_data['waiting'] = 'event_name'

async def add_event_name(update, context):
    context.user_data['event_name'] = update.message.text.strip()
    await update.message.reply_text("📅 Введите дату (ГГГГ-ММ-ДД):")
    context.user_data['waiting'] = 'event_date'

async def add_event_date(update, context):
    name = context.user_data.get('event_name')
    date = update.message.text.strip()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO events (name, date) VALUES (?, ?)", (name, date))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Мероприятие '{name}' добавлено")
    context.user_data['waiting'] = None
    await start(update, context)

async def delete_event_list(update, context):
    events = get_active_events()
    if not events:
        await update.callback_query.edit_message_text("📭 Нет мероприятий")
        return
    
    keyboard = []
    for eid, name in events:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"del_event_{eid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="events")])
    
    await update.callback_query.edit_message_text("❌ *Выберите мероприятие для удаления:*", 
                                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def delete_event(update, context, event_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM events WHERE id = ?", (event_id,))
    name = cur.fetchone()[0]
    cur.execute("UPDATE events SET is_active = 0 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    
    await update.callback_query.edit_message_text(f"✅ Мероприятие '{name}' удалено")

# ========== АДМИН: СБРОС МЕСЯЦА ==========
async def reset_month(update, context):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM users WHERE role = 'promoter'")
    promoters = cur.fetchall()
    cur.execute("UPDATE lists SET is_confirmed = 0")
    conn.commit()
    conn.close()
    
    for p in promoters:
        try:
            await context.bot.send_message(p[0], "📅 *НОВЫЙ МЕСЯЦ!*\n\nСтатистика обнулена. Удачи!", parse_mode='Markdown')
        except:
            pass
    
    await update.callback_query.edit_message_text("✅ Месяц сброшен")

# ========== ПРОМОУТЕР: СПИСКИ ==========
async def my_lists(update, context):
    user_id = update.callback_query.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    if not promoter:
        await update.callback_query.edit_message_text("Ошибка")
        return
    
    cur.execute('''
        SELECT l.full_name, e.name, l.is_confirmed 
        FROM lists l
        JOIN events e ON l.event_id = e.id
        WHERE l.promoter_id = ?
        ORDER BY l.is_confirmed, l.id DESC
    ''', (promoter[0],))
    lists = cur.fetchall()
    conn.close()
    
    if not lists:
        await update.callback_query.edit_message_text("📭 Список пуст")
        return
    
    text = "📋 *ВАШ СПИСОК*\n\n"
    for name, event, status in lists:
        icon = "✅" if status else "⏳"
        text += f"{icon} {name} [{event}]\n"
    
    await update.callback_query.edit_message_text(text, parse_mode='Markdown')

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
    
    pid, balance = promoter
    monthly = get_monthly_count(pid)
    rate = get_rate(monthly)
    
    cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ?", (pid,))
    total_added = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ? AND is_confirmed = 1", (pid,))
    total_confirmed = cur.fetchone()[0]
    conn.close()
    
    conv = round(total_confirmed / total_added * 100, 1) if total_added > 0 else 0
    
    text = (
        f"💰 *БАЛАНС:* {balance} руб.\n\n"
        f"📊 *ЗА МЕСЯЦ:* {monthly} чел.\n"
        f"💰 *СТАВКА:* {rate} руб./чел.\n\n"
        f"📈 *ВСЕГО:*\n"
        f"• Добавлено: {total_added}\n"
        f"• Пришло: {total_confirmed}\n"
        f"• Конверсия: {conv}%"
    )
    
    await update.callback_query.edit_message_text(text, parse_mode='Markdown')

# ========== ПРОМОУТЕР: ДОБАВИТЬ ЧЕЛОВЕКА ==========
async def add_person_start(update, context):
    events = get_active_events()
    if not events:
        await update.callback_query.edit_message_text("❌ Нет мероприятий")
        return
    
    keyboard = []
    for eid, name in events:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"add_{eid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    
    await update.callback_query.edit_message_text("📅 *Выберите мероприятие:*", 
                                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def add_person_event(update, context, event_id):
    context.user_data['event_id'] = event_id
    await update.callback_query.edit_message_text("✍️ Введите Фамилию и Имя:")
    context.user_data['waiting'] = 'add_person'

async def add_person_process(update, context):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    event_id = context.user_data.get('event_id')
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    
    if not promoter:
        await update.message.reply_text("Ошибка")
        context.user_data['waiting'] = None
        return
    
    cur.execute("SELECT id FROM lists WHERE full_name = ? AND promoter_id = ? AND event_id = ?", 
                (name, promoter[0], event_id))
    if cur.fetchone():
        await update.message.reply_text(f"⚠️ {name} уже есть в списке")
    else:
        cur.execute("INSERT INTO lists (full_name, promoter_id, event_id, is_confirmed) VALUES (?, ?, ?, 0)",
                    (name, promoter[0], event_id))
        conn.commit()
        await update.message.reply_text(f"✅ {name} добавлен")
    
    conn.close()
    context.user_data['waiting'] = None
    await start(update, context)

# ========== ПРОМОУТЕР: УДАЛИТЬ ЧЕЛОВЕКА ==========
async def delete_person_start(update, context):
    events = get_active_events()
    if not events:
        await update.callback_query.edit_message_text("❌ Нет мероприятий")
        return
    
    keyboard = []
    for eid, name in events:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"del_{eid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    
    await update.callback_query.edit_message_text("📅 *Выберите мероприятие:*", 
                                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def delete_person_event(update, context, event_id):
    context.user_data['event_id'] = event_id
    await update.callback_query.edit_message_text("🗑 Введите Фамилию и Имя:")
    context.user_data['waiting'] = 'delete_person'

async def delete_person_process(update, context):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    event_id = context.user_data.get('event_id')
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    
    if not promoter:
        await update.message.reply_text("Ошибка")
        context.user_data['waiting'] = None
        return
    
    cur.execute("DELETE FROM lists WHERE full_name = ? AND promoter_id = ? AND event_id = ? AND is_confirmed = 0",
                (name, promoter[0], event_id))
    conn.commit()
    
    if cur.rowcount > 0:
        await update.message.reply_text(f"🗑 {name} удален")
    else:
        await update.message.reply_text(f"❌ {name} не найден")
    
    conn.close()
    context.user_data['waiting'] = None
    await start(update, context)

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
    
    context.user_data['pending'] = {
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
    await update.message.reply_text(f"🔔 {full_name}\n📅 {event_name}", reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_no":
        await query.edit_message_text("❌ ОТМЕНЕНО")
        if 'pending' in context.user_data:
            del context.user_data['pending']
        return
    
    if query.data == "confirm_yes":
        pending = context.user_data.get('pending')
        if not pending:
            await query.edit_message_text("❌ ОШИБКА")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("SELECT is_confirmed FROM lists WHERE id = ?", (pending['list_id'],))
        if cur.fetchone()[0] == 1:
            await query.edit_message_text("⚠️ УЖЕ ОТМЕЧЕН")
            conn.close()
            return
        
        monthly = get_monthly_count(pending['promoter_id'])
        rate = get_rate(monthly)
        
        cur.execute("UPDATE lists SET is_confirmed = 1 WHERE id = ?", (pending['list_id'],))
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (rate, pending['promoter_id']))
        
        cur.execute("SELECT balance FROM users WHERE id = ?", (pending['promoter_id'],))
        new_balance = cur.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # Кассиру не показываем сумму
        await query.edit_message_text(f"✅ ПОДТВЕРЖДЕНО!\n\n👤 {pending['name']}\n📅 {pending['event_name']}")
        
        # Промоутеру показываем сумму
        if pending['promoter_tg']:
            await context.bot.send_message(
                pending['promoter_tg'],
                f"🎉 *ПРИШЕЛ ГОСТЬ!*\n\n"
                f"👤 {pending['name']}\n"
                f"📅 {pending['event_name']}\n"
                f"💰 +{rate} руб.\n"
                f"💰 Баланс: {new_balance} руб.",
                parse_mode='Markdown'
            )
        
        del context.user_data['pending']

# ========== ОБРАБОТЧИК КНОПОК ==========
async def handle_callback(update, context):
    query = update.callback_query
    data = query.data
    
    if data == "back":
        await start(update, context)
        return
    
    if data == "stats":
        await admin_stats(update, context)
    elif data == "promoters":
        await admin_promoters(update, context)
    elif data == "cashiers":
        await admin_cashiers(update, context)
    elif data == "events":
        await admin_events(update, context)
    elif data == "reset_month":
        await reset_month(update, context)
    elif data == "add_event":
        await add_event_start(update, context)
    elif data == "del_event":
        await delete_event_list(update, context)
    elif data == "my_lists":
        await my_lists(update, context)
    elif data == "add_person":
        await add_person_start(update, context)
    elif data == "delete_person":
        await delete_person_start(update, context)
    elif data == "my_stats":
        await my_stats(update, context)
    
    elif data.startswith("view_promoter_"):
        pid = int(data.split("_")[2])
        await view_promoter(update, context, pid)
    elif data.startswith("del_promoter_"):
        pid = int(data.split("_")[2])
        await delete_promoter(update, context, pid)
    elif data.startswith("del_cashier_"):
        cid = int(data.split("_")[2])
        await delete_cashier(update, context, cid)
    elif data.startswith("del_event_"):
        eid = int(data.split("_")[2])
        await delete_event(update, context, eid)
    elif data.startswith("add_"):
        eid = int(data.split("_")[1])
        await add_person_event(update, context, eid)
    elif data.startswith("del_"):
        eid = int(data.split("_")[1])
        await delete_person_event(update, context, eid)

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
async def handle_message(update, context):
    waiting = context.user_data.get('waiting')
    
    if waiting == 'event_name':
        await add_event_name(update, context)
    elif waiting == 'event_date':
        await add_event_date(update, context)
    elif waiting == 'add_person':
        await add_person_process(update, context)
    elif waiting == 'delete_person':
        await delete_person_process(update, context)
    else:
        user_id = update.effective_user.id
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
        user = cur.fetchone()
        conn.close()
        
        if user and user[0] == 'cashier':
            await check_person(update, context)
        else:
            await update.message.reply_text("❌ Неизвестная команда. Напишите /start")

# ========== ЗАПУСК ==========
def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CallbackQueryHandler(confirm_handler, pattern="^(confirm_yes|confirm_no)$"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ БОТ ЗАПУЩЕН!")
    app.run_polling()

async def set_role(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только администратор")
        return
    
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Использование: /setrole ID promoter|cashier")
            return
        
        tg_id = int(args[0])
        role = args[1]
        
        if role not in ['promoter', 'cashier']:
            await update.message.reply_text("Роль: promoter или cashier")
            return
        
        try:
            chat = await context.bot.get_chat(tg_id)
            username = chat.username
        except:
            username = None
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (telegram_id, username, role, balance) VALUES (?, ?, ?, 0)",
                    (tg_id, username, role))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Роль {role} назначена пользователю {tg_id}")
        await context.bot.send_message(tg_id, f"✅ Вам назначена роль *{role}*!\nНапишите /start", parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()
