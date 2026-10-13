#!/usr/bin/env python3
"""INTERBID kanali: posts/ papkasidagi vaqti kelgan postlarni Telegramga joylaydi.

Ishlatish:
  python3 post.py           vaqti kelgan, hali joylanmagan postlarni yuboradi
  python3 post.py --check   barcha post fayllarini tekshiradi va jadvalni chiqaradi (hech narsa yubormaydi)

Kerakli muhit o'zgaruvchilari:
  TELEGRAM_BOT_TOKEN  bot tokeni (GitHub'da secret sifatida saqlanadi)
  CHAT_ID             kanal, standart qiymati @inter_bid
  MAX_LATE_HOURS      shuncha soatdan ko'p kechikkan post yuborilmaydi (standart 12)
"""
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(ROOT, "posts")
STATE_FILE = os.path.join(ROOT, "state", "sent.json")
CHAT_ID = os.environ.get("CHAT_ID", "@inter_bid")
MAX_LATE = timedelta(hours=int(os.environ.get("MAX_LATE_HOURS", "12")))

MAX_TEXT = 4096
MAX_POLL_QUESTION = 300
MAX_POLL_OPTION = 100


class PostError(Exception):
    pass


def parse_post(path):
    """Fayl tuzilmasi: yuqorida 'kalit: qiymat' qatorlari, keyin '---', keyin matn."""
    post_id = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8") as f:
        raw = f.read().replace("\r\n", "\n")
    head, sep, body = raw.partition("\n---\n")
    if not sep:
        raise PostError(f"{post_id}: '---' ajratuvchi qatori topilmadi")

    meta = {}
    for line in head.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, colon, value = line.partition(":")
        if not colon:
            raise PostError(f"{post_id}: noto'g'ri qator: {line!r}")
        meta[key.strip().lower()] = value.strip()

    if "at" not in meta:
        raise PostError(f"{post_id}: 'at:' (vaqt) ko'rsatilmagan")
    try:
        at = datetime.fromisoformat(meta["at"])
    except ValueError:
        raise PostError(f"{post_id}: vaqt formati noto'g'ri: {meta['at']!r} (masalan 2026-10-17T11:00:00+05:00)")
    if at.tzinfo is None:
        raise PostError(f"{post_id}: vaqtda soat mintaqasi yo'q, oxiriga +05:00 qo'shing")

    kind = meta.get("type", "message")
    body = body.strip("\n")
    post = {"id": post_id, "at": at, "type": kind}

    if kind == "message":
        if not body.strip():
            raise PostError(f"{post_id}: matn bo'sh")
        if len(body) > MAX_TEXT:
            raise PostError(f"{post_id}: matn {len(body)} belgi, Telegram chegarasi {MAX_TEXT}")
        post["text"] = body
        post["preview"] = meta.get("preview", "no").lower() in ("yes", "ha", "true")
    elif kind == "poll":
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if not lines:
            raise PostError(f"{post_id}: so'rovnoma savoli yo'q")
        question = lines[0]
        options = [l[1:].strip() for l in lines[1:] if l.startswith("-")]
        if len(question) > MAX_POLL_QUESTION:
            raise PostError(f"{post_id}: savol {len(question)} belgi, chegarasi {MAX_POLL_QUESTION}")
        if not 2 <= len(options) <= 10:
            raise PostError(f"{post_id}: variantlar soni {len(options)}, 2 dan 10 gacha bo'lishi kerak")
        for o in options:
            if len(o) > MAX_POLL_OPTION:
                raise PostError(f"{post_id}: variant juda uzun ({len(o)} belgi): {o!r}")
        post["question"] = question
        post["options"] = options
        post["anonymous"] = meta.get("anonymous", "yes").lower() in ("yes", "ha", "true")
    else:
        raise PostError(f"{post_id}: noma'lum tur {kind!r} (message yoki poll bo'lishi kerak)")
    return post


