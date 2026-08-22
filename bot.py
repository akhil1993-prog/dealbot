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

# --- വിശ്വസനീയമായ ബ്രാൻഡുകളുടെ ഫിൽട്ടർ ---
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

# --- മലയാളം മെനു ---
def get_daily_essential_keyboard():
    keyboard = [
        [KeyboardButton("🛒 നിത്യോപയോഗ സാധനങ്ങൾ (പലചരക്ക്)"), KeyboardButton("🧼 ക്ലീനിംഗ് & സോപ്പുകൾ")],
        [KeyboardButton("☕ ചായപ്പൊടി & പലഹാരങ്ങൾ"), KeyboardButton("🧴 പേഴ്സണൽ കെയർ & ഷാംപൂ")],
        [KeyboardButton("📱 മൊബൈൽ & ഇലക്ട്രോണിക്സ്"), KeyboardButton("🔥 ഇന്നത്തെ വമ്പൻ പ്രൈസ് ഡ്രോപ്പുകൾ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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

# --- ചാറ്റ് ഹാൻഡ്‌ലർ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        registered_users.add(update.effective_user.id)

    user_text = update.message.text.strip()

    if user_text == "/start":
        welcome_text = (
            "🙏 *നമസ്കാരം! Prime Finder സേവിംഗ്സ് അസിസ്റ്റന്റിലേക്ക് സ്വാഗതം.*\n\n"
            "സൂപ്പർമാർക്കറ്റുകളേക്കാൾ കുറഞ്ഞ വിലയിൽ സാധനങ്ങളും വലിയ വിലക്കുറവുകളും (Price Drops) കണ്ടെത്താൻ താഴെയുള്ള മെനു ഉപയോഗിക്കുക 👇"
        )
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_daily_essential_keyboard()
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

# --- പ്രൈസ് ഡ്രോപ്പ് എഞ്ചിൻ (Price Drop Calculation) ---
def extract_deal_info(entry):
    raw_title = getattr(entry, 'title', '')
    clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
    clean_title = html.unescape(clean_title)

    content = f"{clean_title} {getattr(entry, 'summary', '')}".lower()

    # ക്വാളിറ്റി ഫിൽട്ടർ
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

    # സംഖ്യകൾ വേർതിരിച്ച് വില കണക്കുകൂട്ടുന്നു
    prices = [int(p.replace(',', '')) for p in re.findall(r'(?:Rs\.?|INR|₹)\s?(\d+[\d,]*)', content, re.IGNORECASE)]
    discount_match = re.search(r'(\d+)%\s*off', content, re.IGNORECASE)

    deal_price_num = prices[0] if prices else 0
    mrp_num = prices[1] if len(prices) > 1 else (prices[0] if prices else 0)

    deal_price = f"₹{deal_price_num}" if deal_price_num > 0 else "പ്രത്യേക ഓഫർ വില"
    mrp_price = f"~~₹{mrp_num}~~" if (mrp_num > deal_price_num and deal_price_num > 0) else ""

    # ലാഭത്തിന്റെ തുക
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

# --- പ്രൈസ് ഡ്രോപ്പ് അലർട്ടോടെ ചാനൽ പോസ്റ്റിംഗ് ---
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
    await asyncio.sleep(2)
    while True:
        await check_all_feeds(bot)
        await asyncio.sleep(180)

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
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
