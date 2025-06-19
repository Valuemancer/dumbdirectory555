
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

# === LENS SCORING ===
def score_post(post):
    score = 0
    reasons = []

    title = post.title.lower()
    body = post.selftext.lower()
    text = title + " " + body

    if any(k in text for k in KEYWORDS):
        score += 15
        reasons.append("✅ keyword match")
    if any(city in text for city in CITIES):
        score += 15
        reasons.append("📍 city match")

    if "[pic" in text or "imgur.com" in text:
        score += 10
        reasons.append("📸 probable photo")

    try:
        author = post.author
        if not author or author.name.lower().startswith("throw"):
            reasons.append("🚫 throwaway")
        else:
            if author.comment_karma > 10 or author.link_karma > 10:
                score += 15
                reasons.append("🧍 karma ok")
            if "therapy" in author.name.lower():
                score += 10
                reasons.append("🧠 name = therapy user")

            if hasattr(author, 'is_employee') and not author.is_employee:
                score += 5
    except:
        reasons.append("🚫 author unavailable")

    return min(score, 100), reasons

# === ALERT ===
def send_alert(post, lens_score, reasons):
    msg = f"<b>{post.title}</b>\n"
    msg += f"{post.subreddit_name_prefixed} - u/{post.author.name}\n"
    msg += f"LENS Score: <b>{lens_score}/100</b>\n"
    msg += f"{' | '.join(reasons)}\n\n"
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

                score, reasons = score_post(post)
                if score >= 40:  # threshold for signal
                    send_alert(post, score, reasons)
                SEEN.add(post.id)
        except Exception as e:
            print(f"Error on {sub}: {e}")

if __name__ == "__main__":
    scan()
