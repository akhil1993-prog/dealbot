import asyncio
from datetime import datetime, timezone, timedelta
import html
import os
import re
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- നിങ്ങളുടെ പുതിയ ബോട്ട് ടോക്കൺ & വിവരങ്ങൾ ---
BOT_TOKEN = "8996059238:AAGW7IbrwajkVTAd9vK-niLqGYWRyQqpdio"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"
ADMIN_USER_ID = 0

FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed",
    "https://www.dealofday.in/feed/",
    "https://indiafreestuff.in/feed"
]

TRENDS_RSS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"

posted_deals = set()
registered_users = set()

IST = timezone(timedelta(hours=5, minutes=30))

# --- വെബ് സെർവർ ---
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- ട്രെൻഡിംഗ് സെർച്ചുകൾ ---
def get_trending_searches():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(TRENDS_RSS_URL, headers=headers, timeout=10)
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries[:5]:
            clean_title = re.sub(r'<[^>]+>', '', getattr(entry, 'title', '')).strip()
            if clean_title and clean_title not in items:
                items.append(clean_title)
        if items:
            return items
    except Exception:
        pass
    return ["5G മൊബൈലുകൾ", "സ്മാർട്ട് വാച്ചുകൾ", "ബ്ലൂടൂത്ത് ഇയർഫോൺ", "ഫാഷൻ ഷൂസുകൾ", "ഡ്രസ്സുകൾ"]