def load_posts():
    posts, errors = [], []
    for path in sorted(glob.glob(os.path.join(POSTS_DIR, "*.txt"))):
        try:
            posts.append(parse_post(path))
        except PostError as e:
            errors.append(str(e))
    posts.sort(key=lambda p: p["at"])
    return posts, errors


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def telegram(token, method, payload):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode("utf-8") or "{}")
    if not data.get("ok"):
        raise PostError(f"Telegram {method} xatosi: {data.get('description', data)}")
    return data["result"]


LINK_RE = re.compile(r"\{\{link:([\w\-]+)\}\}")


def channel_url(message_id=None):
    base = f"https://t.me/{CHAT_ID.lstrip('@')}"
    return f"{base}/{message_id}" if message_id else base


def resolve_links(text, state):
    """{{link:post-id}} o'rniga joylangan postning havolasini qo'yadi (topilmasa kanal havolasi)."""
    def repl(m):
        entry = state.get(m.group(1), {})
        return channel_url(entry.get("message_id"))
    return LINK_RE.sub(repl, text)


def send(token, post, state):
    if post["type"] == "message":
        payload = {
            "chat_id": CHAT_ID,
            "text": resolve_links(post["text"], state),
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": not post["preview"]},
        }
        return telegram(token, "sendMessage", payload)
    payload = {
        "chat_id": CHAT_ID,
        "question": post["question"],
        "options": [{"text": o} for o in post["options"]],
        "is_anonymous": post["anonymous"],
    }
    try:
        return telegram(token, "sendPoll", payload)
    except PostError:
        # Bot API'ning eski versiyasi variantlarni oddiy matn ro'yxati sifatida qabul qiladi
        payload["options"] = post["options"]
        return telegram(token, "sendPoll", payload)


def check():
    posts, errors = load_posts()
    state = load_state()
    ids = {p["id"] for p in posts} | set(state)
    for p in posts:
        for ref in LINK_RE.findall(p.get("text", "")):
            if ref not in ids:
                errors.append(f"{p['id']}: {{{{link:{ref}}}}} da ko'rsatilgan post topilmadi")
    tz = timezone(timedelta(hours=5))
    print(f"{len(posts)} ta post topildi:")
    for p in posts:
        status = "joylangan" if p["id"] in state else "kutilmoqda"
        print(f"  {p['at'].astimezone(tz):%Y-%m-%d %H:%M} (Toshkent)  {p['type']:<7}  {status:<10}  {p['id']}")
    for e in errors:
        print(f"XATO: {e}")
    return 1 if errors else 0


def run():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("XATO: TELEGRAM_BOT_TOKEN topilmadi. GitHub'da Settings > Secrets and variables > Actions bo'limiga qo'shing.")
        return 1
    try:
        me = telegram(token, "getMe", {})
        print(f"Bot ulandi: @{me.get('username')}")
    except PostError as e:
        print(f"XATO: bot tokeni ishlamayapti: {e}")
        return 1
    posts, errors = load_posts()
    for e in errors:
        print(f"XATO: {e}")
    state = load_state()
    now = datetime.now(timezone.utc)
    failed = bool(errors)
    for p in posts:
        if p["id"] in state or p["at"] > now:
            continue
        late = now - p["at"]
        if late > MAX_LATE:
            print(f"O'TKAZIB YUBORILDI: {p['id']} {late} kechikkan (chegarasi {MAX_LATE})")
            state[p["id"]] = {"skipped": True, "reason": f"{late} kechikdi", "checked_at": now.isoformat()}
            continue
        try:
            result = send(token, p, state)
        except PostError as e:
            print(f"XATO: {p['id']}: {e}")
            failed = True
            continue
        state[p["id"]] = {"message_id": result.get("message_id"), "sent_at": now.isoformat()}
        print(f"JOYLANDI: {p['id']} -> https://t.me/{CHAT_ID.lstrip('@')}/{result.get('message_id')}")
    save_state(state)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else run())
