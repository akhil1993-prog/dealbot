import asyncio
import datetime
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


# --- 1. സ്മാർട്ട് സെർച്ച് (4★+ ക്വാളിറ്റി ഫിൽട്ടർ) ---
async def handle_normal_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.message.text.strip()

    if query == "/start":
        await update.message.reply_text(
            "👋 *Prime Finder Smart Quality Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "ആമസോണിലെ മോശം ക്വാളിറ്റിയും ഫേക്ക് പ്രൊഡക്റ്റുകളും ഒഴിവാക്കി **4★+ റേറ്റിംഗുള്ള മികച്ച ഒറിജിനൽ പ്രൊഡക്റ്റുകൾ മാത്രം** കണ്ടെത്താൻ സാധനത്തിന്റെ പേര് ഇവിടെ അയക്കൂ.\n\n"
            "ഉദാഹരണം: `smart watch`, `running shoes`, `earbuds`",
            parse_mode="Markdown",
        )
        return

    encoded_query = urllib.parse.quote_plus(query)
    amazon_filtered_url = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    amazon_bestseller_url = f"https://www.amazon.in/s?k={encoded_query}&s=exact-aware-popularity-rank&tag={AMAZON_TAG}"
    flipkart_filtered_url = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link=https://www.flipkart.com/search?q={encoded_query}&sort=popularity"

    reply_text = (
        f"🎯 *Prime Verified Smart Search Results:* \n"
        f"📦 *Query:* _{query}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ *1. Top Rated Products (4★+ Rating Only):*\n"
        f"👉 [ആമസോണിലെ 4★+ മികച്ച ഉൽപ്പന്നങ്ങൾ കാണുക]({amazon_filtered_url})\n\n"
        f"🔥 *2. Best Sellers & Most Bought:*\n"
        f"👉 [ഏറ്റവും കൂടുതൽ ആളുകൾ വാങ്ങിയവ കാണുക]({amazon_bestseller_url})\n\n"
        f"🔵 *3. Flipkart Top Rated Picks:*\n"
        f"👉 [ഫ്ലിപ്കാർട്ട് ജനപ്രിയ കളക്ഷൻ കാണുക]({flipkart_filtered_url})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛡️ *Quality Checklist:* 100% Genuine Brands | Easy Returns"
    )
    await update.message.reply_text(
        reply_text, parse_mode="Markdown", disable_web_page_preview=True
    )


