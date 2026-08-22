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

# മൾട്ടിപ്പിൾ ഡീൽ ഫീഡുകൾ
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

def get_real_url_and_platform(text_or_url):
    if not text_or_url:
        return None, None
    
    # ആമസോൺ ലിങ്കുകൾ
    amz = re.search(r"https?://(?:www\.)?amazon\.in/[^\s\"\'>]+", text_or_url)
    if amz:
        clean = amz.group(0).split('?')[0]
        return f"{clean}?tag={AMAZON_TAG}", "Amazon"

    # ഫ്ലിപ്കാർട്ട് ലിങ്കുകൾ
    fk = re.search(r"https?://(?:www\.)?flipkart\.com/[^\s\"\'>]+", text_or_url)
    if fk:
        clean = fk.group(0).split('?')[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Flipkart"

    # മിന്ത്ര ലിങ്കുകൾ
    myn = re.search(r"https?://(?:www\.)?myntra\.com/[^\s\"\'>]+", text_or_url)
    if myn:
        clean = myn.group(0).split('?')[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}", "Myntra"

    return None, None

async def send_deal_to_telegram(title, final_link, platform_name):
    try:
        platform_badges = {
            "Amazon": "🟠 *Amazon Verified Deal*",
            "Flipkart": "🔵 *Flipkart Assured Deal*",
            "Myntra": "🔴 *Myntra Authentic Deal*"
        }
        badge = platform_badges.get(platform_name, "🛍️ *Prime Verified Deal*")
        
        message_text = (
            f"{badge} ⭐⭐⭐⭐⭐\n\n"
            f"📦 *Product:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ *Quality & Trust Features:*\n"
            f"• 🏆 *100% Genuine & Authentic Brand*\n"
            f"• 🏬 *Top-Rated & Verified Sellers Only*\n"
            f"• 🔄 *Easy Replacement / Return Available*\n"
            f"• 🚚 *Fast Delivery & Secure Packaging*\n"
            f"• 💳 *COD & Secure Online Payment Supported*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 *വാങ്ങാൻ താഴെ കാണുന്ന ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് ഓർഡർ ചെയ്യൂ]({final_link})\n\n"
            f"⚡ _ഓഫർ സ്റ്റോക്ക് തീരുന്നതിന് മുൻപ് വേഗത്തിൽ വാങ്ങൂ!_"
        )
        
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        print(f"✅ പോസ്റ്റ് ചെയ്തു ({platform_name}): {title[:30]}...")
    except Exception as e:
        print(f"⚠️ പോസ്റ്റിംഗ് എറർ: {e}")

async def check_all_feeds():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for url in FEED_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            
            for entry in feed.entries[:10]:
                title = getattr(entry, "title", "Special Deal")
                link = getattr(entry, "link", "")
                summary = getattr(entry, "summary", "")
                
                content = f"{link} {summary}"
                final_link, platform = get_real_url_and_platform(content)
                
                if final_link and final_link not in posted_deals:
                    await send_deal_to_telegram(title, final_link, platform)
                    posted_deals.add(final_link)
                    await asyncio.sleep(6)
        except Exception as e:
            print(f"⚠️ ഫീഡ് ചെക്കിംഗ് എറർ ({url}): {e}")

async def run_bot():
    print("🚀 Prime Finder High-Quality Bot ലൈവ് ആയി...")
    
    # കോഡ് ഡിപ്ലോയ് ആയയുടൻ ഒരു ലൈവ് ടെസ്റ്റ് ഓഫർ ചാനലിൽ പോസ്റ്റ് ചെയ്യും
    test_title = "SanDisk Ultra 128GB MicroSD Card (Class 10)"
    test_link = f"https://www.amazon.in/dp/B08L5HMJVW?tag={AMAZON_TAG}"
    await send_deal_to_telegram(test_title, test_link, "Amazon")
    
    while True:
        await check_all_feeds()
        await asyncio.sleep(300) # ഓരോ 5 മിനിറ്റിലും പരിശോധിക്കും

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(run_bot())
