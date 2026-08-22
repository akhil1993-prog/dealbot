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


# --- സാധാരണക്കാർക്ക് പേര് മാത്രം അയച്ചാൽ മറുപടി നൽകുന്ന ഫീച്ചർ ---
async def handle_normal_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.message.text.strip()

    # സ്റ്റാർട്ട് കമാൻഡ് ആണെങ്കിൽ സ്വാഗതം പറയും
    if query == "/start":
        await update.message.reply_text(
            "👋 *Prime Finder Shopping Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "നിങ്ങൾക്ക് ആവശ്യമുള്ള ഏത് സാധനത്തിന്റെയും പേര് ഇവിടെ മെസ്സേജ് ആയി അയക്കൂ (ഉദാഹരണത്തിന്: `mobile`, `shoes`, `smart watch`, `shirt`).\n\n"
            "ഏറ്റവും മികച്ച ഓഫറുകൾ ഞങ്ങൾ കണ്ടെത്തി തരാം!",
            parse_mode="Markdown",
        )
        return

    encoded_query = urllib.parse.quote_plus(query)
    amazon_search_url = f"https://www.amazon.in/s?k={encoded_query}&tag={AMAZON_TAG}"
    flipkart_search_url = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link=https://www.flipkart.com/search?q={encoded_query}"

    reply_text = (
        f"🔎 *{query}* തിരഞ്ഞതിനുള്ള മികച്ച ഫലങ്ങൾ താഴെ നൽകുന്നു:\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟠 *Amazon Deals:*\n"
        f"👉 [Amazon-ൽ നിന്ന് ഓർഡർ ചെയ്യുക]({amazon_search_url})\n\n"
        f"🔵 *Flipkart Deals:*\n"
        f"👉 [Flipkart-ൽ നിന്ന് ഓർഡർ ചെയ്യുക]({flipkart_search_url})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ _100% ഒറിജിനൽ ബ്രാൻഡുകളും ഫാസ്റ്റ് ഡെലിവറിയും!_"
    )

    await update.message.reply_text(
        reply_text, parse_mode="Markdown", disable_web_page_preview=True
    )


# --- ചാനൽ ഡീൽസ് ഓട്ടോമേഷൻ ഫീച്ചർ ---
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
            f"🛡️ *Quality & Trust Assured:*\n"
            f"• 🏆 100% Original Brand Product\n"
            f"• 🏬 Top Verified Sellers Only\n"
            f"• 🔄 Easy Returns & Replacement Available\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 *വാങ്ങാൻ ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് ഓർഡർ ചെയ്യൂ]({final_link})\n\n"
            f"💡 _മറ്റ് പ്രൊഡക്റ്റുകൾ തിരയാൻ ഈ ബോട്ടിന് സാധനത്തിന്റെ പേര് മാത്രം മെസ്സേജ് അയക്കുക!_"
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

    # ഏതൊരു സാധാരണ മെസ്സേജിനും ഓട്ടോമാറ്റിക് സെർച്ച് നൽകുന്നു
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_normal_text)
    )
    application.add_handler(CommandHandler("start", handle_normal_text))

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
