import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
from database.database import (
    init_db,
    verify_otp,
    link_telegram,
    get_user_by_id,
    get_user_by_telegram_id,
    get_telegram_link,
)


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
            "Cara menghubungkan akun:\n"
            "1. Login di aplikasi\n"
            "2. Generate OTP\n"
            "3. Kirim OTP: /verify <kode_otp>\n"
            "   Contoh: /verify 123456"
        )


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        "/verify - Verifikasi OTP\n"
        "/status - Cek status\n"
        "/unlink - Putus koneksi"
    )


def run_bot():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN belum diset di file .env")
        return

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("verify", verify_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("unlink", unlink_command))
    app.add_handler(CommandHandler("help", help_command))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