# --- മലയാളം മെനു ബട്ടണുകൾ ---
def get_simple_malayalam_keyboard():
    keyboard = [
        [KeyboardButton("📱 5G മൊബൈൽ ഫോണുകൾ"), KeyboardButton("🎧 ബ്ലൂടൂത്ത് ഇയർഫോൺ")],
        [KeyboardButton("⌚ സ്മാർട്ട് വാച്ചുകൾ"), KeyboardButton("👟 ചെരുപ്പ് & വസ്ത്രങ്ങൾ")],
        [KeyboardButton("💄 സൗന്ദര്യവർദ്ധക വസ്തുക്കൾ"), KeyboardButton("🔥 ഇന്നത്തെ വമ്പൻ ഓഫറുകൾ")],
        [KeyboardButton("🌟 കൂടുതൽ ആളുകൾ വാങ്ങുന്നവ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- സാധനം തിരിച്ചറിയൽ ---
def detect_category_and_query(text):
    text_lower = text.lower()
    numbers = re.findall(r'\d+', text)
    budget = f"under {numbers[0]}" if numbers else ""

    if any(w in text_lower for w in ["മൊബൈൽ", "ഫോൺ", "phone", "mobile", "5g"]):
        return "electronics", f"5G smartphone {budget}".strip(), "5G സ്മാർട്ട്‌ഫോണുകൾ"
    elif any(w in text_lower for w in ["ഇയർഫോൺ", "ഇയർബഡ്സ്", "earbuds", "earphone", "audio"]):
        return "electronics", f"wireless earbuds {budget}".strip(), "ബ്ലൂടൂത്ത് ഇയർഫോണുകൾ"
    elif any(w in text_lower for w in ["വാച്ച്", "watch", "smartwatch"]):
        return "electronics", f"smartwatch {budget}".strip(), "സ്മാർട്ട് വാച്ചുകൾ"
    elif any(w in text_lower for w in ["ചെരുപ്പ്", "ഷൂ", "വസ്ത്രങ്ങൾ", "ഷർട്ട്", "സാരി", "shoe", "fashion"]):
        return "fashion", f"fashion shoes clothing {budget}".strip(), "ഫാഷൻ & ഷൂസ്"
    elif any(w in text_lower for w in ["സൗന്ദര്യ", "ക്രീം", "lipstick", "beauty", "cream"]):
        return "beauty", f"beauty skincare {budget}".strip(), "സൗന്ദര്യവർദ്ധക വസ്തുക്കൾ"
    elif any(w in text_lower for w in ["വമ്പൻ", "ഓഫർ", "loot", "deal"]):
        return "loot", "deals of the day", "ഇന്നത്തെ മികച്ച ഓഫറുകൾ"
    else:
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        return "general", f"{clean if clean else 'top deals'} {budget}".strip(), text

# --- ചാറ്റ് ഹാൻഡ്‌ലർ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        registered_users.add(update.effective_user.id)

    user_text = update.message.text.strip()

    if user_text == "/start":
        welcome_text = (
            "🙏 *നമസ്കാരം! Prime Finder-ലേക്ക് സ്വാഗതം.*\n\n"
            "Amazon, Flipkart എന്നിവയിലെ ഏറ്റവും നല്ല സാധനങ്ങളും ഓഫറുകളും അറിയാൻ താഴെ കാണുന്ന ബട്ടണുകളിൽ ക്ലിക്ക് ചെയ്യുക 👇"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_simple_malayalam_keyboard())
        return

    if "കൂടുതൽ ആളുകൾ" in user_text or "Trending" in user_text:
        trends = get_trending_searches()
        msg = "🌟 *ഇന്ന് കൂടുതൽ ആളുകൾ തിരയുന്ന സാധനങ്ങൾ:*\n\n"
        buttons = []
        for i, item in enumerate(trends, 1):
            msg += f"{i}️⃣ *{item}*\n"
            encoded_item = urllib.parse.quote_plus(item)
            amz_url = f"https://www.amazon.in/s?k={encoded_item}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
            buttons.append([InlineKeyboardButton(f"👉 {item} കാണുക", url=amz_url)])

        msg += "\n━━━━━━━━━━━━━━━━━━━━\n🛒 *ഓഫറുകൾ കാണാൻ താഴെ ക്ലിക്ക് ചെയ്യുക:*"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        return

    cat_type, search_query, display_name = detect_category_and_query(user_text)
    encoded = urllib.parse.quote_plus(search_query)

    amazon_url = f"https://www.amazon.in/s?k={encoded}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_url = f"https://www.flipkart.com/search?q={encoded}&sort=popularity"
    myntra_url = f"https://www.myntra.com/{encoded}"

    if cat_type == "fashion":
        buttons = [
            [InlineKeyboardButton("🟠 Amazon-ൽ ഓഫർ കാണുക (4★+)", url=amazon_url)],
            [InlineKeyboardButton("🔵 Flipkart-ൽ കാണുക", url=flipkart_url)],
            [InlineKeyboardButton("🔴 Myntra-ൽ കാണുക", url=myntra_url)]
        ]
    elif cat_type == "beauty":
        buttons = [
            [InlineKeyboardButton("🟠 Amazon-ൽ കാണുക (4★+)", url=amazon_url)],
            [InlineKeyboardButton("🌸 Nykaa-ൽ കാണുക", url=f"https://www.nykaa.com/search/result/?q={encoded}")]
        ]
    elif cat_type == "loot":
        buttons = [
            [InlineKeyboardButton("🔥 ആമസോൺ വമ്പൻ ഓഫറുകൾ (Up to 70% Off)", url=f"https://www.amazon.in/deals?tag={AMAZON_TAG}")],
            [InlineKeyboardButton("⚡ ഫ്ലിപ്കാർട്ട് സൂപ്പർ ഓഫറുകൾ", url="https://www.flipkart.com/offers-list/top-offers")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🟠 ആമസോണിൽ കാണുക (4★+)", url=amazon_url)],
            [InlineKeyboardButton("🔵 ഫ്ലിപ്കാർട്ടിൽ കാണുക", url=flipkart_url)]
        ]

    reply_msg = (
        f"✅ *{display_name} കണ്ടെത്താൻ സാധിച്ചു!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ *പ്രത്യേകതകൾ:*\n"
        f"• 4★+ റേറ്റിംഗുള്ള ഉൽപ്പന്നങ്ങൾ മാത്രം\n"
        f"• 100% ഒറിജിനൽ ബ്രാൻഡുകൾ\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 *വില അറിയാൻ താഴെയുള്ള ബട്ടണിൽ അമർത്തുക:*"
    )

    await update.message.reply_text(reply_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

# --- അഡ്മിൻ ബ്രോഡ്കാസ്റ്റ് ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_USER_ID != 0 and user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ അനുമതിയില്ല.", parse_mode="Markdown")
        return

    broadcast_msg = update.message.text.replace("/broadcast", "").strip()
    if not broadcast_msg or not registered_users:
        return

    for uid in list(registered_users):
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 *അറിയിപ്പ്:*\n\n{broadcast_msg}", parse_mode="Markdown")
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text("✅ ബ്രോഡ്കാസ്റ്റ് പൂർത്തിയായി!")

# --- ഡീൽ എക്സ്ട്രാക്ഷൻ ---
def extract_deal_info(entry):
    raw_title = getattr(entry, 'title', 'Special Verified Deal')
    clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
    clean_title = html.unescape(clean_title)

    content = f"{clean_title} {getattr(entry, 'summary', '')}"

    image_url = None
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url')
    if not image_url and hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        image_url = entry.enclosures[0].get('href')
    if not image_url:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', getattr(entry, 'summary', ''))
        if img_match:
            image_url = img_match.group(1)

    prices = re.findall(r'(?:Rs\.?|INR|₹)\s?(\d+[\d,]*)', content, re.IGNORECASE)
    discount_match = re.search(r'(\d+%\s*off)', content, re.IGNORECASE)

    deal_price = f"₹{prices[0]}" if prices else "പ്രത്യേക ഓഫർ വില"
    mrp_price = f"~~₹{prices[1]}~~" if len(prices) > 1 else ""
    discount = f"({discount_match.group(1).upper()})" if discount_match else ""

    final_link, platform = None, "Amazon"
    amz = re.search(r'https?://(?:www\.)?amazon\.in/[^\s"\'>]+', content)
    fk = re.search(r'https?://(?:www\.)?flipkart\.com/[^\s"\'>]+', content)
    myn = re.search(r'https?://(?:www\.)?myntra\.com/[^\s"\'>]+', content)

    if amz:
        clean = amz.group(0).split('?')[0]
        final_link, platform = f"{clean}?tag={AMAZON_TAG}", "Amazon"
    elif fk:
        clean = fk.group(0).split('?')[0]
        final_link, platform = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Flipkart"
    elif myn:
        clean = myn.group(0).split('?')[0]
        final_link, platform = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Myntra"
    else:
        search_words = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
        short_search = " ".join(search_words.split()[:5])
        encoded_query = urllib.parse.quote_plus(short_search)
        final_link, platform = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}", "Amazon"

    return clean_title, final_link, platform, image_url, deal_price, mrp_price, discount

# --- ചാനൽ പോസ്റ്റിംഗ് ---
async def send_deal_to_telegram(bot, title, final_link, platform_name, image_url, deal_price, mrp_price, discount):
    try:
        caption = (
            f"🛍️ *വിലക്കുറവിൽ വാങ്ങാം!*\n\n"
            f"📦 *സാധനം:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *ഇന്നത്തെ ഓഫർ വില:* *{deal_price}* {mrp_price} {discount}\n"
            f"🛡️ 100% ഒറിജിനൽ ബ്രാൻഡ് വാറന്റി\n"
            f"🚚 വേഗത്തിൽ വീട്ടിലെത്തിക്കുന്നു\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        inline_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 {platform_name}-ൽ നിന്ന് ഓർഡർ ചെയ്യുക", url=final_link)]
        ])

        if image_url:
            try:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=caption, parse_mode="Markdown", reply_markup=inline_btn)
                print(f"✅ ഫോട്ടോ പോസ്റ്റ് അയച്ചു: {title[:30]}")
                return
            except Exception:
                pass

        await bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown", reply_markup=inline_btn, disable_web_page_preview=False)
        print(f"✅ ടെക്സ്റ്റ് പോസ്റ്റ് അയച്ചു: {title[:30]}")
    except Exception as e:
        print(f"⚠️ പോസ്റ്റിംഗ് എറർ: {e}")

# --- ലൈവ് ഫീഡ് ചെക്കർ ---
async def check_all_feeds(bot):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for url in FEED_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:4]:
                    title, final_link, platform, image_url, deal_price, mrp_price, discount = extract_deal_info(entry)
                    if final_link and final_link not in posted_deals:
                        await send_deal_to_telegram(bot, title, final_link, platform, image_url, deal_price, mrp_price, discount)
                        posted_deals.add(final_link)
                        await asyncio.sleep(4)
        except Exception as e:
            print(f"⚠️ ഫീഡ് എറർ ({url}): {e}")

async def channel_deals_loop(bot):
    await asyncio.sleep(2)
    while True:
        await check_all_feeds(bot)
        await asyncio.sleep(120)

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_query))
    application.add_handler(CommandHandler("start", handle_user_query))

    asyncio.create_task(channel_deals_loop(application.bot))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(main())
