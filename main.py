import os
import praw
import requests
import time
from dotenv import load_dotenv
import re

load_dotenv()

# === CONFIGURATION ===
SUBREDDITS = [
    "r4r", "r4rDenver", "coloradosexuals", "dirtyr4r", "r4rColorado",
    "AgeGapPersonals", "t4r", "t4m", "transr4r", "R4R30Plus", "R4R30PlusNSFW",
    "KindVoiceR4R", "ForeverAloneDating", "ForeverAlone", "DatingAdvice",
    "ForeverAloneTogether", "needafriend", "MakeNewFriendsHere"
]

CORE_KEYWORDS = ["f4m", "f4a", "f4x"]
EMOTIONAL_KEYWORDS = ["lonely", "alone", "isolated", "sad", "heartbroken", "shy", "quiet", "nervous", "new here", "newbie", "first time", "single", "looking", "introvert", "playful", "fun", "flirty", "open to", "down to", "casual", "hookup", "flirt", "adventurous", "open-minded"]
NEGATIVE_KEYWORDS = ["m4f", "m4a", "m4x", "f4f", "spam", "bot", "fake"]

RESULT_LIMIT = 50
NSFW_OK = True

MAX_QUALITY_SCORE = 100  # arbitrary max for scaling

# Adjust weighting factors as needed
KARMA_WEIGHT = 0.7
AGE_WEIGHT = 0.3

SEEN = set()

def send_alert(post, reasons):
    try:
        msg = f"<b>{post.title}</b>\n"
        msg += f"{post.subreddit_name_prefixed} - u/{post.author}\n"
        msg += " | ".join(reasons) + "\n"
        msg += f"{post.url}"
        url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
        data = {
            "chat_id": os.getenv('TELEGRAM_CHAT_ID'),
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        requests.post(url, data=data, timeout=10)
        print(f"✅ Alert sent for: {post.title} Reasons: {'; '.join(reasons)}")
    except Exception as e:
        print("Telegram error:", e)

def contains_keyword(text, keywords):
    text = text.lower()
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return True
    return False

def account_age_days(author):
    try:
        return (time.time() - author.created_utc) / 86400
    except Exception:
        return 0

def quality_score(karma, age_days):
    karma_scaled = min(karma, 500) / 500 * 100
    age_scaled = min(age_days, 365) / 365 * 100
    score = KARMA_WEIGHT * karma_scaled + AGE_WEIGHT * age_scaled
    return score

def passes_filters(post):
    title = post.title.lower()

    if contains_keyword(title, NEGATIVE_KEYWORDS):
        return False, ["🚫 contains negative keyword"]

    if not contains_keyword(title, CORE_KEYWORDS):
        return False, ["🚫 missing core keyword"]

    reasons = ["✅ core keyword matched"]

    try:
        author = post.author
        if not author:
            return False, ["🚫 no author info"]

        is_throwaway = author.name.lower().startswith("throw")
        karma = max(author.comment_karma or 0, author.link_karma or 0)
        age_days = account_age_days(author)
        score = quality_score(karma, age_days)

        if is_throwaway:
            reasons.append("⚠️ throwaway username")

        emotional_or_open = contains_keyword(title, EMOTIONAL_KEYWORDS)

        if score >= 50:
            reasons.append(f"🧍 quality score {score:.1f} good (karma {karma}, age {int(age_days)}d)")
            if emotional_or_open:
                reasons.append("✨ emotional/openness keywords present")
            return True, reasons

        if score >= 20 and emotional_or_open:
            reasons.append(f"👧 lower quality score {score:.1f} but emotional/openness keywords")
            return True, reasons

        reasons.append(f"🚫 rejected: quality score {score:.1f}, emotional/openness keywords {'present' if emotional_or_open else 'absent'}")
        return False, reasons

    except Exception as e:
        return False, [f"🚫 author info error: {e}"]

def scan():
    for sub in SUBREDDITS:
        try:
            for post in praw.Reddit().subreddit(sub).new(limit=RESULT_LIMIT):
                if post.id in SEEN:
                    continue
                if post.over_18 and not NSFW_OK:
                    continue

                passed, reasons = passes_filters(post)
                if passed:
                    send_alert(post, reasons)
                    SEEN.add(post.id)
                else:
                    print(f"Skipped post {post.id} - Reasons: {'; '.join(reasons)}")
        except Exception as e:
            print(f"Error scanning {sub}: {e}")

if __name__ == "__main__":
    print("🔁 Starting Reddit scan loop with quality scoring and expanded subreddits...")
    while True:
        try:
            scan()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60)
