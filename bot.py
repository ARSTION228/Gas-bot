import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext

TOKEN = "8680724321:AAGmcU8I5Z1T9d8kHrqCS5qiZpmLpvPnLY0"
ADMIN_ID = 355936751

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

def start(update, context):
    tg = update.effective_user.id
    role = get_role(tg)
    if not role:
        update.message.reply_text(f"👋 Ваш ID: {tg}\nОжидайте назначения роли")
        context.bot.send_message(ADMIN_ID, f"Новый пользователь: {tg}")
        return
    if role == 'admin':
        kb = [[InlineKeyboardButton("📊 Статистика", callback_data="stats")],
              [InlineKeyboardButton("👥 Промоутеры", callback_data="promoters")],
              [InlineKeyboardButton("💳 Кассиры", callback_data="cashiers")],
              [InlineKeyboardButton("📅 Мероприятия", callback_data="events")],
              [InlineKeyboardButton("🔄 Сброс месяца", callback_data="reset")]]
        update.message.reply_text("👑 АДМИН", reply_markup=InlineKeyboardMarkup(kb))
    elif role == 'promoter':
        kb = [[InlineKeyboardButton("📋 Мои списки", callback_data="mylists")],
              [InlineKeyboardButton("➕ Добавить", callback_data="add")],
              [InlineKeyboardButton("❌ Удалить", callback_data="del")],
              [InlineKeyboardButton("💰 Статистика", callback_data="stats_p")]]
        update.message.reply_text("🔧 ПРОМОУТЕР", reply_markup=InlineKeyboardMarkup(kb))
    elif role == 'cashier':
        update.message.reply_text("🔍 КАССИР\n\nОтправьте Фамилию Имя")

def admin_stats(update, context):
    q = update.callback_query
    prs = get_promoters()
    if not prs:
        q.edit_message_text("Нет промоутеров")
        return
    txt = "📊 СТАТИСТИКА\n\n"
    for pid, tg, name, bal in prs:
        nm = f"@{name}" if name else str(tg)
        cnt = len(get_people(pid))
        txt += f"{nm}\n💰 {bal} руб. | 👥 {cnt} чел.\n\n"
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

