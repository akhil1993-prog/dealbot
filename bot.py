import asyncio
from datetime import datetime, timezone, timedelta
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

BOT_TOKEN = "8996059238:AAEkf-zvMgRqUFG0Q-oJ39alhTcOfrldwuA"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"

FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed"
]

posted_deals = set()
IST = timezone(timedelta(hours=5, minutes=30))

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- സ്ഥിരമായ മെനു കീബോർഡ് ---
def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("📱 Mobiles & 5G"), KeyboardButton("🎧 Earbuds & Audio")],
        [KeyboardButton("⌚ Smart Watches"), KeyboardButton("👟 Shoes & Fashion")],
        [KeyboardButton("💄 Beauty & Care"), KeyboardButton("🔥 Today's Top Loot")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- കാറ്റഗറി ഡിറ്റക്ഷൻ ---
def detect_category_and_query(text):
    text_lower = text.lower()
    numbers = re.findall(r'\d+', text)
    budget = f"under {numbers[0]}" if numbers else ""

    if "mobile" in text_lower or "5g" in text_lower or "ഫോൺ" in text_lower:
        return "electronics", f"5G smartphone {budget}".strip()
    elif "earbud" in text_lower or "audio" in text_lower or "ഇയർഫോൺ" in text_lower:
        return "electronics", f"wireless earbuds {budget}".strip()
    elif "watch" in text_lower or "വാച്ച്" in text_lower:
        return "electronics", f"smartwatch {budget}".strip()
    elif any(w in text_lower for w in ["shoe", "fashion", "shirt", "dress", "ഷൂ", "സാരി"]):
        return "fashion", f"fashion shoes clothing {budget}".strip()
    elif any(w in text_lower for w in ["beauty", "care", "lipstick", "cream"]):
        return "beauty", f"beauty skincare {budget}".strip()
    elif "loot" in text_lower or "today" in text_lower:
        return "loot", "deals of the day"
    else:
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        return "general", f"{clean if clean else 'top deals'} {budget}".strip()

# --- യൂസർ സെർച്ച് ഹാൻഡ്‌ലർ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if user_text == "/start":
        welcome_text = (
            "👋 *Prime Finder Smart Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "താഴെ കാണുന്ന മെനുവിൽ നിന്ന് കാറ്റഗറി തിരഞ്ഞെടുക്കുക, അല്ലെങ്കിൽ സാധനത്തിന്റെ പേര് ഇവിടെ ടൈപ്പ് ചെയ്യുക."
        )
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        return

    cat_type, search_query = detect_category_and_query(user_text)
    encoded = urllib.parse.quote_plus(search_query)

    amazon_url = f"https://www.amazon.in/s?k={encoded}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_url = f"https://www.flipkart.com/search?q={encoded}&sort=popularity"
    myntra_url = f"https://www.myntra.com/{encoded}"

    if cat_type == "fashion":
        inline_buttons = [
            [InlineKeyboardButton("🟠 Buy on Amazon (4★+)", url=amazon_url)],
            [InlineKeyboardButton("🔵 View on Flipkart", url=flipkart_url)],
            [InlineKeyboardButton("🔴 Trending on Myntra", url=myntra_url)]
        ]
    elif cat_type == "beauty":
        nykaa_url = f"https://www.nykaa.com/search/result/?q={encoded}"
        inline_buttons = [
            [InlineKeyboardButton("🟠 View on Amazon (4★+)", url=amazon_url)],
            [InlineKeyboardButton("🌸 100% Genuine Nykaa", url=nykaa_url)],
            [InlineKeyboardButton("🔴 Explore Myntra Beauty", url=myntra_url)]
        ]
    elif cat_type == "loot":
        amz_loot = f"https://www.amazon.in/deals?tag={AMAZON_TAG}"
        inline_buttons = [
            [InlineKeyboardButton("🔥 Amazon Mega Deals (Up to 70% Off)", url=amz_loot)],
            [InlineKeyboardButton("⚡ Flipkart Super Offers", url="https://www.flipkart.com/offers-list/top-offers")]
        ]
    else:
        inline_buttons = [
            [InlineKeyboardButton("🟠 View on Amazon (4★+ Only)", url=amazon_url)],
            [InlineKeyboardButton("🔵 Assured Deals on Flipkart", url=flipkart_url)]
        ]

    reply_markup = InlineKeyboardMarkup(inline_buttons)
    reply_msg = (
        f"🎯 *Prime Verified Results:* \n"
        f"📦 *Product:* _{search_query}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ *Quality Guarantee:*\n"
        f"• 4★+ Top-Rated Products Only\n"
        f"• 100% Genuine Brands & Easy Returns\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 *ഓർഡർ ചെയ്യാൻ താഴെയുള്ള ബട്ടണുകളിൽ ക്ലിക്ക് ചെയ്യുക:*"
    )

    await update.message.reply_text(
        reply_msg,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# --- ലിങ്കും ചിത്രവും വേർതിരിച്ചെടുക്കുന്നു ---
def extract_deal_info(entry):
    content = f"{getattr(entry, 'link', '')} {getattr(entry, 'summary', '')}"
    
    # 1. ചിത്രങ്ങൾ കണ്ടെത്തുന്നു
    image_url = None
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url')
    if not image_url and hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        image_url = entry.enclosures[0].get('href')
    if not image_url:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', getattr(entry, 'summary', ''))
        if img_match:
            image_url = img_match.group(1)

    # 2. അഫിലിയേറ്റ് ലിങ്ക് തയ്യാറാക്കുന്നു
    final_link, platform = None, None
    amz = re.search(r'https?://(?:www\.)?amazon\.in/[^\s"\'>]+', content)
    if amz:
        clean = amz.group(0).split('?')[0]
        final_link, platform = f"{clean}?tag={AMAZON_TAG}", "Amazon"
    else:
        fk = re.search(r'https?://(?:www\.)?flipkart\.com/[^\s"\'>]+', content)
        if fk:
            clean = fk.group(0).split('?')[0]
            final_link, platform = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Flipkart"
        else:
            myn = re.search(r'https?://(?:www\.)?myntra\.com/[^\s"\'>]+', content)
            if myn:
                clean = myn.group(0).split('?')[0]
                final_link, platform = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Myntra"

    return final_link, platform, image_url

# --- ഇമേജ് കാർഡ് സഹിതം ചാനൽ പോസ്റ്റിംഗ് ---
async def send_deal_to_telegram(bot, title, final_link, platform_name, image_url):
    try:
        badges = {
            "Amazon": "🟠 *Amazon Verified Deal*",
            "Flipkart": "🔵 *Flipkart Assured Deal*",
            "Myntra": "🔴 *Myntra Authentic Deal*"
        }
        badge = badges.get(platform_name, "🛍️ *Prime Verified Deal*")
        
        caption = (
            f"{badge} ⭐⭐⭐⭐⭐\n\n"
            f"📦 *Product:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ *Trust & Quality:*\n"
            f"• 🏆 100% Genuine Original Brand\n"
            f"• 🏬 Top Verified Sellers Only\n"
            f"• 🔄 Easy Replacement Available\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        inline_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 Buy on {platform_name} Now", url=final_link)]
        ])

        # ഇമേജ് ഉണ്ടെങ്കിൽ ഫോട്ടോ കാർഡായി അയക്കും
        if image_url:
            try:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=inline_btn
                )
                return
            except Exception:
                pass  # ഫോട്ടോ ലോഡ് ആയില്ലെങ്കിൽ താഴെ ടെക്സ്റ്റ് ആയി അയക്കും

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=caption,
            parse_mode="Markdown",
            reply_markup=inline_btn,
            disable_web_page_preview=False
        )
    except Exception as e:
        print(f"⚠️ പോസ്റ്റിംഗ് എറർ: {e}")

async def check_all_feeds(bot):
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in FEED_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:8]:
                title = getattr(entry, 'title', 'Special Deal')
                final_link, platform, image_url = extract_deal_info(entry)
                if final_link and final_link not in posted_deals:
                    await send_deal_to_telegram(bot, title, final_link, platform, image_url)
                    posted_deals.add(final_link)
                    await asyncio.sleep(6)
        except Exception as e:
            print(f"⚠️ ഫീഡ് എറർ: {e}")

async def channel_deals_loop(bot):
    while True:
        await check_all_feeds(bot)
        await asyncio.sleep(300)

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
