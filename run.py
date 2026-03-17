import subprocess
import sys
import time
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

def start_bot():
    return subprocess.Popen([sys.executable, "-m", "app.bot"])

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN belum diset di file .env")
        sys.exit(1)
    
    bot_process = start_bot()
    time.sleep(2)

    try:
        subprocess.run([sys.executable, "-m", "app.app"])
    except KeyboardInterrupt:
        pass
    finally:
        bot_process.terminate()
        sys.exit(0)
