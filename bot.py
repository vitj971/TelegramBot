import os
import random
import time
import sqlite3
import asyncio
from aiohttp import web

from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

GLOBAL_CD = 3
EARN_CD = 3
DAILY_CD = 24 * 60 * 60

# ---------------- DB ----------------

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0,
    last_action INTEGER DEFAULT 0,
    last_earn INTEGER DEFAULT 0
)
""")
conn.commit()


def ensure_user(user):
    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, balance, last_daily, last_action, last_earn)
        VALUES (?, ?, ?, 0, 0, 0, 0)
    """, (user.id, user.username or "", user.first_name or "Игрок"))

    cur.execute("""
        UPDATE users
        SET username=?, first_name=?
        WHERE user_id=?
    """, (user.username or "", user.first_name or "Игрок", user.id))

    conn.commit()


def get_user(user_id):
    cur.execute("""
        SELECT username, first_name, balance, last_daily, last_action, last_earn
        FROM users
        WHERE user_id=?
    """, (user_id,))
    return cur.fetchone()


def update_user(user_id, username, first_name, balance, last_daily, last_action, last_earn):
    cur.execute("""
        UPDATE users
        SET username=?, first_name=?, balance=?, last_daily=?, last_action=?, last_earn=?
        WHERE user_id=?
    """, (username, first_name, balance, last_daily, last_action, last_earn, user_id))
    conn.commit()


def get_top(limit=10):
    cur.execute("""
        SELECT username, first_name, balance
        FROM users
        ORDER BY balance DESC
        LIMIT ?
    """, (limit,))
    return cur.fetchall()


# ---------------- COOLDOWNS ----------------

