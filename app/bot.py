import asyncio
import os
import json
import random
import string
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.error import NetworkError, Forbidden, Conflict, TimedOut
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Silence verbose library logs
logging.basicConfig(level=logging.ERROR)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("telegram.ext.Updater").setLevel(logging.CRITICAL)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OTP_LENGTH = int(os.getenv("OTP_LENGTH", 6))
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 300))

from database.database import (
    init_db,
    verify_otp,
    link_telegram,
    get_user_by_id,
    get_user_by_telegram_id,
    get_telegram_link,
    get_user_by_username,
    save_otp,
)

WAIT_USER, WAIT_OTP = range(2)

def _generate_otp(user: dict):
    otp_code = ''.join(random.choices(string.digits, k=OTP_LENGTH))
    expires_at = datetime.now() + timedelta(seconds=OTP_EXPIRY_SECONDS)
    save_otp(user["id"], otp_code, expires_at.isoformat())
    
    output = {
        "username": user["username"],
        "otp": otp_code,
        "expired_at": expires_at.isoformat()
    }
    print(f"OTP Generated {json.dumps(output)}")
    return otp_code

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)

    if user:
        await update.message.reply_text(
            f"Halo, {user['name']}!\n\n"
            f"Telegram terhubung dengan username: {user['username']}\n\n"
            f"/status - Lihat detail\n"
            f"/unlink - Putus koneksi"
        )
    else:
        await update.message.reply_text(
            "TelegramConnect\n\n"
            "Gunakan command berikut untuk terhubung:\n"
            "/login - Memulai proses login dan binding"
        )

# -- FLOW /login --
async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    existing_user = get_user_by_telegram_id(telegram_id)
    if existing_user:
        await update.message.reply_text(f"Telegram sudah terhubung dengan akun: {existing_user['username']}")
        return ConversationHandler.END

    await update.message.reply_text("Silakan masukkan username Anda:")
    return WAIT_USER

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    user = get_user_by_username(username)
    
    if not user:
        await update.message.reply_text(
            "Akun tidak ditemukan. Silakan masukkan username yang benar, atau ketik /cancel untuk membatalkan."
        )
        return WAIT_USER
        
    context.user_data['login_user'] = user
    _generate_otp(user)
    
    await update.message.reply_text(
        "OTP telah digenerate di console server (CMD).\n"
        "Silakan kirimkan kode OTP Anda ke sini.\n\n"
        "Ketik /resendotp jika ingin generate ulang, atau /cancel untuk membatalkan."
    )
    return WAIT_OTP

async def handle_otp_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    otp_code = update.message.text.strip()
    user = context.user_data.get('login_user')
    
    verified_user_id = verify_otp(otp_code)
    
    if verified_user_id and verified_user_id == user["id"]:
        telegram_id = str(update.effective_user.id)
        telegram_username = update.effective_user.username
        
        success = link_telegram(verified_user_id, telegram_id, telegram_username)
        if success:
            await update.message.reply_text(
                f"Berhasil terhubung!\n\n"
                f"Username: {user['username']}\n"
                f"Nama: {user['name']}"
            )
        else:
            await update.message.reply_text("Gagal menghubungkan akun.")
        
        context.user_data.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text("OTP tidak valid atau expired. Silakan kirimkan OTP yang benar, /resendotp, atau /cancel.")
        return WAIT_OTP

async def resend_otp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data.get('login_user')
    if not user:
        await update.message.reply_text("Tidak ada sesi login yang aktif.")
        return ConversationHandler.END
        
    _generate_otp(user)
    
    await update.message.reply_text("OTP baru telah digenerate di console server. Silakan kirimkan OTP baru tersebut ke sini.")
    return WAIT_OTP
    
async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Login dibatalkan.")
    return ConversationHandler.END

# -----------------

async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # logic lama /verify manual
    telegram_id = str(update.effective_user.id)
    telegram_username = update.effective_user.username

    existing_user = get_user_by_telegram_id(telegram_id)
    if existing_user:
        await update.message.reply_text(
            f"Telegram sudah terhubung dengan akun: {existing_user['username']}\n"
            f"Gunakan /unlink jika ingin beralih akun."
        )
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Format: /verify <kode_otp>")
        return

    otp_code = context.args[0]
    user_id = verify_otp(otp_code)

    if user_id:
        success = link_telegram(user_id, telegram_id, telegram_username)

        if success:
            user = get_user_by_id(user_id)
            await update.message.reply_text(
                f"Berhasil terhubung!\n\n"
                f"Username: {user['username']}\n"
                f"Nama: {user['name']}"
            )
        else:
            await update.message.reply_text("Gagal menghubungkan akun.")
    else:
        await update.message.reply_text("OTP tidak valid atau expired.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)

    if user:
        link = get_telegram_link(user["id"])
        await update.message.reply_text(
            f"Status: Terhubung\n"
            f"Username: {user['username']}\n"
            f"Nama: {user['name']}\n"
            f"Terhubung pada: {link['linked_at']}"
        )
    else:
        await update.message.reply_text("Telegram belum terhubung dengan akun.")

async def unlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)

    if user:
        from database.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM telegram_links WHERE user_id = ?", (user["id"],))
        conn.commit()
        conn.close()

        await update.message.reply_text("Koneksi berhasil diputus.")
    else:
        await update.message.reply_text("Tidak ada akun yang terhubung.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Command yang tersedia:\n"
        "/start - Menu utama\n"
        "/login - Memulai proses login\n"
        "/verify - Verifikasi OTP (manual)\n"
        "/status - Cek status\n"
        "/unlink - Putus koneksi"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    error = context.error
    
    if isinstance(error, NetworkError):
        print(f"[Network Error] Koneksi bermasalah: {error}")
    elif isinstance(error, Conflict):
        print(f"[Conflict Error] Bot instance lain sedang berjalan: {error}")
    else:
        print(f"[Bot Error] Terjadi kesalahan: {error}")
        # import traceback
        # print("".join(traceback.format_exception(None, error, error.__traceback__)))

def run_bot():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN belum diset di file .env")
        return

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    login_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_command)],
        states={
            WAIT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username)],
            WAIT_OTP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_otp_login),
                CommandHandler("resendotp", resend_otp_command)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_login)]
    )
    app.add_handler(login_handler)
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("verify", verify_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("unlink", unlink_command))
    app.add_handler(CommandHandler("help", help_command))

    # Error handler
    app.add_error_handler(error_handler)

    print("Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
