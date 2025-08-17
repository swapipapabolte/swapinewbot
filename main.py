import sqlite3
import requests
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = "7554237948:AAGgiGNIvqFagBkeY15I8GkqgwWUWXTpMIY"
API_KEY = "JEm6wdy7CvsJBNjLoL9JGhjK"
ADMIN_IDS = "7810784093"  # Apna Telegram user ID dalna

# --- Database Setup ---
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cur.execute("CREATE TABLE IF NOT EXISTS channels (channel TEXT PRIMARY KEY)")
conn.commit()

# --- Helpers ---
async def check_subscription(user_id, app):
    cur.execute("SELECT channel FROM channels")
    channels = [row[0] for row in cur.fetchall()]
    for ch in channels:
        try:
            member = await app.bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

def add_user(user_id):
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

# --- Commands ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    if not await check_subscription(user.id, ctx):
        cur.execute("SELECT channel FROM channels")
        channels = [row[0] for row in cur.fetchall()]
        buttons = [[InlineKeyboardButton(f"📢 Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in channels]
        buttons.append([InlineKeyboardButton("🔄 Re-Check", callback_data="recheck")])
        await update.message.reply_text(
            "✨ *Welcome to Premium Background Remover Bot* ✨\n\n"
            "⚠️ Please join all our partner channels first:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    await update.message.reply_text(
        f"✅ Welcome, *{user.first_name}*!\n\n"
        "Send me a photo and I’ll remove its background instantly. 🚀",
        parse_mode="Markdown"
    )

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "recheck":
        if await check_subscription(query.from_user.id, ctx):
            await query.edit_message_text("🎉 Thank you! Now send me a photo ✨")
        else:
            await query.answer("⚠️ Please join all required channels.", show_alert=True)

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    if not await check_subscription(user.id, ctx):
        await update.message.reply_text("⚠️ Please join all required channels first.")
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    await file.download_to_drive("input.jpg")

    with open("input.jpg", "rb") as f:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={'image_file': f},
            data={'size': 'auto'},
            headers={'X-Api-Key': API_KEY}
        )

    if response.status_code == requests.codes.ok:
        with open("no-bg.png", "wb") as out:
            out.write(response.content)
        await update.message.reply_photo(open("no-bg.png", "rb"),
            caption="✨ Here’s your result 🚀")
        os.remove("no-bg.png")
    else:
        await update.message.reply_text("❌ Error: " + response.text)

# --- Admin Commands ---
async def add_channel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /addchannel @username")
        return
    ch = ctx.args[0]
    cur.execute("INSERT OR IGNORE INTO channels (channel) VALUES (?)", (ch,))
    conn.commit()
    await update.message.reply_text(f"✅ Channel {ch} added.")

async def remove_channel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /removechannel @username")
        return
    ch = ctx.args[0]
    cur.execute("DELETE FROM channels WHERE channel=?", (ch,))
    conn.commit()
    await update.message.reply_text(f"❌ Channel {ch} removed.")

async def list_channels(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT channel FROM channels")
    channels = [row[0] for row in cur.fetchall()]
    msg = "📢 *Current Force-Join Channels:*\n\n" + "\n".join(channels) if channels else "No channels set."
    await update.message.reply_text(msg, parse_mode="Markdown")

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    await update.message.reply_text(f"📊 *Bot Statistics:*\n\n👥 Total Users: {total_users}", parse_mode="Markdown")

async def broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    msg = " ".join(ctx.args)
    cur.execute("SELECT user_id FROM users")
    users = [row[0] for row in cur.fetchall()]
    sent, failed = 0, 0
    for uid in users:
        try:
            await ctx.bot.send_message(uid, f"📢 *Broadcast:*\n\n{msg}", parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users, ❌ failed: {failed}")

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CommandHandler("addchannel", add_channel))
    app.add_handler(CommandHandler("removechannel", remove_channel))
    app.add_handler(CommandHandler("listchannels", list_channels))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.run_polling()

if __name__ == "__main__":
    main()
