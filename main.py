
import os
import praw
import requests
import time
import re

NSFW_OK = False
RESULT_LIMIT = 25

# High-quality subreddits only
SUBREDDITS = [
    "r4r", "r4rDenver", "r4rColorado", "R4R30Plus", "KindVoiceR4R"
]

# Subreddits to block manually (not even checked)
BLOCKED_SUBS = {
    "dirtyr4r", "r4rnsfw", "nsfw_r4r", "gonewild", "hotwife", "sluttyconfessions",
    "RealGirls", "NSFW_GIF", "PetiteGoneWild", "Amateur", "cumsluts", "bdsmcommunity"
}

FEMALE_TAGS = ["f4m", "f4a", "f4r"]
MALE_TAG_PATTERN = re.compile(r"\bm\s*4\s*[a-z]+", re.IGNORECASE)
SEXUAL_KEYWORDS = re.compile(r"(nsfw|kink|bdsm|daddy|submissive|dominant|horny|fetish|sex|onlyfans|panties|cock|pussy|nude|nudes)", re.IGNORECASE)

REDDIT = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_SECRET"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
    user_agent="scanneroni-v3"
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN = set()

def is_intelligent(post):
    return len(post.selftext.split()) > 100 or any(word in post.title.lower() for word in ["thoughtful", "philosophy", "depth"])

def is_empathetic(post):
    return any(word in post.selftext.lower() for word in ["lonely", "caring", "open heart", "gentle", "kind"])

def is_female_post(title):
    lower = title.lower()
    return any(ftag in lower for ftag in FEMALE_TAGS) and not MALE_TAG_PATTERN.search(lower)

def is_clean(post):
    return not SEXUAL_KEYWORDS.search(post.title + " " + post.selftext)

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

def scan():
    global SEEN
    for sub in SUBREDDITS:
        subreddit_name = sub.lower().replace("r/", "")
        if subreddit_name in BLOCKED_SUBS:
            continue

        try:
            for post in REDDIT.subreddit(subreddit_name).new(limit=RESULT_LIMIT):
                if post.id in SEEN:
                    continue
                if post.over_18 or post.subreddit.display_name.lower() in BLOCKED_SUBS:
                    continue

                title = post.title.lower()
                flags = []
                score = 0

                if not is_female_post(title):
                    continue

                if not is_clean(post):
                    continue

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
            print(f"Error in {sub}: {e}")

if __name__ == "__main__":
    while True:
        scan()
        time.sleep(90)
