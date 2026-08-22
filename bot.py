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

# --- പ്രധാന ക്രമീകരണങ്ങൾ (Bot Configurations) ---
BOT_TOKEN = "8996059238:AAEkf-zvMgRqUFG0Q-oJ39alhTcOfrldwuA"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"
ADMIN_USER_ID = 0  # @userinfobot വഴി ലഭിച്ച യൂസർ ഐഡി ഇവിടെ നൽകാം

FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed"
]

TRENDS_RSS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=IN"

posted_deals = set()
registered_users = set()

IST = timezone(timedelta(hours=5, minutes=30))

# --- വെബ് സെർവർ (Render 24/7 സജീവമായിരിക്കാൻ) ---
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- ഗൂഗിൾ ട്രെൻഡ്സ് ഉൽപ്പന്നങ്ങൾ ശേഖരിക്കുന്നു ---
def get_trending_searches():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        feed = feedparser.parse(TRENDS_RSS_URL)
        items = []
        for entry in feed.entries[:6]:
            clean_title = re.sub(r'<[^>]+>', '', getattr(entry, 'title', '')).strip()
            if clean_title and clean_title not in items:
                items.append(clean_title)
        if items:
            return items
    except Exception as e:
        print(f"⚠️ ഗൂഗിൾ ട്രെൻഡ്സ് എറർ: {e}")
    
    # ബാക്കപ്പ് ട്രെൻഡിംഗ് ലിസ്റ്റ്
    return [
        "Smartphones 5G",
        "Smart Watches",
        "Wireless Earbuds",
        "Branded Running Shoes",
        "Home Gadgets",
        "Fashion Clothing"
    ]

