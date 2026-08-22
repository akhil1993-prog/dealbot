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


# --- മലയാളം/മംഗ്ലീഷ് ചോദ്യങ്ങളെ കൃത്യമായ ഇംഗ്ലീഷ് സെർച്ച് കീവേഡുകളാക്കി മാറ്റുന്നു ---
def extract_smart_keyword_and_advice(text):
    text_lower = text.lower()

    # ബഡ്ജറ്റ് കണ്ടെത്തൽ (ഉദാ: 15000, 20k)
    numbers = re.findall(r"\d+", text)
    budget = f"under {numbers[0]}" if numbers else ""

    # കാറ്റഗറി മാപ്പിംഗ്
    if any(
        w in text_lower
        for w in [
            "ഫോൺ",
            "phone",
            "mobile",
            "ക്യാമറ",
            "camera",
            "5g",
            "സ്മാർട്ട്ഫോൺ",
        ]
    ):
        keyword = f"5G smartphone camera {budget}".strip()
        advice = (
            f"📱 *മികച്ച 5G സ്മാർട്ട്‌ഫോണുകൾ ({budget}):*\n\n"
            f"• 🏆 *Redmi / Realme / Samsung 5G* - മികച്ച ക്യാമറയും ഫാസ്റ്റ് ചാർജിംഗും\n"
            f"• 🔋 5000mAh ബാറ്ററിയും മികച്ച പെർഫോമൻസും\n"
            f"• 4★+ കസ്റ്റമർ റേറ്റിംഗുള്ള ഒറിജിനൽ മോഡലുകൾ"
        )
    elif any(
        w in text_lower
        for w in ["വാച്ച്", "watch", "smartwatch", "സ്മാർട്ട് വാച്ച്"]
    ):
        keyword = f"smartwatch {budget}".strip()
        advice = (
            f"⌚ *മികച്ച സ്മാർട്ട് വാച്ചുകൾ ({budget}):*\n\n"
            f"• 🏆 *Noise / Fire-Boltt / Fastrack* - ബ്ലൂടൂത്ത് കോളിംഗും AMOLED ഡിസ്‌പ്ലേയും\n"
            f"• 💧 വാട്ടർ റെസിസ്റ്റന്റ് ബോഡിയും ഫിറ്റ്നസ് ട്രാക്കിംഗും"
        )
    elif any(
        w in text_lower
        for w in [
            "ഇയർഫോൺ",
            "earbuds",
            "airpods",
            "ബ്ലൂടൂത്ത്",
            "headset",
            "earphones",
        ]
    ):
        keyword = f"wireless earbuds {budget}".strip()
        advice = (
            f"🎧 *മികച്ച വയർലെസ്സ് ഇയർബഡ്സ് ({budget}):*\n\n"
            f"• 🏆 *boAt / Boult / Noise* - മികച്ച ബാസും നോയ്‌സ് ക്യാൻസലേഷനും\n"
            f"• ⚡ 40+ മണിക്കൂർ ബാറ്ററി ലൈഫും ഫാസ്റ്റ് ചാർജിംഗും"
        )
    elif any(w in text_lower for w in ["ഷൂ", "shoe", "shoes", "സ്നീക്കർ"]):
        keyword = f"running shoes {budget}".strip()
        advice = (
            f"👟 *മികച്ച ഷൂസ് കളക്ഷൻ ({budget}):*\n\n"
            f"• 🏆 *Puma / Sparx / Campus* - കംഫർട്ടബിൾ സോൾ & ലോങ് ലാസ്റ്റിംഗ് മെറ്റീരിയൽ"
        )
    elif any(w in text_lower for w in ["ലാപ്‌ടോപ്പ്", "laptop"]):
        keyword = f"laptop {budget}".strip()
        advice = (
            f"💻 *മികച്ച ലാപ്ടോപ്പുകൾ ({budget}):*\n\n"
            f"• 🏆 *HP / Lenovo / ASUS* - ഫാസ്റ്റ് പ്രോസസ്സറും മികച്ച ബാറ്ററിയും"
        )
    else:
        eng_only = re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
        keyword = eng_only if eng_only else "best deals electronics"
        advice = f"🛍️ *{text}* തിരഞ്ഞതിനുള്ള ഏറ്റവും മികച്ച 4★+ ഓഫറുകൾ താഴെ നൽകുന്നു:"

    return keyword, advice


async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if user_text == "/start":
        await update.message.reply_text(
            "👋 *Prime Finder Smart Shopping Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "ഷോപ്പിംഗുമായി ബന്ധപ്പെട്ട എന്ത് സംശയങ്ങളും ഇവിടെ ചോദിക്കാം (ഉദാ: `15000 രൂപയിൽ താഴെ നല്ല ക്യാമറയുള്ള ഫോൺ`, `smart watch`, `shoes`).\n\n"
            "മികച്ച ഉൽപ്പന്നങ്ങളും ഓഫർ ലിങ്കുകളും ഞാൻ തരാം!",
            parse_mode="Markdown",
        )
        return

    # ഉപഭോക്താവിന് സ്മാർട്ട് അസിസ്റ്റന്റ് മറുപടിയും കൃത്യമായ ഇംഗ്ലീഷ് ആമസോൺ ലിങ്കും ഉണ്ടാക്കുന്നു
    search_keyword, advice_text = extract_smart_keyword_and_advice(user_text)
    encoded_query = urllib.parse.quote_plus(search_keyword)

    amazon_url = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_url = f"https://www.flipkart.com/search?q={encoded_query}&sort=popularity"

    final_reply = (
        f"{advice_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 *ഓർഡർ ചെയ്യാൻ ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക (4★+ Only):*\n"
        f"👉 [Amazon-ൽ നിന്ന് വാങ്ങൂ]({amazon_url})\n"
        f"👉 [Flipkart-ൽ നിന്ന് വാങ്ങൂ]({flipkart_url})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ _100% Original Brand Warranty & Easy Replacement!_"
    )

    await update.message.reply_text(
        final_reply, parse_mode="Markdown", disable_web_page_preview=True
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
            f"🛡️ *ക്വാളിറ്റി & സെല്ലർ ഫീച്ചറുകൾ:*\n"
            f"• 🏆 100% ഒറിജിനൽ ബ്രാൻഡ്\n"
            f"• 🏬 ടോപ്പ് വെരിഫൈഡ് സെല്ലർമാർ മാത്രം\n"
            f"• 🔄 ഈസി റിട്ടേൺ ലഭ്യമാണ്\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 *ഓർഡർ ചെയ്യാൻ ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് വാങ്ങൂ]({final_link})\n\n"
            f"💡 _മറ്റ് സംശയങ്ങൾക്ക് ഈ ബോട്ടിനോട് നേരിട്ട് ചോദിക്കൂ!_"
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