def global_cd(user_id):
    cur.execute("SELECT last_action FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return time.time() - row[0] < GLOBAL_CD


def set_global_cd(user_id):
    cur.execute("""
        UPDATE users
        SET last_action=?
        WHERE user_id=?
    """, (int(time.time()), user_id))
    conn.commit()


def earn_cd(user_id):
    cur.execute("SELECT last_earn FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return time.time() - row[0] < EARN_CD


def set_earn_cd(user_id):
    cur.execute("""
        UPDATE users
        SET last_earn=?
        WHERE user_id=?
    """, (int(time.time()), user_id))
    conn.commit()


# ---------------- BOT ----------------

app = ApplicationBuilder().token(TOKEN).build()


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    await update.message.reply_text("👋 Бот готов! /earn /pay /daily /balance /top")


# ---------------- BALANCE ----------------

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    if global_cd(user.id):
        return await update.message.reply_text("⏳ 3 сек")
    set_global_cd(user.id)

    _, _, bal, _, _, _ = get_user(user.id)
    await update.message.reply_text(f"💰 Баланс: {bal}")


# ---------------- EARN (FIXED ANTI-ABUSE) ----------------

async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    if earn_cd(user.id):
        return await update.message.reply_text("⏳ Подожди 3 сек")

    set_earn_cd(user.id)

    username, name, bal, _, _, _ = get_user(user.id)

    roll = random.random()

    if roll < 0.69:
        coins = random.randint(10, 35)
    elif roll < 0.89:
        coins = random.randint(36, 70)
    elif roll < 0.96:
        coins = random.randint(71, 120)
    elif roll < 0.993:
        coins = random.randint(121, 155)
    else:
        coins = random.randint(233, 855)

    bal += coins

    update_user(user.id, username, name, bal, 0, 0, int(time.time()))

    await update.message.reply_text(f"💰 {name} получил {coins} Бебракоинов! 🎉")


# ---------------- PAY ----------------

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    if global_cd(user.id):
        return await update.message.reply_text("⏳ 3 сек")
    set_global_cd(user.id)

    if not context.args:
        return await update.message.reply_text("Используй: /pay 100 (reply или @user)")

    try:
        amount = int(context.args[0])
    except:
        return await update.message.reply_text("❌ Неверная сумма")

    if amount < 1 or amount > 1_000_000:
        return await update.message.reply_text("❌ 1 - 1 000 000")

    sender = get_user(user.id)
    sender_balance = sender[2]

    if sender_balance < amount:
        return await update.message.reply_text("❌ Нет денег")

    receiver = None

    if update.message.reply_to_message:
        receiver = update.message.reply_to_message.from_user

    elif len(context.args) > 1:
        target = context.args[1].replace("@", "")
        cur.execute("SELECT user_id FROM users WHERE username=?", (target,))
        row = cur.fetchone()

        if row:
            receiver = type("obj", (), {
                "id": row[0],
                "username": target,
                "first_name": target
            })()

    if not receiver:
        return await update.message.reply_text("❌ Игрок не найден")

    ensure_user(receiver)

    _, _, receiver_balance, _, _, _ = get_user(receiver.id)

    sender_balance -= amount
    receiver_balance += amount

    update_user(user.id, user.username or "", user.first_name or "Игрок",
                sender_balance, 0, 0, int(time.time()))

    update_user(receiver.id, receiver.username or "", receiver.first_name or "Игрок",
                receiver_balance, 0, 0, 0)

    await update.message.reply_text(
        f"{user.first_name} дал {amount} Бебракоинов {receiver.first_name} 💸"
    )


# ---------------- DAILY ----------------

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    if global_cd(user.id):
        return await update.message.reply_text("⏳ 3 сек")
    set_global_cd(user.id)

    username, name, bal, last_daily, _, _ = get_user(user.id)
    now = int(time.time())

    if now - last_daily < DAILY_CD:
        rem = DAILY_CD - (now - last_daily)
        return await update.message.reply_text(f"⏳ Жди {rem//3600}ч {(rem%3600)//60}м")

    roll = random.random()

    if roll < 0.33:
        reward = 100
    elif roll < 0.66:
        reward = 150
    elif roll < 0.99:
        reward = 200
    else:
        reward = 750

    bal += reward

    update_user(user.id, username, name, bal, now, 0, 0)

    if reward == 750:
        text = f"🍀 Счастливчик {name} получил {reward}!"
    else:
        text = f"✨ {name} получил {reward} Бебракоинов"

    await update.message.reply_text(text)


# ---------------- TOP ----------------

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if global_cd(update.effective_user.id):
        return await update.message.reply_text("⏳ 3 сек")
    set_global_cd(update.effective_user.id)

    data = get_top(10)

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 Топ игроков:\n\n"

    for i, (username, name, bal) in enumerate(data):
        display = f"@{username}" if username else name
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {display} — {bal} 💰\n"

    await update.message.reply_text(text)


# ---------------- COMMANDS ----------------

async def set_commands():
    await app.bot.set_my_commands([
        BotCommand("start", "Старт"),
        BotCommand("earn", "Заработок"),
        BotCommand("pay", "Перевод"),
        BotCommand("daily", "Дейли"),
        BotCommand("balance", "Баланс"),
        BotCommand("top", "Топ"),
    ])


# ---------------- WEBHOOK ----------------

async def webhook(request):
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return web.Response(text="ok")


async def main():
    await app.initialize()
    await app.start()

    await set_commands()

    server = web.Application()
    server.router.add_post("/webhook", webhook)

    runner = web.AppRunner(server)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    repl_slug = os.getenv("REPL_SLUG")
    repl_owner = os.getenv("REPL_OWNER")

    url = f"https://{repl_slug}.{repl_owner}.repl.co/webhook"

    await app.bot.set_webhook(url=url)

    print("🤖 Bot running:", url)

    while True:
        await asyncio.sleep(3600)


# ---------------- HANDLERS ----------------

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("earn", earn))
app.add_handler(CommandHandler("pay", pay))
app.add_handler(CommandHandler("daily", daily))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("top", top))


if __name__ == "__main__":
    asyncio.run(main())