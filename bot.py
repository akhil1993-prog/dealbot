import asyncio
import os
import re
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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


# --- കസ്റ്റമർ സെർച്ച് കമാൻഡ് ഫീച്ചർ (/search) ---
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text(
            "🔍 ദയവായി നിങ്ങൾ തിരയുന്ന സാധനത്തിന്റെ പേര് നൽകുക.\n\n"
            "ഉദാഹരണം: `/search boat airpodes` അല്ലെങ്കിൽ `/search 5g mobile`",
            parse_mode="Markdown",
        )
        return

    encoded_query = urllib.parse.quote_plus(query)
    amazon_search_url = f"https://www.amazon.in/s?k={encoded_query}&tag={AMAZON_TAG}"
    flipkart_search_url = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link=https://www.flipkart.com/search?q={encoded_query}"

    reply_text = (
        f"🔎 *Search Results for:* _{query}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ *Amazon Deals & Best Sellers:*\n"
        f"👉 [Amazon-ൽ തിരയുക & വാങ്ങുക]({amazon_search_url})\n\n"
        f"🛍️ *Flipkart Deals & Offers:*\n"
        f"👉 [Flipkart-ൽ തിരയുക & വാങ്ങുക]({flipkart_search_url})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ _100% Genuine & Verified Products Assured!_"
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
            f"🛒 *ഓർഡർ ചെയ്യാൻ താഴെ കാണുന്ന ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് വാങ്ങൂ]({final_link})\n\n"
            f"🔍 _നിങ്ങൾക്ക് ആവശ്യമുള്ള പ്രൊഡക്റ്റ് സെർച്ച് ചെയ്യാൻ ബോട്ടിൽ_ `/search <item>` _ടൈപ്പ് ചെയ്യുക._"
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
    application.add_handler(CommandHandler("search", search_command))

    # ബാക്ക്ഗ്രൗണ്ടിൽ ഡീൽ പോസ്റ്റിംഗ് തുടങ്ങുന്നു
    asyncio.create_task(channel_deals_loop(application.bot))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # എപ്പോഴും റൺ ആകാൻ
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(main())
