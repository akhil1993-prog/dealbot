import asyncio
import os
import re
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
import requests
from telegram import Update
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

FEED_URLS = ["https://www.desidime.com/feed", "https://freekaamaal.com/feed"]

posted_deals = set()


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()


def clean_and_translate_query(text):
    text_lower = text.lower()
    numbers = re.findall(r"\d+", text)
    budget = f"under {numbers[0]}" if numbers else ""

    if any(
        w in text_lower
        for w in ["ഫോൺ", "phone", "mobile", "smart phone", "5g"]
    ):
        return f"5G Mobile {budget}".strip()
    elif any(
        w in text_lower
        for w in ["വാച്ച്", "watch", "smart watch", "സ്മാർട്ട് വാച്ച്"]
    ):
        return f"Smart Watch {budget}".strip()
    elif any(
        w in text_lower
        for w in ["ഇയർഫോൺ", "earbuds", "airpods", "headset", "earphones"]
    ):
        return f"Wireless Earbuds {budget}".strip()
    elif any(w in text_lower for w in ["ഷൂ", "shoe", "shoes", "sneakers"]):
        return f"Shoes {budget}".strip()
    elif any(w in text_lower for w in ["ലാപ്‌ടോപ്പ്", "laptop"]):
        return f"Laptop {budget}".strip()
    elif any(w in text_lower for w in ["സ്പീക്കർ", "speaker", "soundbar"]):
        return f"Bluetooth Speaker {budget}".strip()
    elif any(w in text_lower for w in ["ട്രിമ്മർ", "trimmer", "shaver"]):
        return f"Trimmer {budget}".strip()
    else:
        eng_only = re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
        return eng_only if eng_only else "best seller deals"


async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if user_text == "/start":
        await update.message.reply_text(
            "👋 *Prime Finder Smart Shopping Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "നിങ്ങൾക്ക് ആവശ്യമുള്ള സാധനത്തിന്റെ പേര് ഇവിടെ അയക്കൂ (ഉദാ: `15000 രൂപയിൽ താഴെ 5G ഫോൺ`, `smart watch`, `shoes`).\n\n"
            "4★+ റേറ്റിംഗുള്ള മികച്ച ഓഫറുകൾ ഞാൻ നൽകാം!",
            parse_mode="Markdown",
        )
        return

    search_keyword = clean_and_translate_query(user_text)
    encoded_query = urllib.parse.quote_plus(search_keyword)

    # 1. ആമസോൺ 4★+ റേറ്റിംഗ് ഫിൽട്ടർ ലിങ്ക്
    amazon_url = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"

    # 2. ഫ്ലിപ്കാർട്ട് ആപ്പ് / വെബ്സൈറ്റ് നേരിട്ട് ഓപ്പൺ ആകുന്ന ക്ലീൻ സെർച്ച് ലിങ്ക്
    flipkart_direct_url = f"https://www.flipkart.com/search?q={encoded_query}&sort=popularity"

    reply_text = (
        f"🎯 *Prime Verified Deals Found!* \n"
        f"📦 *Product:* _{search_keyword}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟠 *Amazon Top Rated (4★+ Only):*\n"
        f"👉 [Amazon-ൽ നിന്ന് ഓർഡർ ചെയ്യുക]({amazon_url})\n\n"
        f"🔵 *Flipkart Popular Results:*\n"
        f"👉 [Flipkart-ൽ നിന്ന് ഓർഡർ ചെയ്യുക]({flipkart_direct_url})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛡️ _100% ഒറിജിനൽ ബ്രാൻഡുകളും ഫാസ്റ്റ് ഡെലിവറിയും!_"
    )

    await update.message.reply_text(
        reply_text, parse_mode="Markdown", disable_web_page_preview=True
    )


# --- ചാനൽ ഡീൽസ് ഓട്ടോമേഷൻ ---
def get_real_url_and_platform(text_or_url):
    if not text_or_url:
        return None, None
    amz = re.search(r"https?://(?:www\.)?amazon\.in/[^\s\"\'>]+", text_or_url)
    if amz:
        clean = amz.group(0).split("?")[0]
        return f"{clean}?tag={AMAZON_TAG}", "Amazon"

    fk = re.search(r"https?://(?:www\.)?flipkart\.com/[^\s\"\'>]+", text_or_url)
    if fk:
        clean = fk.group(0).split("?")[0]
        # സിംഗിൾ പ്രൊഡക്റ്റ് ലിങ്കുകൾ EarnKaro വഴി കൃത്യമായി വർക്ക് ചെയ്യും
        return (
            f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}",
            "Flipkart",
        )

    return None, None


async def send_deal_to_telegram(bot, title, final_link, platform_name):
    try:
        badges = {
            "Amazon": "🟠 *Amazon Verified Deal*",
            "Flipkart": "🔵 *Flipkart Assured Deal*",
        }
        badge = badges.get(platform_name, "🛍️ *Prime Verified Deal*")
        message_text = (
            f"{badge} ⭐⭐⭐⭐⭐\n\n"
            f"📦 *Product:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ *Quality & Trust Assured:*\n"
            f"• 🏆 100% Original Brand Product\n"
            f"• 🏬 Top Verified Sellers Only\n"
            f"• 🔄 Easy Returns & Replacement Available\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 *ഓർഡർ ചെയ്യാൻ ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് വാങ്ങൂ]({final_link})"
        )
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            parse_mode="Markdown",
            disable_web_page_preview=False,
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
                title = getattr(entry, "title", "Special Deal")
                link = getattr(entry, "link", "")
                summary = getattr(entry, "summary", "")
                content = f"{link} {summary}"
                final_link, platform = get_real_url_and_platform(content)
                if final_link and final_link not in posted_deals:
                    await send_deal_to_telegram(
                        bot, title, final_link, platform
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
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_query)
    )
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
