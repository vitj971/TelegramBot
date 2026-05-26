import os
import random
import time
import sqlite3

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# ---------------- CONFIG ----------------

TOKEN = os.getenv("8698374492:AAHsKMRR_FRW-9rLoTh-6qxow0AshOpytmM")

if not TOKEN:
    raise ValueError("8698374492:AAHsKMRR_FRW-9rLoTh-6qxow0AshOpytmM не найден")

CD_SHORT = 3
CD_EARN = 4 * 60 * 60
CD_DAILY = 24 * 60 * 60

# ---------------- DATABASE ----------------

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER DEFAULT 0,
    last_start INTEGER DEFAULT 0,
    last_balance INTEGER DEFAULT 0,
    last_pay INTEGER DEFAULT 0,
    last_earn INTEGER DEFAULT 0,
    last_daily INTEGER DEFAULT 0
)
""")

conn.commit()

# ---------------- FUNCTIONS ----------------

def ensure_user(user):
    cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, balance,
         last_start, last_balance, last_pay,
         last_earn, last_daily)
        VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0)
    """, (
        user.id,
        user.username or "",
        user.first_name or "Игрок"
    ))

    cur.execute("""
        UPDATE users
        SET username=?, first_name=?
        WHERE user_id=?
    """, (
        user.username or "",
        user.first_name or "Игрок",
        user.id
    ))

    conn.commit()


def get_user(user_id):
    cur.execute("""
        SELECT username, first_name, balance,
               last_start, last_balance,
               last_pay, last_earn, last_daily
        FROM users
        WHERE user_id=?
    """, (user_id,))
    return cur.fetchone()


def update_field(user_id, field, value):
    cur.execute(
        f"UPDATE users SET {field}=? WHERE user_id=?",
        (value, user_id)
    )
    conn.commit()


def update_balance(user_id, balance):
    cur.execute(
        "UPDATE users SET balance=? WHERE user_id=?",
        (balance, user_id)
    )
    conn.commit()


def get_top():
    cur.execute("""
        SELECT username, first_name, balance
        FROM users
        ORDER BY balance DESC
        LIMIT 10
    """)
    return cur.fetchall()


def check_cd(last_time, cooldown):
    return time.time() - last_time < cooldown


def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}ч {minutes}м"

# ---------------- BOT ----------------

app = ApplicationBuilder().token(TOKEN).build()

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    data = get_user(user.id)

    if check_cd(data[3], CD_SHORT):
        return await update.message.reply_text("⏳ Подожди 3 сек")

    update_field(user.id, "last_start", int(time.time()))

    await update.message.reply_text(
        "👋 Бот работает!\n\n"
        "/earn\n"
        "/pay\n"
        "/daily\n"
        "/balance\n"
        "/top"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    data = get_user(user.id)

    if check_cd(data[4], CD_SHORT):
        return await update.message.reply_text("⏳ Подожди 3 сек")

    update_field(user.id, "last_balance", int(time.time()))

    await update.message.reply_text(
        f"💰 Баланс: {data[2]} Бебракоинов"
    )


async def earn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    data = get_user(user.id)

    if check_cd(data[6], CD_EARN):
        remaining = CD_EARN - (time.time() - data[6])

        return await update.message.reply_text(
            f"⏳ Работать можно через {format_time(remaining)}"
        )

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

    new_balance = data[2] + coins

    update_balance(user.id, new_balance)
    update_field(user.id, "last_earn", int(time.time()))

    if coins >= 233:
        text = (
            f"😱 Ничего себе! "
            f"{user.first_name} нашёл {coins} Бебракоинов!"
        )
    else:
        text = (
            f"💰 {user.first_name} получил "
            f"{coins} Бебракоинов! 🎉"
        )

    await update.message.reply_text(text)


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    data = get_user(user.id)

    if check_cd(data[7], CD_DAILY):
        remaining = CD_DAILY - (time.time() - data[7])

        return await update.message.reply_text(
            f"⏳ Приходи через {format_time(remaining)}"
        )

    roll = random.random()

    if roll < 0.33:
        reward = 100

    elif roll < 0.66:
        reward = 150

    elif roll < 0.99:
        reward = 200

    else:
        reward = 750

    new_balance = data[2] + reward

    update_balance(user.id, new_balance)
    update_field(user.id, "last_daily", int(time.time()))

    if reward == 750:
        text = (
            f"🍀 Счастливчик! "
            f"{user.first_name} получил {reward}!"
        )
    else:
        text = (
            f"✨ {user.first_name} получил "
            f"{reward} Бебракоинов"
        )

    await update.message.reply_text(text)


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)

    data = get_user(user.id)

    if check_cd(data[5], CD_SHORT):
        return await update.message.reply_text("⏳ Подожди 3 сек")

    if not context.args:
        return await update.message.reply_text(
            "Используй:\n/pay 100 @user"
        )

    try:
        amount = int(context.args[0])
    except:
        return await update.message.reply_text(
            "❌ Неверная сумма"
        )

    if amount < 1 or amount > 1_000_000:
        return await update.message.reply_text(
            "❌ 1 - 1 000 000"
        )

    sender_balance = data[2]

    if sender_balance < amount:
        return await update.message.reply_text(
            "❌ Недостаточно средств"
        )

    receiver = None

    if update.message.reply_to_message:
        receiver = update.message.reply_to_message.from_user

    elif len(context.args) > 1:
        username = context.args[1].replace("@", "")

        cur.execute(
            "SELECT user_id FROM users WHERE username=?",
            (username,)
        )

        row = cur.fetchone()

        if row:
            receiver = type(
                "obj",
                (),
                {
                    "id": row[0],
                    "first_name": username
                }
            )()

    if not receiver:
        return await update.message.reply_text(
            "❌ Игрок не найден"
        )

    ensure_user(receiver)

    rec_data = get_user(receiver.id)

    update_balance(
        user.id,
        sender_balance - amount
    )

    update_balance(
        receiver.id,
        rec_data[2] + amount
    )

    update_field(
        user.id,
        "last_pay",
        int(time.time())
    )

    await update.message.reply_text(
        f"{user.first_name} дал "
        f"{amount} Бебракоинов "
        f"{receiver.first_name} 💸"
    )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_top()

    medals = ["🥇", "🥈", "🥉"]

    text = "🏆 Топ игроков:\n\n"

    for i, (username, name, balance) in enumerate(data):

        display = f"@{username}" if username else name

        medal = medals[i] if i < 3 else f"{i+1}."

        text += (
            f"{medal} {display} — "
            f"{balance} 💰\n"
        )

    await update.message.reply_text(text)

# ---------------- COMMAND MENU ----------------

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Старт"),
        BotCommand("earn", "Работа"),
        BotCommand("pay", "Перевод"),
        BotCommand("daily", "Дейли"),
        BotCommand("balance", "Баланс"),
        BotCommand("top", "Топ"),
    ])

# ---------------- HANDLERS ----------------

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("earn", earn))
app.add_handler(CommandHandler("pay", pay))
app.add_handler(CommandHandler("daily", daily))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("top", top))

# ---------------- START BOT ----------------

def main():
    app.post_init = set_commands

    print("🤖 Bot started")

    app.run_polling()


if __name__ == "__main__":
    main()