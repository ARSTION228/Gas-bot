import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== НАСТРОЙКИ ==========
TOKEN = "8680724321:AAGmcU8I5Z1T9d8kHrqCS5qiZpmLpvPnLY0"  # ЗАМЕНИ НА СВОЙ
ADMIN_ID = 355936751  # ЗАМЕНИ НА СВОЙ

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, tg_id INTEGER UNIQUE, name TEXT, role TEXT, balance INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS people (id INTEGER PRIMARY KEY, name TEXT, promoter_id INTEGER, event_id INTEGER)''')
    c.execute("INSERT OR IGNORE INTO users (tg_id, role) VALUES (?, 'admin')", (ADMIN_ID,))
    c.execute("INSERT OR IGNORE INTO events (name) VALUES ('Основное')",)
    conn.commit()
    conn.close()

def get_role(tg):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE tg_id = ?", (tg,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

def get_promoters():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT id, tg_id, name, balance FROM users WHERE role = 'promoter'")
    r = c.fetchall()
    conn.close()
    return r

def get_cashiers():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT id, tg_id, name FROM users WHERE role = 'cashier'")
    r = c.fetchall()
    conn.close()
    return r

def get_events():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM events")
    r = c.fetchall()
    conn.close()
    return r

def get_people(pid):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT name FROM people WHERE promoter_id = ?", (pid,))
    r = [x[0] for x in c.fetchall()]
    conn.close()
    return r

def add_person(pid, name, eid):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO people (name, promoter_id, event_id) VALUES (?, ?, ?)", (name, pid, eid))
    conn.commit()
    conn.close()

def del_person(pid, name, eid):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("DELETE FROM people WHERE name = ? AND promoter_id = ? AND event_id = ?", (name, pid, eid))
    conn.commit()
    conn.close()
    return c.rowcount

def add_balance(pid, amount):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, pid))
    conn.commit()
    conn.close()

def get_balance(pid):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id = ?", (pid,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def get_promoter_by_tg(tg):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE tg_id = ? AND role = 'promoter'", (tg,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

# ========== ГЛАВНОЕ МЕНЮ ==========
async def start(update, context):
    tg = update.effective_user.id
    role = get_role(tg)
    if not role:
        await update.message.reply_text(f"👋 Ваш ID: {tg}\nОжидайте назначения роли")
        await context.bot.send_message(ADMIN_ID, f"Новый пользователь: {tg}")
        return
    if role == 'admin':
        kb = [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("👥 Промоутеры", callback_data="promoters")],
            [InlineKeyboardButton("💳 Кассиры", callback_data="cashiers")],
            [InlineKeyboardButton("📅 Мероприятия", callback_data="events")],
            [InlineKeyboardButton("🔄 Сброс месяца", callback_data="reset")]
        ]
        await update.message.reply_text("👑 АДМИН", reply_markup=InlineKeyboardMarkup(kb))
    elif role == 'promoter':
        kb = [
            [InlineKeyboardButton("📋 Мои списки", callback_data="mylists")],
            [InlineKeyboardButton("➕ Добавить", callback_data="add")],
            [InlineKeyboardButton("❌ Удалить", callback_data="del")],
            [InlineKeyboardButton("💰 Статистика", callback_data="stats_p")]
        ]
        await update.message.reply_text("🔧 ПРОМОУТЕР", reply_markup=InlineKeyboardMarkup(kb))
    elif role == 'cashier':
        await update.message.reply_text("🔍 КАССИР\n\nОтправьте Фамилию Имя")

# ========== АДМИН ==========
async def admin_stats(update, context):
    q = update.callback_query
    prs = get_promoters()
    if not prs:
        await q.edit_message_text("Нет промоутеров")
        return
    txt = "📊 СТАТИСТИКА\n\n"
    for pid, tg, name, bal in prs:
        nm = f"@{name}" if name else str(tg)
        cnt = len(get_people(pid))
        txt += f"{nm}\n💰 {bal} руб. | 👥 {cnt} чел.\n\n"
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def admin_promoters(update, context):
    q = update.callback_query
    prs = get_promoters()
    if not prs:
        await q.edit_message_text("Нет промоутеров")
        return
    kb = []
    for pid, tg, name, bal in prs:
        nm = f"@{name}" if name else str(tg)
        kb.append([InlineKeyboardButton(f"{nm} ({bal} руб.)", callback_data=f"view_{pid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    await q.edit_message_text("👥 ПРОМОУТЕРЫ", reply_markup=InlineKeyboardMarkup(kb))

async def view_promoter(update, context, pid):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT tg_id, name, balance FROM users WHERE id = ?", (pid,))
    tg, name, bal = c.fetchone()
    c.execute("SELECT name FROM people WHERE promoter_id = ?", (pid,))
    people = c.fetchall()
    conn.close()
    nm = f"@{name}" if name else str(tg)
    txt = f"👤 {nm}\n💰 Баланс: {bal} руб.\n👥 Людей: {len(people)}\n\n"
    if people:
        txt += "📋 СПИСОК:\n" + "\n".join([f"• {p[0]}" for p in people])
    else:
        txt += "Список пуст"
    kb = [
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"del_p_{pid}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="promoters")]
    ]
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def delete_promoter(update, context, pid):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT tg_id FROM users WHERE id = ?", (pid,))
    tg = c.fetchone()[0]
    c.execute("DELETE FROM users WHERE id = ?", (pid,))
    c.execute("DELETE FROM people WHERE promoter_id = ?", (pid,))
    conn.commit()
    conn.close()
    await q.edit_message_text("✅ Промоутер удален")
    await context.bot.send_message(tg, "❌ Ваша роль промоутера удалена")

async def admin_cashiers(update, context):
    q = update.callback_query
    cs = get_cashiers()
    if not cs:
        await q.edit_message_text("Нет кассиров")
        return
    kb = []
    for cid, tg, name in cs:
        nm = f"@{name}" if name else str(tg)
        kb.append([InlineKeyboardButton(nm, callback_data=f"del_c_{cid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    await q.edit_message_text("💳 КАССИРЫ\n\nНажмите для удаления", reply_markup=InlineKeyboardMarkup(kb))

async def delete_cashier(update, context, cid):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT tg_id FROM users WHERE id = ?", (cid,))
    tg = c.fetchone()[0]
    c.execute("DELETE FROM users WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    await q.edit_message_text("✅ Кассир удален")
    await context.bot.send_message(tg, "❌ Ваша роль кассира удалена")

async def admin_events(update, context):
    q = update.callback_query
    evs = get_events()
    txt = "📅 МЕРОПРИЯТИЯ\n\n" + "\n".join([f"• {e[1]}" for e in evs]) if evs else "Нет мероприятий"
    kb = [
        [InlineKeyboardButton("➕ Добавить", callback_data="add_event")],
        [InlineKeyboardButton("❌ Удалить", callback_data="del_event")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def add_event_start(update, context):
    await update.callback_query.edit_message_text("✍️ Введите название мероприятия:")
    context.user_data['step'] = 'event'

async def add_event(update, context):
    name = update.message.text.strip()
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO events (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Мероприятие '{name}' добавлено")
    context.user_data['step'] = None
    await start(update, context)

async def delete_event_list(update, context):
    q = update.callback_query
    evs = get_events()
    if not evs:
        await q.edit_message_text("Нет мероприятий")
        return
    kb = []
    for eid, name in evs:
        kb.append([InlineKeyboardButton(name, callback_data=f"del_e_{eid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="events")])
    await q.edit_message_text("❌ Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))

async def delete_event(update, context, eid):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("DELETE FROM events WHERE id = ?", (eid,))
    c.execute("DELETE FROM people WHERE event_id = ?", (eid,))
    conn.commit()
    conn.close()
    await q.edit_message_text("✅ Мероприятие удалено")

async def admin_reset(update, context):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT tg_id FROM users WHERE role = 'promoter'")
    promoters = c.fetchall()
    c.execute("DELETE FROM people")
    c.execute("UPDATE users SET balance = 0 WHERE role = 'promoter'")
    conn.commit()
    conn.close()
    for p in promoters:
        try:
            await context.bot.send_message(p[0], "📅 НОВЫЙ МЕСЯЦ!\n\nВсе списки и баланс обнулены")
        except:
            pass
    await q.edit_message_text("✅ Месяц сброшен")

# ========== ПРОМОУТЕР ==========
async def promo_lists(update, context):
    q = update.callback_query
    tg = q.from_user.id
    pid = get_promoter_by_tg(tg)
    if not pid:
        await q.edit_message_text("Ошибка")
        return
    people = get_people(pid)
    if not people:
        await q.edit_message_text("📭 Список пуст")
        return
    txt = "📋 ВАШ СПИСОК\n\n" + "\n".join([f"• {p}" for p in people])
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def promo_stats(update, context):
    q = update.callback_query
    tg = q.from_user.id
    pid = get_promoter_by_tg(tg)
    if not pid:
        await q.edit_message_text("Ошибка")
        return
    bal = get_balance(pid)
    cnt = len(get_people(pid))
    txt = f"💰 БАЛАНС: {bal} руб.\n\n📊 ДОБАВЛЕНО: {cnt} чел."
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def promo_add(update, context):
    q = update.callback_query
    evs = get_events()
    if not evs:
        await q.edit_message_text("Нет мероприятий")
        return
    kb = []
    for eid, name in evs:
        kb.append([InlineKeyboardButton(name, callback_data=f"add_p_{eid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    await q.edit_message_text("📅 Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))

async def add_person_start(update, context, eid):
    context.user_data['eid'] = eid
    await update.callback_query.edit_message_text("✍️ Введите Фамилию Имя:")
    context.user_data['step'] = 'add'

async def add_person(update, context):
    name = update.message.text.strip()
    tg = update.effective_user.id
    pid = get_promoter_by_tg(tg)
    eid = context.user_data.get('eid')
    if not pid:
        await update.message.reply_text("Ошибка")
        return
    add_person(pid, name, eid)
    await update.message.reply_text(f"✅ {name} добавлен")
    context.user_data['step'] = None
    await start(update, context)

async def promo_del(update, context):
    q = update.callback_query
    evs = get_events()
    if not evs:
        await q.edit_message_text("Нет мероприятий")
        return
    kb = []
    for eid, name in evs:
        kb.append([InlineKeyboardButton(name, callback_data=f"del_p_{eid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    await q.edit_message_text("📅 Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))

async def del_person_start(update, context, eid):
    context.user_data['eid'] = eid
    await update.callback_query.edit_message_text("🗑 Введите Фамилию Имя:")
    context.user_data['step'] = 'del'

async def del_person(update, context):
    name = update.message.text.strip()
    tg = update.effective_user.id
    pid = get_promoter_by_tg(tg)
    eid = context.user_data.get('eid')
    if not pid:
        await update.message.reply_text("Ошибка")
        return
    res = del_person(pid, name, eid)
    if res:
        await update.message.reply_text(f"🗑 {name} удален")
    else:
        await update.message.reply_text(f"❌ {name} не найден")
    context.user_data['step'] = None
    await start(update, context)

# ========== КАССИР ==========
async def check_person(update, context):
    name = update.message.text.strip()
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''SELECT p.id, p.name, u.id, u.tg_id, e.name FROM people p 
                 JOIN users u ON p.promoter_id = u.id 
                 JOIN events e ON p.event_id = e.id 
                 WHERE p.name = ?''', (name,))
    res = c.fetchone()
    conn.close()
    if not res:
        await update.message.reply_text("❌ Человека нет в списках")
        return
    pid, pname, promoter_id, promoter_tg, evname = res
    context.user_data['pending'] = (pid, pname, promoter_id, promoter_tg, evname)
    kb = [[InlineKeyboardButton("✅ ПОДТВЕРДИТЬ", callback_data="ok"), InlineKeyboardButton("❌ ОТМЕНА", callback_data="no")]]
    await update.message.reply_text(f"🔔 {pname}\n📅 {evname}", reply_markup=InlineKeyboardMarkup(kb))

