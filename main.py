import os
import praw
import requests
import time
import re
import json
from dotenv import load_dotenv
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

load_dotenv()

# === CONFIGURATION ===
SUBREDDITS = [
    "r4r", "r4rDenver", "coloradosexuals", "dirtyr4r", "r4rColorado",
    "AgeGapPersonals", "t4r", "t4m", "transr4r", "R4R30Plus", "R4R30PlusNSFW",
    "KindVoiceR4R", "ForeverAloneDating", "ForeverAlone", "DatingAdvice",
    "ForeverAloneTogether", "needafriend", "MakeNewFriendsHere"
]

# Keywords indicating women seeking men (core)
CORE_KEYWORDS = ["f4m", "f4a", "f4x"]

# Relationship types to exclude (hard filter)
EXCLUDE_RELATIONSHIP_KEYWORDS = [
    "m4m", "m4f", "m4a", "m4x",
    "f4f", "spam", "bot", "fake"
]

# Emotional, playful, openness keywords (boosting factors)
EMOTIONAL_KEYWORDS = [
    "lonely", "alone", "isolated", "sad", "heartbroken", "shy", "quiet", "nervous",
    "new here", "newbie", "first time", "single", "looking", "introvert",
    "playful", "fun", "flirty", "open to", "down to", "casual", "hookup", "flirt",
    "adventurous", "open-minded"
]

RESULT_LIMIT = 50
NSFW_OK = True

# Weighting constants for quality score
KARMA_WEIGHT = 0.7
AGE_WEIGHT = 0.3

# Thresholds
QUALITY_SCORE_HIGH = 50
QUALITY_SCORE_LOW = 20
MIN_ACCOUNT_AGE_DAYS = 7

# Caching user analysis results to reduce API calls
user_analysis_cache = {}

# Initialize sentiment analyzer once
vader_analyzer = SentimentIntensityAnalyzer()

# Initialize Reddit API
REDDIT = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_SECRET"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
    user_agent=os.getenv("REDDIT_USER_AGENT", "scanneroni-v3")
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN = set()

# Helper functions
def send_telegram_alert(post, reasons, lens_scores):
    try:
        msg = f"<b>{post.title}</b>\n"
        msg += f"{post.subreddit_name_prefixed} - u/{post.author}\n"
        msg += " | ".join(reasons) + "\n"
        msg += f"Lens Scores:\n"
        msg += json.dumps(lens_scores, indent=2) + "\n"
        msg += f"{post.url}"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        requests.post(url, data=data, timeout=10)
        print(f"✅ Alert sent for: {post.title}")
    except Exception as e:
        print(f"Telegram error: {e}")

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

def analyze_texts(texts):
    combined_text = " ".join(texts)
    blob = TextBlob(combined_text)
    words = blob.words
    unique_words = set(words)
    lexical_diversity = len(unique_words) / len(words) if words else 0
    avg_sentence_len = sum(len(sentence.words) for sentence in blob.sentences) / len(blob.sentences) if blob.sentences else 0
    polarity = blob.sentiment.polarity
    vader_scores = vader_analyzer.polarity_scores(combined_text)
    positive_score = vader_scores.get("pos", 0)
    negative_score = vader_scores.get("neg", 0)
    compound_score = vader_scores.get("compound", 0)
    toxic_words = ["hate", "stupid", "idiot", "dumb", "kill", "bitch", "shit", "fuck"]
    toxicity_count = sum(combined_text.lower().count(word) for word in toxic_words)
    return {
        "lexical_diversity": round(lexical_diversity, 3),
        "avg_sentence_length": round(avg_sentence_len, 2),
        "textblob_polarity": round(polarity, 3),
        "vader_positive": round(positive_score, 3),
        "vader_negative": round(negative_score, 3),
        "vader_compound": round(compound_score, 3),
        "toxicity_count": toxicity_count,
        "total_text_words": len(words)
    }

def fetch_user_history_analysis(author_name):
    if author_name in user_analysis_cache:
        return user_analysis_cache[author_name]

    try:
        user = REDDIT.redditor(author_name)
        posts = list(user.submissions.new(limit=50))
        comments = list(user.comments.new(limit=50))
        texts = [post.title + " " + (post.selftext or "") for post in posts]
        texts += [comment.body for comment in comments]
        scores = analyze_texts(texts)
        karma = max(user.comment_karma or 0, user.link_karma or 0)
        age_days = account_age_days(user)
        scores["karma"] = karma
        scores["account_age_days"] = round(age_days)
        user_analysis_cache[author_name] = scores
        return scores
    except Exception as e:
        print(f"Error fetching user history for {author_name}: {e}")
        return {}

def passes_filters(post):
    title = post.title.lower()

    if contains_keyword(title, EXCLUDE_RELATIONSHIP_KEYWORDS):
        return False, ["🚫 excluded relationship type keyword"]

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

        if score >= QUALITY_SCORE_HIGH:
            reasons.append(f"🧍 quality score {score:.1f} good (karma {karma}, age {int(age_days)}d)")
            if emotional_or_open:
                reasons.append("✨ emotional/openness keywords present")
            return True, reasons

        if score >= QUALITY_SCORE_LOW and emotional_or_open:
            reasons.append(f"👧 lower quality score {score:.1f} but emotional/openness keywords")
            return True, reasons

        reasons.append(f"🚫 rejected: quality score {score:.1f}, emotional/openness keywords {'present' if emotional_or_open else 'absent'}")
        return False, reasons

    except Exception as e:
        return False, [f"🚫 author info error: {e}"]

def scan():
    for sub in SUBREDDITS:
        try:
            for post in REDDIT.subreddit(sub).new(limit=RESULT_LIMIT):
                if post.id in SEEN:
                    continue
                if post.over_18 and not NSFW_OK:
                    continue

                passed, reasons = passes_filters(post)
                if passed:
                    lens_scores = fetch_user_history_analysis(str(post.author))
                    send_telegram_alert(post, reasons, lens_scores)
                    SEEN.add(post.id)
                else:
                    print(f"Skipped post {post.id} - Reasons: {'; '.join(reasons)}")
        except Exception as e:
            print(f"Error scanning {sub}: {e}")

if __name__ == "__main__":
    print("🔁 Starting advanced Reddit scan loop with user history analysis...")
    while True:
        try:
            scan()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60)
