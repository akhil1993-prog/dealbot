import asyncio
import os
import re
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
import requests
from telegram import Bot

BOT_TOKEN = "8996059238:AAEkf-zvMgRqUFG0Q-oJ39alhTcOfrldwuA"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"

# വിശ്വസനീയമായ പ്രധാന ഡീൽ ഫീഡുകൾ
FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed"
]

posted_deals = set()
bot = Bot(token=BOT_TOKEN)

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def extract_direct_url(url):
    """റീഡയറക്റ്റ് ലിങ്കുകളിൽ നിന്ന് യഥാർത്ഥ സ്റ്റോർ ലിങ്ക് കണ്ടെത്തുന്നു"""
    try:
        if "amazon" in url or "flipkart" in url or "myntra" in url:
            return url
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.url
    except Exception:
        return url

def convert_to_affiliate(real_url):
    if not real_url:
        return None, None
        
    if "amazon.in" in real_url:
        clean = real_url.split("?")[0]
        return f"{clean}?tag={AMAZON_TAG}", "Amazon"
    elif "flipkart.com" in real_url:
        clean = real_url.split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Flipkart"
    elif "myntra.com" in real_url:
        clean = real_url.split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Myntra"
        
    return None, None

async def send_deal_to_telegram(title, final_link, platform_name):
    try:
        badges = {
            "Amazon": "🟠 *Amazon Verified Deal*",
            "Flipkart": "🔵 *Flipkart Assured Deal*",
            "Myntra": "🔴 *Myntra Authentic Deal*"
        }
        badge = badges.get(platform_name, "🛍️ *Prime Verified Deal*")
        
        message_text = (
            f"{badge} ⭐⭐⭐⭐⭐\n\n"
            f"📦 *Product:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ *Quality & Trust Assured:*\n"
            f"• 🏆 *100% Original Brand Product*\n"
            f"• 🏬 *Top Verified Sellers Only*\n"
            f"• 🔄 *Easy Returns & Replacement*\n"
            f"• 🚚 *Fast Delivery Supported*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 *ഓർഡർ ചെയ്യാൻ താഴെ കാണുന്ന ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് വാങ്ങൂ]({final_link})\n\n"
            f"⚡ _ഓഫർ അവസാനിക്കുന്നതിന് മുൻപ് വേഗത്തിൽ വാങ്ങൂ!_"
        )
        
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        print(f"✅ പോസ്റ്റ് ചെയ്തു ({platform_name}): {title[:30]}...")
    except Exception as e:
        print(f"⚠️ ടെലിഗ്രാം എറർ: {e}")

async def check_all_feeds():
    for feed_url in FEED_URLS:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                continue

            for entry in feed.entries[:8]:
                title = getattr(entry, "title", "Special Deal")
                raw_link = getattr(entry, "link", "")
                
                if raw_link in posted_deals:
                    continue

                real_url = extract_direct_url(raw_link)
                final_link, platform = convert_to_affiliate(real_url)

                if final_link:
                    await send_deal_to_telegram(title, final_link, platform)
                    posted_deals.add(raw_link)
                    await asyncio.sleep(6)
        except Exception as e:
            print(f"⚠️ ഫീഡ് എറർ: {e}")

async def run_bot():
    print("🚀 Prime Finder Auto Bot ലൈവായി ആരംഭിച്ചു...")
    
    # കണക്ഷൻ ടെസ്റ്റ് ചെയ്യാനായി ഉടൻ ഒരു സ്ഥിരീകരണ പോസ്റ്റ് ഇടുന്നു
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="🟢 *Prime Finder Bot Online!* \nഏറ്റവും പുതിയ ഓഫറുകൾ ഉടൻ പോസ്റ്റ് ചെയ്യപ്പെടുന്നതാണ്.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"⚠️ ടെസ്റ്റ് മെസ്സേജ് അയക്കാൻ കഴിഞ്ഞില്ല: {e}")

    while True:
        await check_all_feeds()
        await asyncio.sleep(300)  # ഓരോ 5 മിനിറ്റിലും പുതിയ ഓഫറുകൾ പരിശോധിക്കും

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(run_bot())