# --- സ്ഥിരമായ മെനു കീബോർഡ് (Malayalam UI) ---
def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("📱 മൊബൈൽ & 5G"), KeyboardButton("🎧 ഇയർബഡ്സ് & ഓഡിയോ")],
        [KeyboardButton("⌚ സ്മാർട്ട് വാച്ചുകൾ"), KeyboardButton("👟 ഫാഷൻ & ഷൂസ്")],
        [KeyboardButton("🔥 ട്രെൻഡിംഗ് സെർച്ചുകൾ"), KeyboardButton("⚡ ലൂട്ട് ഡീലുകൾ (₹499 താഴെ)")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- കാറ്റഗറി & ഹാഷ്‌ടാഗ് നിർണ്ണയം ---
def detect_category_and_query(text):
    text_lower = text.lower()
    numbers = re.findall(r'\d+', text)
    budget = f"under {numbers[0]}" if numbers else ""

    if any(w in text_lower for w in ["മൊബൈൽ", "ഫോൺ", "phone", "mobile", "5g", "സ്മാർട്ട്ഫോൺ"]):
        return "electronics", f"5G smartphone {budget}".strip(), "#Smartphones #TechDeals #5G"
    elif any(w in text_lower for w in ["ഇയർബഡ്സ്", "ഓഡിയോ", "earbuds", "audio", "earphone", "ഹെഡ്സെറ്റ്"]):
        return "electronics", f"wireless earbuds {budget}".strip(), "#Audio #Earbuds #MusicDeals"
    elif any(w in text_lower for w in ["വാച്ച്", "watch", "smartwatch", "സ്മാർട്ട് വാച്ച്"]):
        return "electronics", f"smartwatch {budget}".strip(), "#Smartwatch #Fitness #Wearables"
    elif any(w in text_lower for w in ["ഫാഷൻ", "ഷൂസ്", "ഷർട്ട്", "സാരി", "shoe", "shoes", "fashion", "dress"]):
        return "fashion", f"fashion shoes clothing {budget}".strip(), "#Fashion #Style #TrendingFashion"
    elif any(w in text_lower for w in ["ബ്യൂട്ടി", "സ്കിൻകെയർ", "beauty", "cream", "lipstick", "perfume"]):
        return "beauty", f"beauty skincare {budget}".strip(), "#Beauty #PersonalCare #Cosmetics"
    elif any(w in text_lower for w in ["ലൂട്ട്", "loot", "499", "ഓഫർ", "offer"]):
        return "loot", "deals of the day under 499", "#LootDeal #MegaSavings #BudgetFinds"
    else:
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        return "general", f"{clean if clean else 'top deals'} {budget}".strip(), "#TopDeals #AmazonOffers"

# --- ഉപഭോക്താവിന്റെ സന്ദേശങ്ങൾക്കുള്ള മറുപടി ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        registered_users.add(update.effective_user.id)

    user_text = update.message.text.strip()

    # /start സ്വാഗത സന്ദേശം
    if user_text == "/start":
        welcome_text = (
            "👋 *Prime Finder സ്മാർട്ട് ഷോപ്പിംഗ് അസിസ്റ്റന്റിലേക്ക് സ്വാഗതം!*\n\n"
            "Amazon, Flipkart, Myntra തുടങ്ങിയ മുൻനിര സൈറ്റുകളിലെ മികച്ച 4★+ ഓഫറുകൾ നിമിഷങ്ങൾക്കകം കണ്ടെത്താൻ ഞാൻ സഹായിക്കാം.\n\n"
            "👇 *താഴെ കാണുന്ന മെനുവിൽ നിന്ന് കാറ്റഗറി തിരഞ്ഞെടുക്കുക അല്ലെങ്കിൽ സാധനത്തിന്റെ പേര് ഇവിടെ ടൈപ്പ് ചെയ്യുക:*"
        )
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        return

    # ട്രെൻഡിംഗ് സെർച്ച് ബട്ടൺ
    if "ട്രെൻഡിംഗ്" in user_text or "Trending" in user_text:
        trends = get_trending_searches()
        msg = "🔥 *ഇന്ന് ആളുകൾ ഏറ്റവും കൂടുതൽ തിരയുന്ന ട്രെൻഡിംഗ് ഉൽപ്പന്നങ്ങൾ:*\n\n"
        buttons = []
        for i, item in enumerate(trends, 1):
            msg += f"• *{i}. {item}*\n"
            encoded_item = urllib.parse.quote_plus(item)
            amz_url = f"https://www.amazon.in/s?k={encoded_item}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
            buttons.append([InlineKeyboardButton(f"🔎 {item} ഓഫറുകൾ കാണുക", url=amz_url)])

        msg += "\n━━━━━━━━━━━━━━━━━━━━\n🛒 *താല്പര്യമുള്ള ഉൽപ്പന്നം കാണാൻ താഴെയുള്ള ബട്ടണിൽ ക്ലിക്ക് ചെയ്യുക:*"
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # സാധാരണ കാറ്റഗറി അല്ലെങ്കിൽ സെർച്ച്
    cat_type, search_query, hashtags = detect_category_and_query(user_text)
    encoded = urllib.parse.quote_plus(search_query)

    amazon_url = f"https://www.amazon.in/s?k={encoded}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_url = f"https://www.flipkart.com/search?q={encoded}&sort=popularity"
    myntra_url = f"https://www.myntra.com/{encoded}"

    if cat_type == "fashion":
        inline_buttons = [
            [InlineKeyboardButton("🟠 Amazon Fashion (4★+ റേറ്റിംഗ്)", url=amazon_url)],
            [InlineKeyboardButton("🔵 Flipkart Fashion ഓഫറുകൾ", url=flipkart_url)],
            [InlineKeyboardButton("🔴 Myntra ട്രെൻഡിംഗ് കളക്ഷൻ", url=myntra_url)]
        ]
    elif cat_type == "beauty":
        nykaa_url = f"https://www.nykaa.com/search/result/?q={encoded}"
        inline_buttons = [
            [InlineKeyboardButton("🟠 Amazon Beauty (4★+ റേറ്റിംഗ്)", url=amazon_url)],
            [InlineKeyboardButton("🌸 Nykaa 100% ഒറിജിനൽ സ്റ്റോർ", url=nykaa_url)],
            [InlineKeyboardButton("🔴 Myntra Beauty കളക്ഷൻ", url=myntra_url)]
        ]
    elif cat_type == "loot":
        amz_loot = f"https://www.amazon.in/deals?tag={AMAZON_TAG}"
        inline_buttons = [
            [InlineKeyboardButton("🔥 ആമസോൺ മെഗാ ഡീലുകൾ (Up to 70% Off)", url=amz_loot)],
            [InlineKeyboardButton("⚡ ഫ്ലിപ്കാർട്ട് സൂപ്പർ ഓഫറുകൾ", url="https://www.flipkart.com/offers-list/top-offers")]
        ]
    else:
        inline_buttons = [
            [InlineKeyboardButton("🟠 Amazon-ൽ നിന്ന് വാങ്ങൂ (4★+ Only)", url=amazon_url)],
            [InlineKeyboardButton("🔵 Flipkart-ൽ നിന്ന് വാങ്ങൂ (Assured)", url=flipkart_url)]
        ]

    reply_markup = InlineKeyboardMarkup(inline_buttons)
    reply_msg = (
        f"🎯 *Prime വെരിഫൈഡ് റിസൾട്ടുകൾ:* \n"
        f"📦 *Product:* _{search_query}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ *ക്വാളിറ്റി & വാറന്റി ഗ്യാരണ്ടി:*\n"
        f"• 4★+ ഉപഭോക്തൃ റേറ്റിംഗുള്ള ഉൽപ്പന്നങ്ങൾ മാത്രം\n"
        f"• 100% ഒറിജിനൽ ബ്രാൻഡുകൾ & ഈസി റീപ്ലേസ്‌മെന്റ്\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 *ഓർഡർ ചെയ്യാൻ താഴെയുള്ള ബട്ടണുകളിൽ ക്ലിക്ക് ചെയ്യുക:*"
    )

    await update.message.reply_text(
        reply_msg,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# --- അഡ്മിൻ ബ്രോഡ്കാസ്റ്റ് ഫീച്ചർ ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_USER_ID != 0 and user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ *നിങ്ങൾക്ക് ഈ കമാൻഡ് ഉപയോഗിക്കാൻ അനുമതിയില്ല.*", parse_mode="Markdown")
        return

    broadcast_msg = update.message.text.replace("/broadcast", "").strip()
    if not broadcast_msg:
        await update.message.reply_text("⚠️ *ഉപയോഗിക്കേണ്ട വിധം:* `/broadcast നിങ്ങളുടെ സന്ദേശം`", parse_mode="Markdown")
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
                text=f"📢 *Prime Finder സ്പെഷ്യൽ അലർട്ട്:*\n\n{broadcast_msg}",
                parse_mode="Markdown"
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await update.message.reply_text(f"✅ ബ്രോഡ്കാസ്റ്റ് പൂർത്തിയായി! ({success_count}/{len(registered_users)})", parse_mode="Markdown")

# --- ലൈവ് ഡീൽ വിവരങ്ങൾ വേർതിരിച്ചെടുക്കുന്നു ---
def extract_deal_info(entry):
    title = getattr(entry, 'title', 'Special Verified Deal')
    content = f"{title} {getattr(entry, 'summary', '')}"

    # ഇമേജ് കണ്ടെത്തുന്നു
    image_url = None
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url')
    if not image_url and hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        image_url = entry.enclosures[0].get('href')
    if not image_url:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', getattr(entry, 'summary', ''))
        if img_match:
            image_url = img_match.group(1)

    # വിലയും ഡിസ്കൗണ്ടും
    prices = re.findall(r'(?:Rs\.?|INR|₹)\s?(\d+[\d,]*)', content, re.IGNORECASE)
    discount_match = re.search(r'(\d+%\s*off)', content, re.IGNORECASE)

    deal_price = f"₹{prices[0]}" if prices else "പ്രത്യേക ഓഫർ വില"
    mrp_price = f"~~₹{prices[1]}~~" if len(prices) > 1 else ""
    discount = f"({discount_match.group(1).upper()})" if discount_match else ""

    # അഫിലിയേറ്റ് ലിങ്കുകൾ
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

# --- ചാനലിലേക്ക് മലയാളം ഫോർമാറ്റിൽ പോസ്റ്റ് ചെയ്യുന്നു ---
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
            f"📦 *ഉൽപ്പന്നം:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *ഓഫർ വില:* *{deal_price}* {mrp_price} {discount}\n"
            f"🛡️ *ക്വാളിറ്റി:* 100% ഒറിജിനൽ ബ്രാൻഡ് വാറന്റി\n"
            f"🏬 *സെല്ലർ:* വെരിഫൈഡ് ടോപ്പ് സെല്ലർമാർ മാത്രം\n"
            f"🔄 *സേവനം:* ഈസി റീപ്ലേസ്‌മെന്റും ഫാസ്റ്റ് ഡെലിവറിയും\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 {hashtags}"
        )

        inline_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🛒 {platform_name}-ൽ നിന്ന് വാങ്ങൂ", url=final_link)]
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

# --- ചാനൽ ഫീഡുകൾ തുടർച്ചയായി പരിശോധിക്കുന്നു ---
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

# --- പ്രധാന ഫംഗ്ഷൻ (Main Function) ---
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
