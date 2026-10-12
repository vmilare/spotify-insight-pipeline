"""Deterministic (code-only) fields: evidence quote, entities, language flag. No model calls."""
import re

QUOTE_TERMS = {
    "access": ["login", "log in", "logged out", "sign in", "password", "account", "facebook", "google"],
    "usability": ["ads", "ad ", "advert", "shuffle", "queue", "playlist", "navigation", "layout", "button",
                  "interface", "design", "home screen", "skip", "update"],
    "playback": ["crash", "stop", "lag", "freez", "play", "buffer", "connection", "audio", "sound",
                 "battery", "bluetooth", "loading"],
    "downloads": ["download", "offline", "saved"],
    "catalog": ["lyrics", "search", "recommend", "podcast", "artist", "song", "album", "not available"],
    "billing": ["premium", "price", "pay", "charge", "subscription", "money", "trial", "refund", "free version"],
    "support": ["support", "customer service", "contact", "help"],
    "other": [],
}

ENTITY_TERMS = [
    "smart shuffle", "shuffle", "ads", "advert", "playlist", "queue", "lyrics", "podcast", "audiobook",
    "download", "offline", "premium", "family plan", "duo", "student plan", "subscription", "free trial",
    "price", "login", "password", "account", "search", "recommendations", "dj", "radio", "skips", "skip",
    "repeat", "bluetooth", "android auto", "widget", "notification", "battery", "storage", "audio quality",
    "volume", "equalizer", "sleep timer", "home screen", "library", "liked songs", "refund", "customer service",
    "support", "facebook", "chromecast", "spotify connect", "video", "update", "wear os", "car",
]
ENTITY_PATTERNS = [(t, re.compile(r"(?<![a-z])" + re.escape(t) + r"s?(?![a-z])", re.I)) for t in ENTITY_TERMS]

EN_WORDS = set("the a an and or but is are was were be been i you it this that to of in on for with my me not "
               "no can can't cant dont don't do does app very so too please when why what just".split())
SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")


def evidence_quote(text, topic, whole_max):
    """Exact substring of the original text. Short reviews: the whole text. Long reviews: the sentence
    with the most terms for the predicted topic (earliest on ties), else the first sentence."""
    if len(text) <= whole_max:
        return text
    best, best_score = None, -1
    for m in SENTENCE.finditer(text):
        span = m.group(0)
        lead = len(span) - len(span.lstrip())
        trail = len(span) - len(span.rstrip())
        start, end = m.start() + lead, m.end() - trail
        if end - start < 3:
            continue
        low = text[start:end].lower()
        score = sum(low.count(t) for t in QUOTE_TERMS.get(topic, []))
        if score > best_score:
            best, best_score = (start, end), score
    if not best:
        return text
    start, end = best
    return text[start:min(end, start + 400)]


def entities(text):
    found = [t for t, p in ENTITY_PATTERNS if p.search(text)]
    # Drop a term contained in a longer matched term (e.g. "shuffle" when "smart shuffle" matched).
    return [t for t in found if not any(t != o and t in o for o in found)]


def likely_non_english(text):
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 3 and sum(ord(c) > 0x024F for c in letters) / len(letters) > 0.5:
        return True
    words = re.findall(r"[a-z']+", text.lower())
    return len(words) >= 4 and not (set(words) & EN_WORDS)
