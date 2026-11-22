import asyncio
import html
import os
import re
from collections import OrderedDict

import phonenumbers
import requests
from phonenumbers import geocoder
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

try:
    from telegram import CopyTextButton
except ImportError:
    CopyTextButton = None

# === CONFIGURATION ===
# Token ko code mein mat likho. Chalane se pehle: export BOT_TOKEN="your_new_token"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID", "-1003931834861"))
API_URL = "https://panel.lamix.org/api/v1/messages"
POLL_INTERVAL = 10   # Seconds between API checks
REQUEST_TIMEOUT = 15  # Seconds before an API call is given up
MAX_SEEN = 10000

# Emojis for services
APP_EMOJIS = {
    "whatsapp": "💬",
    "telegram": "✈️",
    "facebook": "📘",
    "instagram": "📸",
    "tiktok": "🎵",
    "google": "🌐",
    "twitter": "🐦",
}


def get_app_emoji(service_name):
    service_name = str(service_name).lower()
    for key, emoji in APP_EMOJIS.items():
        if key in service_name:
            return emoji
    return "📱"


def get_country_info(phone_number):
    phone_number = str(phone_number)
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    try:
        parsed = phonenumbers.parse(phone_number)
        country_name = geocoder.country_name_for_number(parsed, "en") or "Unknown"
        region = phonenumbers.region_code_for_number(parsed)
        if region:
            flag = chr(ord(region[0]) + 127397) + chr(ord(region[1]) + 127397)
        else:
            flag = "🏳️"
        iso = region or "UN"
        return country_name, flag, iso
    except Exception:
        return "Unknown", "🏳️", "UN"


def extract_otp(msg):
    otp_match = re.search(r"\d{3}[-\s]?\d{3,4}|\d{4,8}", str(msg))
    return otp_match.group(0) if otp_match else "Unknown"


def mask_number(num):
    num = str(num).replace("+", "")
    if len(num) <= 6:
        return num
    return num[:3] + "x" * (len(num) - 6) + num[-3:]


def make_uid(item):
    return f"{item[0]}_{item[1]}_{item[3]}"


def fetch_messages():
    """Blocking API call (runs in a thread). Returns a list of valid entries."""
    resp = requests.get(API_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError("Unexpected API response format")
    return [item for item in data if isinstance(item, (list, tuple)) and len(item) >= 4]


async def send_to_group(bot, entry):
    service = str(entry[0])
    num = entry[1]
    msg = entry[2]

    country_name, flag, iso = get_country_info(num)
    app_emoji = get_app_emoji(service)
    masked = mask_number(num)
    otp = extract_otp(msg)

    text = (
        f"{flag} <b>#{iso} {app_emoji}{html.escape(service)} {masked}</b> "
        f'<tg-emoji emoji-id="5264919878082509254">▶️</tg-emoji>'
    )

    if CopyTextButton:
        try:
            row1 = [InlineKeyboardButton(
                text=f"{otp}",
                copy_text=CopyTextButton(text=otp),
                icon_custom_emoji_id="6176966310920983412",
            )]
        except Exception:
            row1 = [InlineKeyboardButton(text=f"🔑 {otp}", callback_data="noop")]
    else:
        row1 = [InlineKeyboardButton(text=f"🔑 {otp}", callback_data="noop")]

    row2 = [
        InlineKeyboardButton(text="Methods", url="https://youtube.com/@xclusor",
                             icon_custom_emoji_id="5807797645443340724"),
        InlineKeyboardButton(text="Channel", url="https://whatsapp.com/channel/0029VbC0kzIEFeXq9XLgHZ3y",
                             icon_custom_emoji_id="5429571366384842791"),
    ]
    row3 = [InlineKeyboardButton(text="OTP Panel", url="https://t.me/XclusoRPanelBot",
                                 icon_custom_emoji_id="5372917041193828849")]

    markup = InlineKeyboardMarkup([row1, row2, row3])

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
            disable_web_page_preview=True,
        )
        print(f"✅ Sent OTP for {num} - {service}", flush=True)
    except Exception as e:
        print(f"❌ Failed to send to group: {e}", flush=True)


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable set nahi hai. Pehle: export BOT_TOKEN=\"...\"")

    bot = Bot(token=BOT_TOKEN)
    seen = OrderedDict()  # insertion-ordered, so trimming removes the oldest

    print("🚀 Starting Forwarder Bot...", flush=True)

    # Initial fetch to prevent sending old OTPs
    try:
        items = await asyncio.to_thread(fetch_messages)
        for item in items:
            seen[make_uid(item)] = True
        print(f"📦 Initialized with {len(seen)} existing OTPs.", flush=True)
    except Exception as e:
        print(f"⚠️ Initial API fetch failed: {e}", flush=True)

    while True:
        try:
            items = await asyncio.to_thread(fetch_messages)
            for item in reversed(items):
                uid = make_uid(item)
                if uid not in seen:
                    seen[uid] = True
                    await send_to_group(bot, item)
                    await asyncio.sleep(0.5)

            while len(seen) > MAX_SEEN:
                seen.popitem(last=False)  # drop oldest

        except Exception as e:
            print(f"⚠️ Error fetching API: {e}", flush=True)

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
