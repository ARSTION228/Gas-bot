import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ========== НАСТРОЙКИ ==========
TOKEN = "8680724321:AAGmcU8I5Z1T9d8kHrqCS5qiZpmLpvPnLY0"  # ← ЗАМЕНИ
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
            role TEXT,
            balance INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            promoter_id INTEGER,
            is_confirmed INTEGER DEFAULT 0
        )
    ''')
    cur.execute('INSERT OR IGNORE INTO users (telegram_id, role) VALUES (?, ?)', (ADMIN_ID, 'admin'))
    conn.commit()
    conn.close()

# ========== ВСПОМОГАТЕЛЬНЫЕ ==========
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

# ========== ГЛАВНОЕ МЕНЮ ==========
async def start(update, context):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    
    if not user:
        await update.message.reply_text(f"👋 Добро пожаловать!\nВаш ID: {user_id}\nОжидайте назначения роли.")
        await context.bot.send_message(ADMIN_ID, f"🔔 Новый пользователь: ID {user_id}")
        return
    
    role = user[0]
    
    if role == 'admin':
        await update.message.reply_text(
            "👑 АДМИНИСТРАТОР\n\n"
            "Команды:\n"
            "/setrole ID promoter - назначить промоутера\n"
            "/setrole ID cashier - назначить кассира\n"
            "/stats - статистика\n"
            "/reset - сбросить месяц"
        )
    elif role == 'promoter':
        keyboard = [
            [InlineKeyboardButton("📋 Мои списки", callback_data="lists")],
            [InlineKeyboardButton("➕ Добавить", callback_data="add")],
            [InlineKeyboardButton("❌ Удалить", callback_data="delete")],
            [InlineKeyboardButton("💰 Статистика", callback_data="stats")]
        ]
        await update.message.reply_text("🔧 МЕНЮ ПРОМОУТЕРА", reply_markup=InlineKeyboardMarkup(keyboard))
    elif role == 'cashier':
        await update.message.reply_text("🔍 КАССИР\n\nПросто отправьте Фамилию Имя человека.")

# ========== МЕНЮ ПРОМОУТЕРА (КНОПКИ) ==========
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    promoter = cur.fetchone()
    conn.close()
    
    if not promoter:
        await query.edit_message_text("Ошибка: вы не зарегистрированы")
        return
    
    promoter_id = promoter[0]
    
    if action == "lists":
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT full_name, is_confirmed FROM lists WHERE promoter_id = ?", (promoter_id,))
        people = cur.fetchall()
        conn.close()
        
        if not people:
            await query.edit_message_text("📭 Список пуст")
            return
        
        text = "📋 ВАШ СПИСОК:\n\n"
        for name, status in people:
            icon = "✅" if status else "⏳"
            text += f"{icon} {name}\n"
        await query.edit_message_text(text)
    
    elif action == "add":
        context.user_data['action'] = 'add'
        await query.edit_message_text("✍️ Введите Фамилию Имя:")
    
    elif action == "delete":
        context.user_data['action'] = 'delete'
        await query.edit_message_text("🗑 Введите Фамилию Имя для удаления:")
    
    elif action == "stats":
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE id = ?", (promoter_id,))
        balance = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ?", (promoter_id,))
        total_added = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM lists WHERE promoter_id = ? AND is_confirmed = 1", (promoter_id,))
        total_confirmed = cur.fetchone()[0]
        conn.close()
        
        monthly = get_monthly_count(promoter_id)
        rate = get_rate(monthly)
        
        text = (
            f"💰 БАЛАНС: {balance} руб.\n"
            f"📊 ЗА МЕСЯЦ: {monthly} чел. (ставка {rate} руб.)\n"
            f"📈 ВСЕГО: {total_confirmed}/{total_added} чел."
        )
        await query.edit_message_text(text)

# ========== ОБРАБОТКА ТЕКСТА ==========
async def handle_text(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE telegram_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    
    if not user:
        await update.message.reply_text("❌ Вы не зарегистрированы")
        return
    
    role = user[0]
    
    # ПРОМОУТЕР - добавление/удаление
    if role == 'promoter' and 'action' in context.user_data:
        action = context.user_data['action']
        del context.user_data['action']
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
        promoter_id = cur.fetchone()[0]
        
        if action == 'add':
            cur.execute("INSERT INTO lists (full_name, promoter_id, is_confirmed) VALUES (?, ?, 0)", (text, promoter_id))
            conn.commit()
            await update.message.reply_text(f"✅ {text} ДОБАВЛЕН")
        
        elif action == 'delete':
            cur.execute("DELETE FROM lists WHERE full_name = ? AND promoter_id = ? AND is_confirmed = 0", (text, promoter_id))
            conn.commit()
            if cur.rowcount > 0:
                await update.message.reply_text(f"🗑 {text} УДАЛЕН")
            else:
                await update.message.reply_text(f"❌ {text} НЕ НАЙДЕН")
        conn.close()
        
        # Показываем меню после действия
        keyboard = [
            [InlineKeyboardButton("📋 Мои списки", callback_data="lists")],
            [InlineKeyboardButton("➕ Добавить", callback_data="add")],
            [InlineKeyboardButton("❌ Удалить", callback_data="delete")],
            [InlineKeyboardButton("💰 Статистика", callback_data="stats")]
        ]
        await update.message.reply_text("🔧 МЕНЮ ПРОМОУТЕРА", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # КАССИР - проверка человека
    if role == 'cashier':
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('''
            SELECT l.id, l.full_name, u.id 
            FROM lists l
            JOIN users u ON l.promoter_id = u.id
            WHERE l.full_name = ? AND l.is_confirmed = 0
        ''', (text,))
        result = cur.fetchone()
        conn.close()
        
        if not result:
            await update.message.reply_text("❌ ЧЕЛОВЕКА НЕТ В СПИСКАХ")
            return
        
        list_id, name, promoter_id = result
        
        keyboard = [[
            InlineKeyboardButton("✅ ПОДТВЕРДИТЬ", callback_data=f"ok_{list_id}_{promoter_id}"),
            InlineKeyboardButton("❌ ОТМЕНА", callback_data="no")
        ]]
        await update.message.reply_text(f"🔔 НАЙДЕН: {name}", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    await update.message.reply_text("❌ НЕИЗВЕСТНАЯ КОМАНДА")

# ========== ПОДТВЕРЖДЕНИЕ КАССИРА ==========
async def confirm_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "no":
        await query.edit_message_text("❌ ОТМЕНЕНО")
        return
    
    if query.data.startswith("ok_"):
        _, list_id, promoter_id = query.data.split("_")
        list_id = int(list_id)
        promoter_id = int(promoter_id)
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Проверяем, не подтвержден ли уже
        cur.execute("SELECT is_confirmed FROM lists WHERE id = ?", (list_id,))
        if cur.fetchone()[0] == 1:
            await query.edit_message_text("⚠️ УЖЕ ПОДТВЕРЖДЕН")
            conn.close()
            return
        
        # Считаем сколько уже подтверждено за месяц
        monthly = get_monthly_count(promoter_id)
        rate = get_rate(monthly)
        
        # Отмечаем как подтвержденного
        cur.execute("UPDATE lists SET is_confirmed = 1 WHERE id = ?", (list_id,))
        
        # Начисляем деньги
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (rate, promoter_id))
        
        # Получаем новый баланс
        cur.execute("SELECT balance FROM users WHERE id = ?", (promoter_id,))
        new_balance = cur.fetchone()[0]
        
        conn.commit()
        
        # Получаем Telegram ID промоутера
        cur.execute("SELECT telegram_id FROM users WHERE id = ?", (promoter_id,))
        promoter_tg = cur.fetchone()
        conn.close()
        
        await query.edit_message_text(f"✅ ПОДТВЕРЖДЕНО!\n💰 +{rate} руб.\n💰 БАЛАНС: {new_balance} руб.")
        
        # Уведомляем промоутера
        if promoter_tg:
            await context.bot.send_message(promoter_tg[0], f"🎉 ПРИШЕЛ ГОСТЬ!\n💰 +{rate} руб.\n💰 БАЛАНС: {new_balance} руб.")

# ========== АДМИН КОМАНДЫ ==========
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
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (telegram_id, role, balance) VALUES (?, ?, 0)", (tg_id, role))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Роль {role} назначена {tg_id}")
        await context.bot.send_message(tg_id, f"✅ Вам назначена роль {role}")
        
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def stats_all(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только администратор")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, role, balance FROM users WHERE role = 'promoter'")
    promoters = cur.fetchall()
    conn.close()
    
    if not promoters:
        await update.message.reply_text("Нет промоутеров")
        return
    
    text = "📊 СТАТИСТИКА:\n\n"
    for tg_id, role, balance in promoters:
        monthly = get_monthly_count(tg_id)
        text += f"ID {tg_id}: {monthly} чел., {balance} руб.\n"
    
    await update.message.reply_text(text)

async def reset_month(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Только администратор")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Обнуляем статистику (просто удаляем подтвержденных)
    cur.execute("UPDATE lists SET is_confirmed = 0")
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ Месяц сброшен. Статистика обнулена.")

# ========== ЗАПУСК ==========
def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setrole", set_role))
    app.add_handler(CommandHandler("stats", stats_all))
    app.add_handler(CommandHandler("reset", reset_month))
    
    # Обработчики
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(lists|add|delete|stats)$"))
    app.add_handler(CallbackQueryHandler(confirm_handler, pattern="^(ok_|no)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ БОТ ЗАПУЩЕН!")
    app.run_polling()

if __name__ == '__main__':
    main()
