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

# --- പ്രധാന ക്രമീകരണങ്ങൾ ---
BOT_TOKEN = "8996059238:AAGW7IbrwajkVTAd9vK-niLqGYWRyQqpdio"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"
ADMIN_USER_ID = 0

FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed",
    "https://indiafreestuff.in/feed"
]

posted_deals = set()
registered_users = set()

IST = timezone(timedelta(hours=5, minutes=30))

# --- ക്വാളിറ്റി ഫിൽട്ടർ ---
TRUSTED_KEYWORDS = [
    "oil", "sugar", "tea", "soap", "surf", "detergent", "shampoo", "toothpaste",
    "rice", "ghee", "fortune", "tata", "dettol", "vim", "ariel", "colgate",
    "cadbury", "nestle", "horlicks", "samsung", "boat", "realme", "redmi", "oneplus",
    "grocery", "combos", "shoes", "fashion", "smartwatch", "earbuds"
]

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- മെനു കീബോർഡ് ---
def get_daily_essential_keyboard():
    keyboard = [
        [KeyboardButton("🛒 നിത്യോപയോഗ സാധനങ്ങൾ (പലചരക്ക്)"), KeyboardButton("🧼 ക്ലീനിംഗ് & സോപ്പുകൾ")],
        [KeyboardButton("☕ ചായപ്പൊടി & പലഹാരങ്ങൾ"), KeyboardButton("🧴 പേഴ്സണൽ കെയർ & ഷാംപൂ")],
        [KeyboardButton("📱 മൊബൈൽ & ഇലക്ട്രോണിക്സ്"), KeyboardButton("🔥 ഇന്നത്തെ വമ്പൻ പ്രൈസ് ഡ്രോപ്പുകൾ")],
        [KeyboardButton("📉 പ്രൈസ് ട്രാക്കർ (വില ഹിസ്റ്ററി പരിശോധിക്കാൻ)")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- ആമസോൺ ലിങ്കിൽ നിന്ന് ASIN തിരിച്ചറിയൽ ---
def extract_asin(url):
    pattern = r'(?:/dp/|/gp/product/|/d/|/ASIN/|/product/)([A-Z0-9]{10})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    short_pattern = r'amzn\.to/([a-zA-Z0-9]+)'
    if re.search(short_pattern, url):
        return "SHORT_LINK"
    return None

# --- സാധനങ്ങൾ തിരിച്ചറിയൽ ---
def detect_category_and_query(text):
    text_lower = text.lower()

    if any(w in text_lower for w in ["പലചരക്ക്", "വെളിച്ചെണ്ണ", "പഞ്ചസാര", "അരി", "ഓയിൽ", "grocery", "oil", "rice", "sugar"]):
        return "grocery", "grocery daily essentials cooking oil sugar tea", "നിത്യോപയോഗ പലചരക്ക് സാധനങ്ങൾ"
    elif any(w in text_lower for w in ["ക്ലീനിംഗ്", "സോപ്പ്", "വാഷിംഗ്", "soap", "surf", "detergent", "vim", "ariel"]):
        return "cleaning", "washing powder detergent soap liquid vim surf excel", "ക്ലീനിംഗ് & സോപ്പുകൾ"
    elif any(w in text_lower for w in ["ചായ", "കാപ്പി", "ബിസ്ക്കറ്റ്", "tea", "coffee", "biscuit", "snacks"]):
        return "food", "tea powder coffee biscuits snacks cadbury", "ചായപ്പൊടി & ഭക്ഷ്യോൽപ്പന്നങ്ങൾ"
    elif any(w in text_lower for w in ["ഷാംപൂ", "പേസ്റ്റ്", "shampoo", "toothpaste", "care", "dettol"]):
        return "personal_care", "shampoo toothpaste body wash dettol soap", "പേഴ്സണൽ കെയർ ഉൽപ്പന്നങ്ങൾ"
    elif any(w in text_lower for w in ["മൊബൈൽ", "ഫോൺ", "phone", "mobile", "5g", "ഇലക്ട്രോണിക്സ്"]):
        return "electronics", "5g smartphone electronics", "സ്മാർട്ട്ഫോണുകൾ & ഇലക്ട്രോണിക്സ്"
    elif any(w in text_lower for w in ["ഡ്രോപ്പ്", "പ്രൈസ്", "വമ്പൻ", "loot", "deal"]):
        return "price_drop", "amazon deals 50% to 80% discount", "ഇന്നത്തെ വലിയ പ്രൈസ് ഡ്രോപ്പുകൾ"
    else:
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        return "general", f"{clean} deals".strip(), text

# --- ചാറ്റ് ഹാൻഡ്‌ലർ & പ്രൈസ് ട്രാക്കർ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        registered_users.add(update.effective_user.id)

    user_text = update.message.text.strip()

    if user_text == "/start":
        welcome_text = (
            "🙏 *നമസ്കാരം! Prime Finder സേവിംഗ്സ് & പ്രൈസ് ട്രാക്കറിലേക്ക് സ്വാഗതം.*\n\n"
            "• നിത്യോപയോഗ സാധനങ്ങൾ വിലക്കുറവിൽ കണ്ടെത്താൻ താഴെയുള്ള മെനു ഉപയോഗിക്കുക.\n"
            "• ഏതെങ്കിലും ഒരു സാധനത്തിന്റെ കഴിഞ്ഞ മാസങ്ങളിലെ ഏറ്റവും കുറഞ്ഞ വില അറിയാൻ **ആമസോൺ ലിങ്ക് ഇവിടെ അയക്കുക!**"
        )
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_daily_essential_keyboard()
        )
        return

    if "പ്രൈസ് ട്രാക്കർ" in user_text:
        help_msg = (
            "📉 *ആമസോൺ പ്രൈസ് ട്രാക്കർ ഉപയോഗിക്കേണ്ട വിധം:*\n\n"
            "1. ആമസോണിൽ നിങ്ങൾ വാങ്ങാൻ ഉദ്ദേശിക്കുന്ന സാധനത്തിന്റെ **ലിങ്ക് (Share Link)** കോപ്പി ചെയ്യുക.\n"
            "2. ആ ലിങ്ക് ഈ ചാറ്റിലേക്ക് പേസ്റ്റ് ചെയ്ത് അയക്കുക.\n"
            "3. ബോട്ട് ഉടൻ തന്നെ ആ സാധനത്തിന്റെ കഴിഞ്ഞ മാസങ്ങളിലെ ഏറ്റവും കുറഞ്ഞ വില പരിശോധിക്കാനുള്ള വിവരങ്ങൾ നൽകും!"
        )
        await update.message.reply_text(help_msg, parse_mode="Markdown")
        return

    if "amazon.in" in user_text or "amzn.to" in user_text:
        asin = extract_asin(user_text)
        clean_url = user_text.split('?')[0] if '?' in user_text else user_text
        buy_url = f"{clean_url}?tag={AMAZON_TAG}" if "amazon.in" in clean_url else clean_url

        price_history_url = f"https://pricehistoryapp.com/search?q={urllib.parse.quote_plus(user_text)}"
        if asin and asin != "SHORT_LINK":
            price_history_url = f"https://pricehistoryapp.com/product/{asin}"

        tracker_buttons = [
            [InlineKeyboardButton("📊 മുൻകാല വില പരിശോധിക്കുക (Price History)", url=price_history_url)],
            [InlineKeyboardButton("🛒 Amazon-ൽ മികച്ച ഓഫറിൽ വാങ്ങുക", url=buy_url)]
        ]

        tracker_msg = (
            "🔍 *ആമസോൺ ഉൽപ്പന്നം വിജയകരമായി ട്രാക്ക് ചെയ്തു!*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *സ്മാർട്ട് ഷോപ്പിംഗ് ടിപ്പ്:*\n"
            "ഇന്നത്തെ ഓഫർ വില യഥാർത്ഥത്തിൽ കുറവാണോ എന്ന് ഉറപ്പാക്കാൻ താഴെയുള്ള ബട്ടണിൽ ക്ലിക്ക് ചെയ്ത് **Price History Graph** പരിശോധിക്കുക.\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(
            tracker_msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(tracker_buttons)
        )
        return

    cat_type, search_query, display_name = detect_category_and_query(user_text)
    encoded = urllib.parse.quote_plus(search_query)

    amazon_grocery_url = f"https://www.amazon.in/s?k={encoded}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_grocery_url = f"https://www.flipkart.com/search?q={encoded}&sort=popularity"
    amazon_price_drops = f"https://www.amazon.in/deals?tag={AMAZON_TAG}&pct-off=40-"

    buttons = [
        [InlineKeyboardButton("🛒 Amazon-ൽ മികച്ച വിലയ്ക്ക് വാങ്ങുക", url=amazon_grocery_url)],
        [InlineKeyboardButton("🔵 Flipkart ഓഫറുകൾ കാണുക", url=flipkart_grocery_url)],
        [InlineKeyboardButton("🔥 40% മുതൽ 80% വരെ പ്രൈസ് ഡ്രോപ്പുകൾ", url=amazon_price_drops)]
    ]

    reply_msg = (
        f"✅ *{display_name} കണ്ടെത്താൻ സാധിച്ചു!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *പ്രത്യേകതകൾ:*\n"
        f"• കടകളിലേതിനേക്കാൾ വലിയ വിലക്കുറവ്\n"
        f"• 100% ഒറിജിനൽ വിശ്വസനീയ ബ്രാൻഡുകൾ\n"
        f"• നേരിട്ട് വീട്ടിലെത്തിക്കുന്ന സർവീസ്\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 *വില പരിശോധിക്കാനും വാങ്ങാനും താഴെ ക്ലിക്ക് ചെയ്യുക:*"
    )

    await update.message.reply_text(
        reply_msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- പ്രൈസ് ഡ്രോപ്പ് എഞ്ചിൻ ---
def extract_deal_info(entry):
    raw_title = getattr(entry, 'title', '')
    clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
    clean_title = html.unescape(clean_title)

    content = f"{clean_title} {getattr(entry, 'summary', '')}".lower()

    is_useful = any(keyword in content for keyword in TRUSTED_KEYWORDS)
    if not is_useful:
        return None, None, None, None, None, None, None, None

    image_url = None
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url')
    if not image_url and hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        image_url = entry.enclosures[0].get('href')
    if not image_url:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', getattr(entry, 'summary', ''))
        if img_match:
            image_url = img_match.group(1)

    prices = [int(p.replace(',', '')) for p in re.findall(r'(?:Rs\.?|INR|₹)\s?(\d+[\d,]*)', content, re.IGNORECASE)]
    discount_match = re.search(r'(\d+)%\s*off', content, re.IGNORECASE)

    deal_price_num = prices[0] if prices else 0
    mrp_num = prices[1] if len(prices) > 1 else (prices[0] if prices else 0)

    deal_price = f"₹{deal_price_num}" if deal_price_num > 0 else "പ്രത്യേക ഓഫർ വില"
    mrp_price = f"~~₹{mrp_num}~~" if (mrp_num > deal_price_num and deal_price_num > 0) else ""

    savings_text = ""
    if mrp_num > deal_price_num and deal_price_num > 0:
        savings = mrp_num - deal_price_num
        savings_text = f"💵 ലാഭം: ₹{savings}"

    discount = f"({discount_match.group(1)}% OFF)" if discount_match else ""

    search_words = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
    short_search = " ".join(search_words.split()[:4])
    encoded_query = urllib.parse.quote_plus(short_search)
    final_link = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"

    return clean_title, final_link, "Amazon", image_url, deal_price, mrp_price, discount, savings_text

# --- ചാനൽ പോസ്റ്റിംഗ് ---
async def send_deal_to_telegram(bot, title, final_link, platform_name, image_url, deal_price, mrp_price, discount, savings_text):
    try:
        caption = (
            f"🔥 *വമ്പൻ വിലക്കുറവ് (PRICE DROP ALERT)!*\n\n"
            f"📦 *ഉൽപ്പന്നം:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *ഇന്നത്തെ ഓഫർ വില:* *{deal_price}* {mrp_price} {discount}\n"
        )
        if savings_text:
            caption += f"🎉 *{savings_text}*\n"

        caption += (
            f"🛡️ 100% ഒറിജിനൽ ഗ്യാരണ്ടി | ടോപ്പ് റേറ്റിംഗ്\n"
            f"🚚 ഓർഡർ ചെയ്താൽ ഉടൻ വീട്ടിലെത്തും\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        inline_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 ഇപ്പോൾ തന്നെ ഓർഡർ ചെയ്യുക", url=final_link)]
        ])

        if image_url:
            try:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=caption, parse_mode="Markdown", reply_markup=inline_btn)
                return
            except Exception:
                pass

        await bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown", reply_markup=inline_btn, disable_web_page_preview=False)
    except Exception as e:
        print(f"⚠️ പോസ്റ്റിംഗ് എറർ: {e}")

async def check_all_feeds(bot):
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in FEED_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:5]:
                    title, final_link, platform, image_url, deal_price, mrp_price, discount, savings_text = extract_deal_info(entry)
                    if final_link and final_link not in posted_deals:
                        await send_deal_to_telegram(bot, title, final_link, platform, image_url, deal_price, mrp_price, discount, savings_text)
                        posted_deals.add(final_link)
                        await asyncio.sleep(4)
        except Exception as e:
            print(f"⚠️ ഫീഡ് എറർ: {e}")

async def channel_deals_loop(bot):
    await asyncio.sleep(3)
    while True:
        await check_all_feeds(bot)
        await asyncio.sleep(180)

async def main():
    # ക്ലൗഡ് കോൺഫ്ലിക്റ്റ് ഒഴിവാക്കാൻ പഴയ സെഷനുകൾ ക്ലിയർ ചെയ്യുന്നു
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_query))
    application.add_handler(CommandHandler("start", handle_user_query))

    asyncio.create_task(channel_deals_loop(application.bot))

    await application.initialize()
    await application.start()
    
    try:
        await application.updater.start_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"Polling handled: {e}")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(main())
