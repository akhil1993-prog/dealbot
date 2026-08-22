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
ADMIN_USER_ID = 0  # Replace with your Telegram numeric ID from @userinfobot

FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed"
]

posted_deals = set()
registered_users = set()

IST = timezone(timedelta(hours=5, minutes=30))

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- മെനു കീബോർഡ് ---
def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("📱 Mobiles & 5G"), KeyboardButton("🎧 Earbuds & Audio")],
        [KeyboardButton("⌚ Smart Watches"), KeyboardButton("👟 Shoes & Fashion")],
        [KeyboardButton("💄 Beauty & Care"), KeyboardButton("🔥 Loot Deals (Under ₹499)")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- അഡ്മിൻ ബ്രോഡ്കാസ്റ്റ് ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_USER_ID != 0 and user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ *അനുമതിയില്ല.*", parse_mode="Markdown")
        return

    broadcast_msg = update.message.text.replace("/broadcast", "").strip()
    if not broadcast_msg:
        await update.message.reply_text("⚠️ `/broadcast <message>` നൽകുക.", parse_mode="Markdown")
        return

    if not registered_users:
        await update.message.reply_text("⚠️ ഉപയോക്താക്കൾ ആരും രജിസ്റ്റർ ആയിട്ടില്ല.", parse_mode="Markdown")
        return

    success_count = 0
    await update.message.reply_text(f"⏳ {len(registered_users)} പേർക്ക് അയക്കുന്നു...", parse_mode="Markdown")

    for uid in list(registered_users):
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 *Prime Finder Alert:*\n\n{broadcast_msg}",
                parse_mode="Markdown"
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ ബ്രോഡ്കാസ്റ്റ് പൂർത്തിയായി! ({success_count}/{len(registered_users)})", parse_mode="Markdown")

# --- കാറ്റഗറി & ഹാഷ്‌ടാഗ് നിർണ്ണയം ---
def detect_category_and_query(text):
    text_lower = text.lower()
    numbers = re.findall(r'\d+', text)
    budget = f"under {numbers[0]}" if numbers else ""

    if "mobile" in text_lower or "5g" in text_lower or "ഫോൺ" in text_lower:
        return "electronics", f"5G smartphone {budget}".strip(), "#Smartphones #TechDeals"
    elif "earbud" in text_lower or "audio" in text_lower or "ഇയർഫോൺ" in text_lower:
        return "electronics", f"wireless earbuds {budget}".strip(), "#Audio #Earbuds #Music"
    elif "watch" in text_lower or "വാച്ച്" in text_lower:
        return "electronics", f"smartwatch {budget}".strip(), "#Smartwatch #Wearables"
    elif any(w in text_lower for w in ["shoe", "fashion", "shirt", "dress", "ഷൂ", "സാരി"]):
        return "fashion", f"fashion shoes clothing {budget}".strip(), "#Fashion #Clothing #Style"
    elif any(w in text_lower for w in ["beauty", "care", "lipstick", "cream"]):
        return "beauty", f"beauty skincare {budget}".strip(), "#Beauty #PersonalCare"
    elif "loot" in text_lower or "499" in text_lower or "today" in text_lower:
        return "loot", "deals of the day under 499", "#LootDeal #BestOffer #BudgetFinds"
    else:
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        return "general", f"{clean if clean else 'top deals'} {budget}".strip(), "#TopDeals #Shopping"

# --- യൂസർ സെർച്ച് അസിസ്റ്റന്റ് ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        registered_users.add(update.effective_user.id)

    user_text = update.message.text.strip()

    if user_text == "/start":
        welcome_text = (
            "👋 *Prime Finder Smart Shopping Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "താഴെ കാണുന്ന മെനുവിൽ നിന്ന് കാറ്റഗറി തിരഞ്ഞെടുക്കുക, അല്ലെങ്കിൽ സാധനത്തിന്റെ പേര് ടൈപ്പ് ചെയ്യുക."
        )
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        return

    cat_type, search_query, hashtags = detect_category_and_query(user_text)
    encoded = urllib.parse.quote_plus(search_query)

    amazon_url = f"https://www.amazon.in/s?k={encoded}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_url = f"https://www.flipkart.com/search?q={encoded}&sort=popularity"
    myntra_url = f"https://www.myntra.com/{encoded}"

    if cat_type == "fashion":
        inline_buttons = [
            [InlineKeyboardButton("🟠 Buy on Amazon (4★+ Only)", url=amazon_url)],
            [InlineKeyboardButton("🔵 View on Flipkart Offers", url=flipkart_url)],
            [InlineKeyboardButton("🔴 Trending on Myntra Store", url=myntra_url)]
        ]
    elif cat_type == "beauty":
        nykaa_url = f"https://www.nykaa.com/search/result/?q={encoded}"
        inline_buttons = [
            [InlineKeyboardButton("🟠 View on Amazon (4★+ Only)", url=amazon_url)],
            [InlineKeyboardButton("🌸 100% Genuine Nykaa Store", url=nykaa_url)],
            [InlineKeyboardButton("🔴 Explore Myntra Beauty", url=myntra_url)]
        ]
    elif cat_type == "loot":
        amz_loot = f"https://www.amazon.in/deals?tag={AMAZON_TAG}"
        inline_buttons = [
            [InlineKeyboardButton("🔥 Amazon Mega Deals (Up to 70% Off)", url=amz_loot)],
            [InlineKeyboardButton("⚡ Flipkart Super Value Deals", url="https://www.flipkart.com/offers-list/top-offers")]
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
        f"🛡️ *ക്വാളിറ്റി & വാറന്റി ഗ്യാരണ്ടി:*\n"
        f"• 4★+ ഉപഭോക്തൃ റേറ്റിംഗുള്ള ഉൽപ്പന്നങ്ങൾ മാത്രം\n"
        f"• 100% ഒറിജിനൽ ബ്രാൻഡുകൾ & ഈസി റിട്ടേൺ\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 *ഓർഡർ ചെയ്യാൻ താഴെയുള്ള ബട്ടണുകളിൽ ക്ലിക്ക് ചെയ്യുക:*"
    )

    await update.message.reply_text(
        reply_msg,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# --- പ്രൈസ്, ഡിസ്കൗണ്ട്, ഇമേജ് വേർതിരിച്ചെടുക്കുന്നു ---
def extract_deal_info(entry):
    title = getattr(entry, 'title', 'Special Verified Deal')
    content = f"{title} {getattr(entry, 'summary', '')}"
    
    # 1. ചിത്രങ്ങൾ
    image_url = None
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url')
    if not image_url and hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        image_url = entry.enclosures[0].get('href')
    if not image_url:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', getattr(entry, 'summary', ''))
        if img_match:
            image_url = img_match.group(1)

    # 2. വിലയും ഡിസ്കൗണ്ടും കണ്ടെത്തൽ
    prices = re.findall(r'(?:Rs\.?|INR|₹)\s?(\d+[\d,]*)', content, re.IGNORECASE)
    discount_match = re.search(r'(\d+%\s*off)', content, re.IGNORECASE)
    
    deal_price = f"₹{prices[0]}" if prices else "Special Deal Price"
    mrp_price = f"~~₹{prices[1]}~~" if len(prices) > 1 else ""
    discount = f"({discount_match.group(1).upper()})" if discount_match else ""

    # 3. അഫിലിയേറ്റ് ലിങ്ക്
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

    _, _, hashtags = detect_category_and_query(title)
    
    return final_link, platform, image_url, deal_price, mrp_price, discount, hashtags

# --- കൃത്യമായ പ്രൈസിംഗ് ലേഔട്ടോടെ ചാനൽ പോസ്റ്റിംഗ് ---
async def send_deal_to_telegram(bot, title, final_link, platform_name, image_url, deal_price, mrp_price, discount, hashtags):
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
            f"💰 *Offer Price:* *{deal_price}* {mrp_price} {discount}\n"
            f"🛡️ *Quality:* 100% ഒറിജിനൽ ബ്രാൻഡ് വാറന്റി\n"
            f"🏬 *Seller:* ടോപ്പ് റേറ്റിംഗുള്ള വെരിഫൈഡ് സെല്ലർമാർ മാത്രം\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 {hashtags}"
        )

        inline_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 Buy on {platform_name} Now", url=final_link)]
        ])

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
                pass

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
                final_link, platform, image_url, deal_price, mrp_price, discount, hashtags = extract_deal_info(entry)
                if final_link and final_link not in posted_deals:
                    await send_deal_to_telegram(
                        bot, title, final_link, platform, image_url, deal_price, mrp_price, discount, hashtags
                    )
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