async def confirm(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "no":
        await q.edit_message_text("❌ Отменено")
        return
    if q.data == "ok":
        pending = context.user_data.get('pending')
        if not pending:
            await q.edit_message_text("Ошибка")
            return
        pid, name, promoter_id, promoter_tg, evname = pending
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT id FROM people WHERE id = ?", (pid,))
        if not c.fetchone():
            await q.edit_message_text("⚠️ Уже отмечен")
            conn.close()
            return
        c.execute("DELETE FROM people WHERE id = ?", (pid,))
        cnt = len(get_people(promoter_id))
        if cnt >= 60: rate = 150
        elif cnt >= 30: rate = 130
        else: rate = 120
        add_balance(promoter_id, rate)
        new_bal = get_balance(promoter_id)
        conn.commit()
        conn.close()
        await q.edit_message_text(f"✅ ПОДТВЕРЖДЕНО!\n\n👤 {name}\n📅 {evname}")
        await context.bot.send_message(promoter_tg, f"🎉 ПРИШЕЛ ГОСТЬ!\n\n👤 {name}\n📅 {evname}\n💰 +{rate} руб.\n💰 Баланс: {new_bal} руб.")
        del context.user_data['pending']

# ========== ОБРАБОТЧИКИ ==========
async def callback_handler(update, context):
    q = update.callback_query
    d = q.data
    
    if d == "back":
        await start(update, context)
    elif d == "stats":
        await admin_stats(update, context)
    elif d == "promoters":
        await admin_promoters(update, context)
    elif d == "cashiers":
        await admin_cashiers(update, context)
    elif d == "events":
        await admin_events(update, context)
    elif d == "reset":
        await admin_reset(update, context)
    elif d == "add_event":
        await add_event_start(update, context)
    elif d == "del_event":
        await delete_event_list(update, context)
    elif d == "mylists":
        await promo_lists(update, context)
    elif d == "add":
        await promo_add(update, context)
    elif d == "del":
        await promo_del(update, context)
    elif d == "stats_p":
        await promo_stats(update, context)
    elif d.startswith("view_"):
        await view_promoter(update, context, int(d.split("_")[1]))
    elif d.startswith("del_p_"):
        await delete_promoter(update, context, int(d.split("_")[2]))
    elif d.startswith("del_c_"):
        await delete_cashier(update, context, int(d.split("_")[2]))
    elif d.startswith("del_e_"):
        await delete_event(update, context, int(d.split("_")[2]))
    elif d.startswith("add_p_"):
        await add_person_start(update, context, int(d.split("_")[2]))
    elif d.startswith("del_p_"):
        await del_person_start(update, context, int(d.split("_")[2]))

async def message_handler(update, context):
    step = context.user_data.get('step')
    if step == 'event':
        await add_event(update, context)
    elif step == 'add':
        await add_person(update, context)
    elif step == 'del':
        await del_person(update, context)
    else:
        role = get_role(update.effective_user.id)
        if role == 'cashier':
            await check_person(update, context)
        else:
            await update.message.reply_text("Напишите /start")

async def set_role(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только администратор")
        return
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Использование: /setrole ID promoter|cashier")
            return
        tg = int(args[0])
        role = args[1]
        if role not in ['promoter', 'cashier']:
            await update.message.reply_text("Роль: promoter или cashier")
            return
        try:
            chat = await context.bot.get_chat(tg)
            name = chat.username
        except:
            name = None
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (tg_id, name, role, balance) VALUES (?, ?, ?, 0)", (tg, name, role))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Роль {role} назначена")
        await context.bot.send_message(tg, f"✅ Вам назначена роль {role}!\nНапишите /start")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ========== ЗАПУСК ==========
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CallbackQueryHandler(confirm, pattern="^(ok|no)$"))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("✅ БОТ ЗАПУЩЕН!")
    app.run_polling()

if __name__ == '__main__':
    main()