def admin_promoters(update, context):
    q = update.callback_query
    prs = get_promoters()
    if not prs:
        q.edit_message_text("Нет промоутеров")
        return
    kb = []
    for pid, tg, name, bal in prs:
        nm = f"@{name}" if name else str(tg)
        kb.append([InlineKeyboardButton(f"{nm} ({bal} руб.)", callback_data=f"view_{pid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    q.edit_message_text("👥 ПРОМОУТЕРЫ", reply_markup=InlineKeyboardMarkup(kb))

def view_promoter(update, context, pid):
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
    kb = [[InlineKeyboardButton("🗑 Удалить", callback_data=f"del_p_{pid}")],
          [InlineKeyboardButton("🔙 Назад", callback_data="promoters")]]
    q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

def delete_promoter(update, context, pid):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT tg_id FROM users WHERE id = ?", (pid,))
    tg = c.fetchone()[0]
    c.execute("DELETE FROM users WHERE id = ?", (pid,))
    c.execute("DELETE FROM people WHERE promoter_id = ?", (pid,))
    conn.commit()
    conn.close()
    q.edit_message_text("✅ Промоутер удален")
    context.bot.send_message(tg, "❌ Ваша роль промоутера удалена")

def admin_cashiers(update, context):
    q = update.callback_query
    cs = get_cashiers()
    if not cs:
        q.edit_message_text("Нет кассиров")
        return
    kb = []
    for cid, tg, name in cs:
        nm = f"@{name}" if name else str(tg)
        kb.append([InlineKeyboardButton(nm, callback_data=f"del_c_{cid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    q.edit_message_text("💳 КАССИРЫ\n\nНажмите для удаления", reply_markup=InlineKeyboardMarkup(kb))

def delete_cashier(update, context, cid):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT tg_id FROM users WHERE id = ?", (cid,))
    tg = c.fetchone()[0]
    c.execute("DELETE FROM users WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    q.edit_message_text("✅ Кассир удален")
    context.bot.send_message(tg, "❌ Ваша роль кассира удалена")

def admin_events(update, context):
    q = update.callback_query
    evs = get_events()
    txt = "📅 МЕРОПРИЯТИЯ\n\n" + "\n".join([f"• {e[1]}" for e in evs]) if evs else "Нет мероприятий"
    kb = [[InlineKeyboardButton("➕ Добавить", callback_data="add_event")],
          [InlineKeyboardButton("❌ Удалить", callback_data="del_event")],
          [InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

def add_event_start(update, context):
    update.callback_query.edit_message_text("✍️ Введите название мероприятия:")
    context.user_data['step'] = 'event'

def add_event(update, context):
    name = update.message.text.strip()
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO events (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    update.message.reply_text(f"✅ Мероприятие '{name}' добавлено")
    context.user_data['step'] = None
    start(update, context)

def delete_event_list(update, context):
    q = update.callback_query
    evs = get_events()
    if not evs:
        q.edit_message_text("Нет мероприятий")
        return
    kb = []
    for eid, name in evs:
        kb.append([InlineKeyboardButton(name, callback_data=f"del_e_{eid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="events")])
    q.edit_message_text("❌ Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))

def delete_event(update, context, eid):
    q = update.callback_query
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("DELETE FROM events WHERE id = ?", (eid,))
    c.execute("DELETE FROM people WHERE event_id = ?", (eid,))
    conn.commit()
    conn.close()
    q.edit_message_text("✅ Мероприятие удалено")

def admin_reset(update, context):
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
            context.bot.send_message(p[0], "📅 НОВЫЙ МЕСЯЦ!\n\nВсе списки и баланс обнулены")
        except:
            pass
    q.edit_message_text("✅ Месяц сброшен")

def promo_lists(update, context):
    q = update.callback_query
    tg = q.from_user.id
    pid = get_promoter_by_tg(tg)
    if not pid:
        q.edit_message_text("Ошибка")
        return
    people = get_people(pid)
    if not people:
        q.edit_message_text("📭 Список пуст")
        return
    txt = "📋 ВАШ СПИСОК\n\n" + "\n".join([f"• {p}" for p in people])
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

def promo_stats(update, context):
    q = update.callback_query
    tg = q.from_user.id
    pid = get_promoter_by_tg(tg)
    if not pid:
        q.edit_message_text("Ошибка")
        return
    bal = get_balance(pid)
    cnt = len(get_people(pid))
    txt = f"💰 БАЛАНС: {bal} руб.\n\n📊 ДОБАВЛЕНО: {cnt} чел."
    kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

def promo_add(update, context):
    q = update.callback_query
    evs = get_events()
    if not evs:
        q.edit_message_text("Нет мероприятий")
        return
    kb = []
    for eid, name in evs:
        kb.append([InlineKeyboardButton(name, callback_data=f"add_p_{eid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    q.edit_message_text("📅 Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))

def add_person_start(update, context, eid):
    context.user_data['eid'] = eid
    update.callback_query.edit_message_text("✍️ Введите Фамилию Имя:")
    context.user_data['step'] = 'add'

def add_person(update, context):
    name = update.message.text.strip()
    tg = update.effective_user.id
    pid = get_promoter_by_tg(tg)
    eid = context.user_data.get('eid')
    if not pid:
        update.message.reply_text("Ошибка")
        return
    add_person(pid, name, eid)
    update.message.reply_text(f"✅ {name} добавлен")
    context.user_data['step'] = None
    start(update, context)

def promo_del(update, context):
    q = update.callback_query
    evs = get_events()
    if not evs:
        q.edit_message_text("Нет мероприятий")
        return
    kb = []
    for eid, name in evs:
        kb.append([InlineKeyboardButton(name, callback_data=f"del_p_{eid}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    q.edit_message_text("📅 Выберите мероприятие:", reply_markup=InlineKeyboardMarkup(kb))

def del_person_start(update, context, eid):
    context.user_data['eid'] = eid
    update.callback_query.edit_message_text("🗑 Введите Фамилию Имя:")
    context.user_data['step'] = 'del'

def del_person(update, context):
    name = update.message.text.strip()
    tg = update.effective_user.id
    pid = get_promoter_by_tg(tg)
    eid = context.user_data.get('eid')
    if not pid:
        update.message.reply_text("Ошибка")
        return
    res = del_person(pid, name, eid)
    if res:
        update.message.reply_text(f"🗑 {name} удален")
    else:
        update.message.reply_text(f"❌ {name} не найден")
    context.user_data['step'] = None
    start(update, context)

def check_person(update, context):
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
        update.message.reply_text("❌ Человека нет в списках")
        return
    pid, pname, promoter_id, promoter_tg, evname = res
    context.user_data['pending'] = (pid, pname, promoter_id, promoter_tg, evname)
    kb = [[InlineKeyboardButton("✅ ПОДТВЕРДИТЬ", callback_data="ok"), 
           InlineKeyboardButton("❌ ОТМЕНА", callback_data="no")]]
    update.message.reply_text(f"🔔 {pname}\n📅 {evname}", reply_markup=InlineKeyboardMarkup(kb))

def confirm(update, context):
    q = update.callback_query
    q.answer()
    if q.data == "no":
        q.edit_message_text("❌ Отменено")
        return
    if q.data == "ok":
        pending = context.user_data.get('pending')
        if not pending:
            q.edit_message_text("Ошибка")
            return
        pid, name, promoter_id, promoter_tg, evname = pending
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("SELECT id FROM people WHERE id = ?", (pid,))
        if not c.fetchone():
            q.edit_message_text("⚠️ Уже отмечен")
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
        q.edit_message_text(f"✅ ПОДТВЕРЖДЕНО!\n\n👤 {name}\n📅 {evname}")
        context.bot.send_message(promoter_tg, f"🎉 ПРИШЕЛ ГОСТЬ!\n\n👤 {name}\n📅 {evname}\n💰 +{rate} руб.\n💰 Баланс: {new_bal} руб.")
        del context.user_data['pending']

def callback_handler(update, context):
    q = update.callback_query
    d = q.data
    
    if d == "back":
        start(update, context)
    elif d == "stats":
        admin_stats(update, context)
    elif d == "promoters":
        admin_promoters(update, context)
    elif d == "cashiers":
        admin_cashiers(update, context)
    elif d == "events":
        admin_events(update, context)
    elif d == "reset":
        admin_reset(update, context)
    elif d == "add_event":
        add_event_start(update, context)
    elif d == "del_event":
        delete_event_list(update, context)
    elif d == "mylists":
        promo_lists(update, context)
    elif d == "add":
        promo_add(update, context)
    elif d == "del":
        promo_del(update, context)
    elif d == "stats_p":
        promo_stats(update, context)
    elif d.startswith("view_"):
        view_promoter(update, context, int(d.split("_")[1]))
    elif d.startswith("del_p_"):
        if len(d.split("_")) == 3:
            delete_promoter(update, context, int(d.split("_")[2]))
        else:
            del_person_start(update, context, int(d.split("_")[2]))
    elif d.startswith("del_c_"):
        delete_cashier(update, context, int(d.split("_")[2]))
    elif d.startswith("del_e_"):
        delete_event(update, context, int(d.split("_")[2]))
    elif d.startswith("add_p_"):
        add_person_start(update, context, int(d.split("_")[2]))

def message_handler(update, context):
    step = context.user_data.get('step')
    if step == 'event':
        add_event(update, context)
    elif step == 'add':
        add_person(update, context)
    elif step == 'del':
        del_person(update, context)
    else:
        role = get_role(update.effective_user.id)
        if role == 'cashier':
            check_person(update, context)
        else:
            update.message.reply_text("Напишите /start")

def set_role(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("⛔ Только администратор")
        return
    try:
        args = context.args
        if len(args) != 2:
            update.message.reply_text("Использование: /setrole ID promoter|cashier")
            return
        tg = int(args[0])
        role = args[1]
        if role not in ['promoter', 'cashier']:
            update.message.reply_text("Роль: promoter или cashier")
            return
        try:
            chat = context.bot.get_chat(tg)
            name = chat.username
        except:
            name = None
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (tg_id, name, role, balance) VALUES (?, ?, ?, 0)", (tg, name, role))
        conn.commit()
        conn.close()
        update.message.reply_text(f"✅ Роль {role} назначена")
        context.bot.send_message(tg, f"✅ Вам назначена роль {role}!\nНапишите /start")
    except Exception as e:
        update.message.reply_text(f"❌ Ошибка: {e}")

def main():
    init_db()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("setrole", set_role))
    dp.add_handler(CallbackQueryHandler(confirm, pattern="^(ok|no)$"))
    dp.add_handler(CallbackQueryHandler(callback_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    
    print("✅ БОТ ЗАПУЩЕН!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
