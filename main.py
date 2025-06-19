
import os
import praw
import requests
import time
import re

# === CONFIG ===
NSFW_OK = False
RESULT_LIMIT = 25

# Clean, connection-focused subreddits
SUBREDDITS = [
    "r4r", "r4rDenver", "r4rColorado", "R4R30Plus", "KindVoiceR4R", "R4R30PlusNSFW"
]

LOW_QUALITY_SUBS = {"attachmenttheory", "traumatoolbox", "cptsd", "healingcomplextrauma"}
FEMALE_TAGS = ["f4m", "f4a", "f4r"]
MALE_TAG_PATTERN = re.compile(r"(\bm4[a-z]*\b|\bm 4 [a-z]+|\bm-4-[a-z]+)", re.IGNORECASE)
SEXUAL_KEYWORDS = re.compile(r"(nsfw|kink|bdsm|daddy|submissive|dominant|horny|fetish|sex|onlyfans|panties|cock|pussy|nude|nudes)", re.IGNORECASE)

# === AUTH ===
REDDIT = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_SECRET"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
    user_agent="scanneroni-v3"
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === CACHE ===
SEEN = set()

# === UTILITIES ===
def is_intelligent(post):
    return len(post.selftext.split()) > 100 or any(word in post.title.lower() for word in ["thoughtful", "philosophy", "depth"])

def is_empathetic(post):
    return any(word in post.selftext.lower() for word in ["lonely", "caring", "open heart", "gentle", "kind"])

def is_female_post(title):
    lower = title.lower()
    return any(ftag in lower for ftag in FEMALE_TAGS) and not MALE_TAG_PATTERN.search(lower)

def is_clean(post):
    return not SEXUAL_KEYWORDS.search(post.title + " " + post.selftext)

# === ALERT SENDER ===
def send_alert(post, score, flags):
    msg = f"🟢 <b>{post.title}</b>
"
    msg += f"<i>r/{post.subreddit.display_name}</i> | u/{post.author.name if post.author else 'unknown'}
"
    msg += f"🔗 {post.shortlink}

"

    msg += "📊 <b>Lens Score:</b> " + str(score) + "\n"
    msg += "🧠 Flags: " + ", ".join(flags) + "\n\n"
    msg += (post.selftext[:700] + "...") if post.selftext else "[No content]"

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

# === SCAN ===
def scan():
    global SEEN
    for sub in SUBREDDITS:
        try:
            subreddit_name = sub.lower().replace("r/", "")
            if subreddit_name in LOW_QUALITY_SUBS:
                continue

            for post in REDDIT.subreddit(subreddit_name).new(limit=RESULT_LIMIT):
                if post.id in SEEN or post.over_18 and not NSFW_OK:
                    continue

                title = post.title.lower()
                flags = []
                score = 0

                if not is_female_post(title):
                    continue  # hard reject male-coded

                if not is_clean(post):
                    continue  # reject sexual/kinky/NSFW content

                flags.append("F4*")
                score += 30

                if is_intelligent(post):
                    score += 20
                    flags.append("Smart")
                if is_empathetic(post):
                    score += 15
                    flags.append("Empath")

                if score >= 40:
                    send_alert(post, score, flags)

                SEEN.add(post.id)
        except Exception as e:
            print(f"Error on subreddit {sub}: {e}")

# === ENTRY ===
if __name__ == "__main__":
    while True:
        scan()
        time.sleep(90)
