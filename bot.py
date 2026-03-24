import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "8680724321:AAGmcU8I5Z1T9d8kHrqCS5qiZpmLpvPnLY0"
ADMIN_ID = 355936751
DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE, username TEXT, role TEXT, balance INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS lists (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT, promoter_id INTEGER, event_id INTEGER)')
    cur.execute('INSERT OR IGNORE INTO users (telegram_id, role) VALUES (?, ?)', (ADMIN_ID, 'admin'))
    cur.execute('INSERT OR IGNORE INTO events (name) VALUES (?)', ('Основное мероприятие',))
    conn.commit()
    conn.close()

def get_user_role(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_promoter_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_promoters():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, telegram_id, username, balance FROM users WHERE role = 'promoter'")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_cashiers():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, telegram_id, username FROM users WHERE role = 'cashier'")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_events():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM events")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_lists(promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT full_name FROM lists WHERE promoter_id = ?", (promoter_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_person(promoter_id, name, event_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO lists (full_name, promoter_id, event_id) VALUES (?, ?, ?)", (name, promoter_id, event_id))
    conn.commit()
    conn.close()

def delete_person(promoter_id, name, event_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM lists WHERE full_name = ? AND promoter_id = ? AND event_id = ?", (name, promoter_id, event_id))
    conn.commit()
    conn.close()
    return cur.rowcount

def add_balance(promoter_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, promoter_id))
    conn.commit()
    conn.close()

def get_balance(promoter_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE id = ?", (promoter_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def reset_month():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM users WHERE role = 'promoter'")
    promoters = cur.fetchall()
    cur.execute("DELETE FROM lists")
    cur.execute("UPDATE users SET balance = 0 WHERE role = 'promoter'")
    conn.commit()
    conn.close()
    return [p[0] for p in promoters]

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
async def start(update, context):
    user_id = update.effective_user.id
    role = get_user_role(user_id)
    
    if not role:
        await update.message.reply_text(f"👋 Добро пожаловать!\nВаш ID: {user_id}\nОжидайте назначения роли.")
        await context.bot.send_message(ADMIN_ID, f"Новый пользователь: {user_id}")
        return
    
    if role == 'admin':
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("👥 Промоутеры", callback_data="promoters")],
            [InlineKeyboardButton("💳 Кассиры", callback_data="cashiers")],
            [InlineKeyboardButton("📅 Мероприятия", callback_data="events")],
            [InlineKeyboardButton("🔄 Сброс месяца", callback_data="reset")]
        ]
        await update.message.reply_text("АДМИН ПАНЕЛЬ", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif role == 'promoter':
        keyboard = [
            [InlineKeyboardButton("Мои списки", callback_data="mylists")],
            [InlineKeyboardButton("Добавить", callback_data="add")],
            [InlineKeyboardButton("Удалить", callback_data="del")],
            [InlineKeyboardButton("Статистика", callback_data="mystats")]
        ]
        await update.message.reply_text("МЕНЮ ПРОМОУТЕРА", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif role == 'cashier':
        await update.message.reply_text("КАССИР\n\nОтправьте Фамилию Имя человека.")

# ========== АДМИН ==========
async def admin_stats(update, context):
    query = update.callback_query
    promoters = get_promoters()
    text = "СТАТИСТИКА\n\n"
    for pid, tg_id, username, bal in promoters:
        name = f"@{username}" if username else str(tg_id)
        cnt = len(get_lists(pid))
        text += f"{name}\nБаланс: {bal} руб. | Добавлено: {cnt} чел.\n\n"
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_promoters(update, context):
    query = update.callback_query
    promoters = get_promoters()
    if not promoters:
        await query.edit_message_text("Нет промоутеров")
        return
    keyboard = []
    for pid, tg_id, username, bal in promoters:
        name = f"@{username}" if username else str(tg_id)
        keyboard.append([InlineKeyboardButton(f"{name} ({bal} руб.)", callback_data=f"view_{pid}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
    await query.edit_message_text("ПРОМОУТЕРЫ", reply_markup=InlineKeyboardMarkup(keyboard))

async def view_promoter(update, context, pid):
    query = update.callback_query
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, username, balance FROM users WHERE id = ?", (pid,))
    user = cur.fetchone()
    cur.execute("SELECT full_name FROM lists WHERE promoter_id = ?", (pid,))
    people = cur.fetchall()
    conn.close()
    name = f"@{user[1]}" if user[1] else str(user[0])
    text = f"{name}\nБаланс: {user[2]} руб.\nДобавлено: {len(people)} чел.\n\n"
    if people:
        text += "СПИСОК:\n" + "\n".join([f"• {p[0]}" for p in people])
    else:
        text += "Список пуст"
    keyboard = [
        [InlineKeyboardButton("Удалить", callback_data=f"delprom_{pid}")],
        [InlineKeyboardButton("Назад", callback_data="promoters")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_promoter(update, context, pid):
    query = update.callback_query
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM users WHERE id = ?", (pid,))
    tg_id = cur.fetchone()[0]
    cur.execute("DELETE FROM users WHERE id = ?", (pid,))
    cur.execute("DELETE FROM lists WHERE promoter_id = ?", (pid,))
    conn.commit()
    conn.close()
    await query.edit_message_text("Промоутер удален")
    await context.bot.send_message(tg_id, "Ваша роль промоутера удалена")

async def admin_cashiers(update, context):
    query = update.callback_query
    cashiers = get_cashiers()
    if not cashiers:
        await query.edit_message_text("Нет кассиров")
        return
    keyboard = []
    for cid, tg_id, username in cashiers:
        name = f"@{username}" if username else str(tg_id)
        keyboard.append([InlineKeyboardButton(name, callback_data=f"delcash_{cid}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
    await query.edit_message_text("КАССИРЫ\n\nНажмите для удаления", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_cashier(update, context, cid):
    query = update.callback_query
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM users WHERE id = ?", (cid,))
    tg_id = cur.fetchone()[0]
    cur.execute("DELETE FROM users WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    await query.edit_message_text("Кассир удален")
    await context.bot.send_message(tg_id, "Ваша роль кассира удалена")

async def admin_events(update, context):
    query = update.callback_query
    events = get_events()
    text = "МЕРОПРИЯТИЯ\n\n" + "\n".join([f"• {e[1]}" for e in events]) if events else "Нет мероприятий"
    keyboard = [
        [InlineKeyboardButton("Добавить", callback_data="addevent")],
        [InlineKeyboardButton("Удалить", callback_data="delevent")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_event_start(update, context):
    await update.callback_query.edit_message_text("Введите название мероприятия:")
    context.user_data['step'] = 'event_name'

async def add_event_name(update, context):
    name = update.message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO events (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"Мероприятие '{name}' добавлено")
    context.user_data['step'] = None
    await start(update, context)

async def delete_event_list(update, context):
    query = update.callback_query
    events = get_events()
    if not events:
        await query.edit_message_text("Нет мероприятий")
        return
    keyboard = []
    for eid, name in events:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"delevent_{eid}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="events")])
    await query.edit_message_text("Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_event(update, context, eid):
    query = update.callback_query
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM events WHERE id = ?", (eid,))
    cur.execute("DELETE FROM lists WHERE event_id = ?", (eid,))
    conn.commit()
    conn.close()
    await query.edit_message_text("Мероприятие удалено")

async def admin_reset(update, context):
    query = update.callback_query
    promoters = reset_month()
    for pid in promoters:
        try:
            await context.bot.send_message(pid, "НОВЫЙ МЕСЯЦ!\n\nВсе списки и баланс обнулены.")
        except:
            pass
    await query.edit_message_text("Месяц сброшен")

# ========== ПРОМОУТЕР ==========
async def promo_lists(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    pid = get_promoter_id(user_id)
    if not pid:
        await query.edit_message_text("Ошибка")
        return
    lists = get_lists(pid)
    if not lists:
        await query.edit_message_text("Список пуст")
        return
    text = "ВАШ СПИСОК\n\n" + "\n".join([f"• {l[0]}" for l in lists])
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def promo_stats(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    pid = get_promoter_id(user_id)
    if not pid:
        await query.edit_message_text("Ошибка")
        return
    balance = get_balance(pid)
    count = len(get_lists(pid))
    text = f"БАЛАНС: {balance} руб.\n\nДОБАВЛЕНО: {count} чел."
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def promo_add(update, context):
    query = update.callback_query
    events = get_events()
    if not events:
        await query.edit_message_text("Нет мероприятий")
        return
    keyboard = []
    for eid, name in events:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"addevent_{eid}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
    await query.edit_message_text("Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_person_event(update, context, eid):
    context.user_data['event_id'] = eid
    await update.callback_query.edit_message_text("Введите Фамилию и Имя:")
    context.user_data['step'] = 'add_person'

async def add_person_process(update, context):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    eid = context.user_data.get('event_id')
    pid = get_promoter_id(user_id)
    if not pid:
        await update.message.reply_text("Ошибка")
        context.user_data['step'] = None
        return
    add_person(pid, name, eid)
    await update.message.reply_text(f"{name} добавлен")
    context.user_data['step'] = None
    await start(update, context)

async def promo_del(update, context):
    query = update.callback_query
    events = get_events()
    if not events:
        await query.edit_message_text("Нет мероприятий")
        return
    keyboard = []
    for eid, name in events:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"delevent_{eid}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
    await query.edit_message_text("Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_person_event(update, context, eid):
    context.user_data['event_id'] = eid
    await update.callback_query.edit_message_text("Введите Фамилию и Имя:")
    context.user_data['step'] = 'delete_person'

async def delete_person_process(update, context):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    eid = context.user_data.get('event_id')
    pid = get_promoter_id(user_id)
    if not pid:
        await update.message.reply_text("Ошибка")
        context.user_data['step'] = None
        return
    deleted = delete_person(pid, name, eid)
    if deleted:
        await update.message.reply_text(f"{name} удален")
    else:
        await update.message.reply_text(f"{name} не найден")
    context.user_data['step'] = None
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
        WHERE l.full_name = ?
    ''', (name,))
    result = cur.fetchone()
    conn.close()
    if not result:
        await update.message.reply_text("Человека нет в списках")
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
        InlineKeyboardButton("ПОДТВЕРДИТЬ", callback_data="confirm_yes"),
        InlineKeyboardButton("ОТМЕНА", callback_data="confirm_no")
    ]]
    await update.message.reply_text(f"{full_name}\n{event_name}", reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_handler(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_no":
        await query.edit_message_text("Отменено")
        if 'pending' in context.user_data:
            del context.user_data['pending']
        return
    if query.data == "confirm_yes":
        pending = context.user_data.get('pending')
        if not pending:
            await query.edit_message_text("Ошибка")
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM lists WHERE id = ?", (pending['list_id'],))
        if not cur.fetchone():
            await query.edit_message_text("Человек уже отмечен")
            conn.close()
            return
        cur.execute("DELETE FROM lists WHERE id = ?", (pending['list_id'],))
        count = len(get_lists(pending['promoter_id']))
        rate = 120
        if count >= 60: rate = 150
        elif count >= 30: rate = 130
        add_balance(pending['promoter_id'], rate)
        new_balance = get_balance(pending['promoter_id'])
        conn.commit()
        conn.close()
        await query.edit_message_text(f"ПОДТВЕРЖДЕНО!\n\n{pending['name']}\n{pending['event_name']}")
        if pending['promoter_tg']:
            await context.bot.send_message(
                pending['promoter_tg'],
                f"ПРИШЕЛ ГОСТЬ!\n\n{pending['name']}\n{pending['event_name']}\n+{rate} руб.\nБаланс: {new_balance} руб."
            )
        del context.user_data['pending']

# ========== ОБРАБОТЧИКИ ==========
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
    elif data == "reset":
        await admin_reset(update, context)
    elif data == "addevent":
        await add_event_start(update, context)
    elif data == "delevent":
        await delete_event_list(update, context)
    elif data == "mylists":
        await promo_lists(update, context)
    elif data == "add":
        await promo_add(update, context)
    elif data == "del":
        await promo_del(update, context)
    elif data == "mystats":
        await promo_stats(update, context)
    
    elif data.startswith("view_"):
        await view_promoter(update, context, int(data.split("_")[1]))
    elif data.startswith("delprom_"):
        await delete_promoter(update, context, int(data.split("_")[1]))
    elif data.startswith("delcash_"):
        await delete_cashier(update, context, int(data.split("_")[1]))
    elif data.startswith("delevent_"):
        await delete_event(update, context, int(data.split("_")[1]))
    elif data.startswith("addevent_"):
        await add_person_event(update, context, int(data.split("_")[1]))
    elif data.startswith("delevent_"):
        eid = int(data.split("_")[1])
        if len(data.split("_")) == 2 and data.startswith("delevent_"):
            if context.user_data.get('step'):
                await delete_person_event(update, context, eid)
            else:
                await delete_event(update, context, eid)

async def handle_message(update, context):
    step = context.user_data.get('step')
    if step == 'event_name':
        await add_event_name(update, context)
    elif step == 'add_person':
        await add_person_process(update, context)
    elif step == 'delete_person':
        await delete_person_process(update, context)
    else:
        role = get_user_role(update.effective_user.id)
        if role == 'cashier':
            await check_person(update, context)
        else:
            await update.message.reply_text("Напишите /start")

async def set_role(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Только администратор")
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
        cur.execute("INSERT OR REPLACE INTO users (telegram_id, username, role, balance) VALUES (?, ?, ?, 0)", (tg_id, username, role))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"Роль {role} назначена")
        await context.bot.send_message(tg_id, f"Вам назначена роль {role}!\nНапишите /start")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ========== ЗАПУСК ==========
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CallbackQueryHandler(confirm_handler, pattern="^(confirm_yes|confirm_no)$"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("БОТ ЗАПУЩЕН")
    app.run_polling()

if __name__ == '__main__':
    main()
