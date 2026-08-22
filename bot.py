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

# മുൻനിര വിശ്വസനീയ ബ്രാൻഡുകൾ
TOP_BRANDS = [
    "samsung", "apple", "iphone", "oneplus", "sony", "boat", "noise", "puma", 
    "nike", "adidas", "realme", "redmi", "xiaomi", "lenovo", "hp", "dell", 
    "asus", "philips", "lg", "whirlpool", "logitech", "fastrack", "titan", 
    "casio", "fossil", "boult", "fire-boltt", "zebronics", "sandisk", "bata", 
    "woodland", "levi", "roadster", "us polo", "allen solly", "mamaearth", 
    "beardo", "nivea", "dove", "ponds"
]

SPAM_KEYWORDS = ["survey", "referral", "free recharge", "loot bug", "giveaway", "spin", "coin"]

posted_deals = set()
bot = Bot(token=BOT_TOKEN)

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

def is_trusted_deal(title):
    title_lower = title.lower()
    if any(spam in title_lower for spam in SPAM_KEYWORDS):
        return False
    if any(brand in title_lower for brand in TOP_BRANDS):
        return True
    if "% off" in title_lower or "flat" in title_lower or "₹" in title or "rs." in title_lower:
        return True
    return False

def detect_and_convert_link(text_or_url):
    if not text_or_url:
        return None, None
    amazon_match = re.search(r"https?://(?:www\.)?amazon\.in/[^\s\"\'>]+", text_or_url)
    if amazon_match:
        clean_url = amazon_match.group(0).split('?')[0]
        return f"{clean_url}?tag={AMAZON_TAG}", "Amazon"

    flipkart_match = re.search(r"https?://(?:www\.)?flipkart\.com/[^\s\"\'>]+", text_or_url)
    if flipkart_match:
        clean_url = flipkart_match.group(0).split('?')[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", "Flipkart"

    myntra_match = re.search(r"https?://(?:www\.)?myntra\.com/[^\s\"\'>]+", text_or_url)
    if myntra_match:
        clean_url = myntra_match.group(0).split('?')[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", "Myntra"

    return None, None

async def send_deal_to_telegram(title, final_link, platform_name):
    """കസ്റ്റമർ സംതൃപ്തി ഉറപ്പാക്കുന്ന സവിശേഷതകളോടെ പോസ്റ്റ് ചെയ്യുന്നു"""
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
        print(f"✅ സവിശേഷതകളോടെ പോസ്റ്റ് ചെയ്തു ({platform_name}): {title[:30]}...")
    except Exception as e:
        print(f"⚠️ പോസ്റ്റിംഗ് എറർ: {e}")

async def check_all_deals():
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        if not feed.entries:
            return

        for entry in feed.entries[:10]:
            title = getattr(entry, "title", "Special Verified Deal")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")

            if not is_trusted_deal(title):
                continue

            combined_text = f"{link} {summary}"
            final_link, platform = detect_and_convert_link(combined_text)

            if final_link and final_link not in posted_deals:
                await send_deal_to_telegram(title, final_link, platform)
                posted_deals.add(final_link)
                await asyncio.sleep(6)
    except Exception as e:
        print(f"⚠️ ഫീഡ് എറർ: {e}")

async def run_bot():
    print("🚀 Prime Finder High-Quality Bot ക്ലൗഡിൽ റൺ ആകുന്നു...")
    while True:
        await check_all_deals()
        await asyncio.sleep(600)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(run_bot())
