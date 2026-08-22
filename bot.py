import asyncio
import os
import re
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
from telegram import Bot

BOT_TOKEN = "8996059238:AAEkf-zvMgRqUFG0Q-oJ39alhTcOfrldwuA"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"

RSS_FEED_URL = "https://www.desidime.com/feed"

posted_deals = set()
bot = Bot(token=BOT_TOKEN)


# Render-ന് ആവശ്യമായ ഡമ്മി വെബ് സെർവർ
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()


def detect_and_convert_link(text_or_url):
    if not text_or_url:
        return None, None

    amazon_match = re.search(
        r"https?://(?:www\.)?amazon\.in/[^\s\"\'>]+", text_or_url
    )
    if amazon_match:
        clean_url = amazon_match.group(0).split("?")[0]
        return f"{clean_url}?tag={AMAZON_TAG}", "Amazon"

    flipkart_match = re.search(
        r"https?://(?:www\.)?flipkart\.com/[^\s\"\'>]+", text_or_url
    )
    if flipkart_match:
        clean_url = flipkart_match.group(0).split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", (
            "Flipkart"
        )

    myntra_match = re.search(
        r"https?://(?:www\.)?myntra\.com/[^\s\"\'>]+", text_or_url
    )
    if myntra_match:
        clean_url = myntra_match.group(0).split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", (
            "Myntra"
        )

    return None, None


async def send_deal_to_telegram(title, final_link, platform_name):
    try:
        badges = {
            "Amazon": "🟠 *Amazon Deal*",
            "Flipkart": "🔵 *Flipkart Deal*",
            "Myntra": "🔴 *Myntra Deal*",
        }
        badge = badges.get(platform_name, "🛍️ *Special Deal*")

        message_text = (
            f"{badge}\n\n"
            f"🔥 *{title}*\n\n"
            f"🛒 *ഓർഡർ ചെയ്യാൻ ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് വാങ്ങുക]({final_link})\n\n"
            f"⚡ _ഓഫർ അവസാനിക്കുന്നതിന് മുൻപ് വേഗത്തിൽ വാങ്ങൂ!_"
        )

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )
        print(f"✅ പോസ്റ്റ് ചെയ്തു ({platform_name}): {title[:35]}...")
    except Exception as e:
        print(f"⚠️ പോസ്റ്റിംഗ് എറർ: {e}")


async def check_all_deals():
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        if not feed.entries:
            return

        for entry in feed.entries[:10]:
            title = getattr(entry, "title", "Special Deal")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")

            combined_text = f"{link} {summary}"
            final_link, platform = detect_and_convert_link(combined_text)

            if final_link and final_link not in posted_deals:
                await send_deal_to_telegram(title, final_link, platform)
                posted_deals.add(final_link)
                await asyncio.sleep(5)
    except Exception as e:
        print(f"⚠️ ഫീഡ് എറർ: {e}")


async def run_bot():
    print("🚀 Prime Finder Auto Bot ക്ലൗഡിൽ റൺ ആകുന്നു...")
    while True:
        await check_all_deals()
        await asyncio.sleep(600)  # ഓരോ 10 മിനിറ്റിലും പുതിയ ഡീലുകൾ പരിശോധിക്കും


if __name__ == "__main__":
    # ബാക്ക്ഗ്രൗണ്ടിൽ വെബ് സെർവർ സ്റ്റാർട്ട് ചെയ്യുന്നു
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # ബോട്ട് റൺ ചെയ്യുന്നു
    asyncio.run(run_bot())
