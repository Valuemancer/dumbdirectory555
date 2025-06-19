
def analyze_user_profile(reddit, username):
    try:
        user = reddit.redditor(username)
        comments = list(user.comments.new(limit=20))
        if not comments:
            return "🔍 No comment history", 0

        empathy_keywords = ["sorry", "thank you", "appreciate", "feel", "hope", "understand", "kind", "support"]
        empathy_score = 0
        total_length = 0
        for comment in comments:
            text = comment.body.lower()
            total_length += len(text.split())
            if any(word in text for word in empathy_keywords):
                empathy_score += 1

        avg_length = total_length / len(comments)
        intelligence_score = "🧠 Avg comment length: {:.0f} words".format(avg_length)

        if empathy_score >= 5:
            empathy_flag = "💗 Empathetic tone detected"
        elif empathy_score >= 2:
            empathy_flag = "💬 Some empathy in tone"
        else:
            empathy_flag = "😐 Low empathy detected"

        return f"{intelligence_score}\n{empathy_flag}", avg_length
    except Exception:
        return "⚠️ Could not evaluate user", 0



def build_telegram_message(post, flags, profile_score) -> str:
    message = f"📬 Post: [{post.title}](https://redd.it/{post.id})\n\n"
    message += f"👤 u/{post.author}\n"
    message += f"🌐 Subreddit: r/{post.subreddit.display_name}\n"
    message += "🧠 Flags:\n"
    for flag in flags:
        message += f" - {flag}\n"
    message += "\n" + profile_score
    message += "\n\n📌 Matched Criteria: ✅"
    return message



def build_telegram_message(post, flags) -> str:
    message = f"📬 Post: [{post.title}](https://redd.it/{post.id})\n\n"
    message += f"👤 u/{post.author}\n"
    message += f"🌐 Subreddit: r/{post.subreddit.display_name}\n"
    message += "🧠 Flags:\n"
    for flag in flags:
        message += f" - {flag}\n"
    message += "\n📌 Matched Criteria: ✅"
    return message



BANNED_SUBREDDITS = [
    "dirtyr4r", "realgirls", "gonewild", "hotwife", "kinkr4r", "nsfwr4r",
    "fetishr4r", "r4rnsfw", "sexsells", "xxxr4r", "nsfw", "bdsmr4r",
    "therapy", "traumatoolbox", "attachmenttheory", "mentalhealth", 
    "offmychest", "relationship_advice", "TrueOffMyChest"
]

def is_banned_subreddit(subreddit: str) -> bool:
    name = subreddit.lower()
    return any(banned in name for banned in BANNED_SUBREDDITS)



import os
import praw
import requests
import time
import re

NSFW_OK = False
RESULT_LIMIT = 25

SUBREDDITS = [
    "r4r", "r4rDenver", "r4rColorado", "R4R30Plus", "KindVoiceR4R"
]

BLOCKED_SUBS = {
    "dirtyr4r", "r4rnsfw", "nsfw_r4r", "gonewild", "hotwife", "sluttyconfessions",
    "realgirls", "nsfw_gif", "petitegonewild", "amateur", "cumsluts", "bdsmcommunity",
    "attachment_theory", "traumatoolbox", "therapy", "mentalhealth", "psychology",
    "depression", "cptsd", "selfimprovement", "socialskills", "askpsychology"
}

FEMALE_TAGS = ["f4m", "f4a", "f4r"]
MALE_TAG_PATTERN = re.compile(r"\bm\s*4\s*[amfr]", re.IGNORECASE)
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
    title_lower = title.lower()
    return any(ftag in title_lower for ftag in FEMALE_TAGS) and not MALE_TAG_PATTERN.search(title)

def is_clean(post):
    return not SEXUAL_KEYWORDS.search(post.title + " " + post.selftext)

def send_alert(post, score, flags):
    msg = "🟢 <b>{}</b>\n".format(post.title)
    msg += "<i>r/{}</i> | u/{}\n".format(post.subreddit.display_name, post.author.name if post.author else "unknown")
    msg += "🔗 {}\n\n".format(post.shortlink)
    msg += "📊 <b>Lens Score:</b> {}\n".format(score)
    msg += "🧠 Flags: {}\n\n".format(", ".join(flags))
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

                title = post.title
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