# --- 2. ഷെഡ്യൂൾഡ് ഓട്ടോ-പോസ്റ്റിംഗ് (ബയിംഗ് ഗൈഡ് & ഗാഡ്‌ജെറ്റ്സ്) ---
async def scheduled_curated_posts(bot):
    """ദിവസവും കൃത്യസമയത്ത് ഓട്ടോമാറ്റിക്കായി ബയിംഗ് ഗൈഡുകളും പ്രോബ്ലം સોൾവിംഗ് ഗാഡ്‌ജെറ്റുകളും പോസ്റ്റ് ചെയ്യുന്നു"""
    while True:
        now = datetime.datetime.now()
        day = now.weekday()  # 0: തിങ്കൾ, 1: ചൊവ്വ ... 6: ഞായർ

        # ദിവസവും ഒരു തവണ പോസ്റ്റ് ചെയ്യാൻ
        try:
            if day in [0, 2]:  # തിങ്കൾ & ബുധൻ: ബയിംഗ് ഗൈഡ്
                guide_url_1 = f"https://www.amazon.in/s?k=boat+airdopes&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
                guide_url_2 = f"https://www.amazon.in/s?k=noise+earbuds&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
                msg = (
                    "🎧 *Weekly Top Picks: Best Earbuds Under ₹1,500* ⭐⭐⭐⭐⭐\n\n"
                    "മികച്ച സൗണ്ട് ക്വാളിറ്റിയും ഉയർന്ന ബാറ്ററിയുമുള്ള 4★+ ചോയ്‌സുകൾ:\n\n"
                    f"1️⃣ *boAt Airdopes (4.1★)* 👉 [ഓർഡർ ചെയ്യൂ]({guide_url_1})\n"
                    f"2️⃣ *Noise True Wireless (4.2★)* 👉 [ഓർഡർ ചെയ്യൂ]({guide_url_2})\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ _100% Original Brand Warranty & Easy Replacement Available!_"
                )
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )

            elif day in [1, 3]:  # ചൊവ്വ & വ്യാഴം: പ്രോബ്ലം-സോൾവിംഗ് ഗാഡ്‌ജെറ്റുകൾ
                gadget_url = f"https://www.amazon.in/s?k=smart+home+gadgets&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
                msg = (
                    "🛠️ *Smart Problem-Solving Gadgets Collection* 💡\n\n"
                    "ദൈനംദിന ജീവിതം എളുപ്പമാക്കുന്ന ഏറ്റവും പുതിയ സ്മാർട്ട് ഉപകരണങ്ങൾ:\n"
                    "• സ്മാർട്ട് കിച്ചൻ ടൂളുകൾ & ക്ലീനിംഗ് ഡിവൈസുകൾ\n"
                    "• കാർ & ബൈക്ക് എമർജൻസി ടൂളുകൾ\n\n"
                    f"👉 [4★+ മികച്ച ഗാഡ്‌ജെറ്റുകൾ കാണാൻ ക്ലിക്ക് ചെയ്യൂ]({gadget_url})\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ _Verified Sellers & Top Deals Assured!_"
                )
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )

            elif day in [4, 5]:  # വെള്ളി & ശനി: സീസണൽ & ട്രെൻഡിംഗ്
                trend_url = f"https://www.amazon.in/s?k=trending+fashion+and+home&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
                msg = (
                    "🌟 *Weekend Trending & Lifestyle Picks* 🛍️\n\n"
                    "ഈ ആഴ്ചയിലെ ഏറ്റവും ജനപ്രിയ ഫാഷൻ, ഹോം ഡെക്കോർ ട്രെൻഡുകൾ:\n"
                    "• വൻ വിലക്കുറവിലുള്ള മികച്ച ബ്രാൻഡുകൾ\n"
                    "• ഉയർന്ന കസ്റ്റമർ റേറ്റിംഗുള്ള പുതിയ കളക്ഷൻ\n\n"
                    f"👉 [ട്രെൻഡിംഗ് ഓഫറുകൾ പരിശോധിക്കാൻ ക്ലിക്ക് ചെയ്യൂ]({trend_url})\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ _Prime Verified Quality Assurance!_"
                )
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
        except Exception as e:
            print(f"⚠️ ഷെഡ്യൂൾഡ് പോസ്റ്റിംഗ് എറർ: {e}")

        # അടുത്ത പോസ്റ്റിംഗിനായി 24 മണിക്കൂർ കാത്തിരിക്കും
        await asyncio.sleep(86400)


# --- 3. സാധാരണ ലൈവ് ഡീലുകൾ ഓട്ടോമാറ്റിക്കായി അയക്കാൻ ---
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
            f"• 🔄 ഈസി റിട്ടേൺ / റീപ്ലേസ്‌മെന്റ് ലഭ്യമാണ്\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 *ഓർഡർ ചെയ്യാൻ ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് വാങ്ങൂ]({final_link})\n\n"
            f"💡 _മറ്റ് പ്രൊഡക്റ്റുകൾ തിരയാൻ ഈ ബോട്ടിൽ പേര് മാത്രം മെസ്സേജ് അയക്കുക!_"
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
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_normal_text)
    )
    application.add_handler(CommandHandler("start", handle_normal_text))

    # ഡീൽസും ഷെഡ്യൂൾഡ് ഗൈഡുകളും ബാക്ക്ഗ്രൗണ്ടിൽ റൺ ചെയ്യുന്നു
    asyncio.create_task(channel_deals_loop(application.bot))
    asyncio.create_task(scheduled_curated_posts(application.bot))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(main())
