import os
import pyotp
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
OTP_LENGTH = int(os.getenv("OTP_LENGTH", 6))
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 300))

from database.database import (
    init_db,
    seed_dummy_users,
    authenticate_user,
    save_otp,
    get_telegram_link,
    unlink_telegram,
)


def generate_otp(secret: str) -> str:
    totp = pyotp.TOTP(secret, interval=OTP_EXPIRY_SECONDS)
    return totp.now()


def login_flow() -> dict | None:
    print("\n-- Login --")
    username = input("Username: ").strip()
    password = input("Password: ").strip()

    if not username or not password:
        print("Error: Username dan password tidak boleh kosong.")
        return None

    user = authenticate_user(username, password)

    if user:
        print(f"Login berhasil. Selamat datang, {user['name']}.")
        return user
    else:
        print("Error: Username atau password salah.")
        return None


def generate_otp_flow(user: dict):
    print("\n-- Link Telegram --")
    link = get_telegram_link(user["id"])
    if link and link.get("telegram_id"):
        print(f"Akun sudah terhubung ke Telegram (@{link.get('telegram_username', 'N/A')}).")
        print("1. Re-link (Generate ulang OTP)")
        print("2. Unlink (Putus koneksi)")
        print("3. Batal")
        choice = input("Pilihan (1/2/3): ").strip()
        
        if choice == '2':
            unlink_telegram(user["id"])
            print("Koneksi berhasil diputus.")
            return
        elif choice != '1':
            return

    secret = user.get("otp_secret") or pyotp.random_base32()
    otp_code = generate_otp(secret)

    expires_at = datetime.now() + timedelta(seconds=OTP_EXPIRY_SECONDS)
    save_otp(user["id"], otp_code, expires_at.isoformat(), telegram_id=None)

    print("\n--- KODE OTP ---")
    print(f"Kode Anda: {otp_code}")
    print(f"Berlaku sampai: {expires_at.strftime('%H:%M:%S')}")
    print("Kirim kode ini melalui command /verify ke bot Telegram.")
    print("----------------")


def check_status_flow(user: dict):
    print("\n-- Status --")
    link = get_telegram_link(user["id"])

    if link and link.get("telegram_id"):
        print("Status: Terhubung")
        print(f"Telegram: @{link.get('telegram_username', 'N/A')}")
        print(f"Terhubung pada: {link.get('linked_at', 'N/A')}")
    else:
        print("Status: Belum terhubung")


def main():
    init_db()
    seed_dummy_users()

    current_user = None
    while current_user is None:
        current_user = login_flow()
        if current_user is None:
            retry = input("Coba lagi? (y/n): ").strip().lower()
            if retry != 'y':
                return

    while True:
        print("\nMenu:")
        print("1. Link Telegram (Generate OTP)")
        print("2. Cek Status")
        print("3. Logout")
        
        choice = input("Pilihan: ").strip()

        if choice == "1":
            generate_otp_flow(current_user)
        elif choice == "2":
            check_status_flow(current_user)
        elif choice == "3":
            print("Logout berhasil.")
            break
        else:
            print("Pilihan invalid.")


if __name__ == "__main__":
    main()
