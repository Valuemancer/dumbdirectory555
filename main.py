import os
import praw
import requests
import json
import time
from datetime import datetime, timedelta

# === CONFIG ===
KEYWORDS = ["f4m", "f4a", "f4t", "f4x", "attachment", "therapy", "healing", "growth", "pics", "imgur"]
CITIES = ["denver", "colorado", "boulder", "fort collins", "colorado springs"]
NSFW_OK = True
RESULT_LIMIT = 25

# === AUTH ===
REDDIT = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_SECRET"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
    user_agent="Scanneroni v2.0 with LENS"
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SUBREDDITS = [
    "r4r", "r4rDenver", "coloradosexuals", "dirtyr4r", "r4rColorado",
    "AgeGapPersonals", "t4r", "t4m", "transr4r", "R4R30Plus", "R4R30PlusNSFW",
    "KindVoiceR4R", "therapy", "attachment_theory", "traumatoolbox"
]

# === CACHE ===
SEEN = set()

# === ALERT ===
def send_alert(post):
    msg = f"<b>{post.title}</b>\n"
    msg += f"{post.subreddit_name_prefixed} - u/{post.author.name}\n"
    msg += f"{post.url}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, data=data, timeout=10)
        print(f"✅ Sent alert for: {post.title}")
    except Exception as e:
        print("Telegram error:", e)

# === RUN ===
def scan():
    global SEEN
    for sub in SUBREDDITS:
        try:
            for post in REDDIT.subreddit(sub).new(limit=RESULT_LIMIT):
                if post.id in SEEN:
                    continue
                if post.over_18 and not NSFW_OK:
                    continue

                text = (post.title + " " + post.selftext).lower()
                if any(k in text for k in KEYWORDS) or any(city in text for city in CITIES):
                    send_alert(post)
                SEEN.add(post.id)
        except Exception as e:
            print(f"Error on {sub}: {e}")

if __name__ == "__main__":
    print("🔁 Starting Reddit scan loop...")
    while True:
        try:
            scan()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60)