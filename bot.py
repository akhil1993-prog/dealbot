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


# --- മൾട്ടി-പ്ലാറ്റ്‌ഫോം കാറ്റഗറി ഡിറ്റക്ഷൻ ---
def detect_category_and_platforms(text):
    text_lower = text.lower()
    numbers = re.findall(r"\d+", text)
    budget = f"under {numbers[0]}" if numbers else ""

    # ഫാഷൻ & വസ്ത്രങ്ങൾ
    if any(
        w in text_lower
        for w in [
            "ഷർട്ട്",
            "shirt",
            "tshirt",
            "pant",
            "ജീൻസ്",
            "jeans",
            "dress",
            "സാരി",
            "saree",
            "കുർത്തി",
            "kurti",
            "ഷൂ",
            "shoe",
            "shoes",
            "sneakers",
            "fashion",
        ]
    ):
        clean_key = (
            re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
            if re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
            else "fashion trends"
        )
        return "fashion", f"{clean_key} {budget}".strip()

    # ബ്യൂട്ടി & സ്കിൻകെയർ
    elif any(
        w in text_lower
        for w in [
            "lipstick",
            "cream",
            "face wash",
            "perfume",
            "makeup",
            "serum",
            "shampoo",
            "beauty",
            "സ്കിൻകെയർ",
        ]
    ):
        clean_key = (
            re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
            if re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
            else "beauty essentials"
        )
        return "beauty", f"{clean_key} {budget}".strip()

    # ഇലക്ട്രോണിക്സ് & ഗാഡ്‌ജെറ്റ്സ്
    elif any(
        w in text_lower
        for w in [
            "ഫോൺ",
            "phone",
            "mobile",
            "5g",
            "വാച്ച്",
            "watch",
            "smartwatch",
            "ഇയർഫോൺ",
            "earbuds",
            "airpods",
            "laptop",
            "ലാപ്‌ടോപ്പ്",
            "tv",
            "ട്രിമ്മർ",
            "trimmer",
            "speaker",
        ]
    ):
        if (
            "phone" in text_lower
            or "mobile" in text_lower
            or "ഫോൺ" in text_lower
        ):
            key = f"5G smartphone {budget}"
        elif "watch" in text_lower or "വാച്ച്" in text_lower:
            key = f"smartwatch {budget}"
        elif (
            "earbud" in text_lower
            or "airpod" in text_lower
            or "ഇയർഫോൺ" in text_lower
        ):
            key = f"wireless earbuds {budget}"
        else:
            clean_key = re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
            key = f"{clean_key} {budget}"
        return "electronics", key.strip()

    else:
        clean_key = re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
        key = clean_key if clean_key else "top deals"
        return "general", f"{key} {budget}".strip()


# --- ഡയറക്റ്റ് സെർച്ച് റൂട്ടിംഗ് (ഹോം പേജ് പ്രോബ്ലം ഒഴിവാക്കുന്നു) ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if user_text == "/start":
        await update.message.reply_text(
            "👋 *Prime Finder All-In-One Shopping Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "Amazon, Flipkart, Myntra, Ajio, Nykaa തുടങ്ങിയ പ്ലാറ്റ്‌ഫോമുകളിലെ കൃത്യമായ ഫലങ്ങൾ ലഭിക്കാൻ സാധനത്തിന്റെ പേര് ഇവിടെ അയക്കൂ!\n\n"
            "ഉദാഹരണം: `5G mobile under 15000`, `running shoes`, `lipstick`, `smart watch`",
            parse_mode="Markdown",
        )
        return

    cat_type, search_keyword = detect_category_and_platforms(user_text)
    encoded_query = urllib.parse.quote_plus(search_keyword)

    # 100% നേരിട്ട് ആപ്പ്/സ്റ്റോർ സെർച്ച് റിസൾട്ടുകൾ ഓപ്പൺ ആകുന്ന ഒറിജിനൽ ലിങ്കുകൾ
    amazon_url = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_url = f"https://www.flipkart.com/search?q={encoded_query}&sort=popularity"
    myntra_url = f"https://www.myntra.com/{encoded_query}"
    ajio_url = f"https://www.ajio.com/search/?text={encoded_query}"
    nykaa_url = f"https://www.nykaa.com/search/result/?q={encoded_query}"

    if cat_type == "fashion":
        links_text = (
            f"🟠 [Amazon Fashion Deals (4★+)]({amazon_url})\n"
            f"🔵 [Flipkart Fashion Offers]({flipkart_url})\n"
            f"🔴 [Myntra Trending Collection]({myntra_url})\n"
            f"🟡 [Ajio Exclusive Fashion]({ajio_url})"
        )
    elif cat_type == "beauty":
        links_text = (
            f"🟠 [Amazon Beauty Deals (4★+)]({amazon_url})\n"
            f"🌸 [Nykaa 100% Genuine Store]({nykaa_url})\n"
            f"🔴 [Myntra Beauty Collection]({myntra_url})"
        )
    elif cat_type == "electronics":
        links_text = (
            f"🟠 [Amazon Top Rated (4★+ Only)]({amazon_url})\n"
            f"🔵 [Flipkart Assured Deals]({flipkart_url})"
        )
    else:
        links_text = (
            f"🟠 [Amazon Verified Deals]({amazon_url})\n"
            f"🔵 [Flipkart Best Sellers]({flipkart_url})\n"
            f"🔴 [Myntra Lifestyle Store]({myntra_url})"
        )

    final_reply = (
        f"🎯 *Prime Verified Multi-Store Results:* \n"
        f"📦 *Product:* _{search_keyword}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ *വിവിധ സ്റ്റോറുകളിൽ നേരിട്ട് പരിശോധിക്കാൻ ക്ലിക്ക് ചെയ്യുക:*\n\n"
        f"{links_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ _100% ഒറിജിനൽ ബ്രാൻഡുകളും ഫാസ്റ്റ് ഡെലിവറിയും!_"
    )

    await update.message.reply_text(
        final_reply, parse_mode="Markdown", disable_web_page_preview=True
    )


# --- ചാനൽ ലൈവ് ഡീലുകൾ (EarnKaro വഴി യഥാർത്ഥ പ്രൊഡക്റ്റ് ലിങ്കുകൾ പോസ്റ്റ് ചെയ്യുന്നു) ---
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

    myn = re.search(r"https?://(?:www\.)?myntra\.com/[^\s\"\'>]+", text_or_url)
    if myn:
        clean = myn.group(0).split("?")[0]
        return (
            f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean}",
            "Myntra",
        )

    return None, None


async def send_deal_to_telegram(bot, title, final_link, platform_name):
    try:
        badges = {
            "Amazon": "🟠 *Amazon Verified Deal*",
            "Flipkart": "🔵 *Flipkart Assured Deal*",
            "Myntra": "🔴 *Myntra Authentic Deal*",
        }
        badge = badges.get(platform_name, "🛍️ *Prime Verified Deal*")
        message_text = (
            f"{badge} ⭐⭐⭐⭐⭐\n\n"
            f"📦 *Product:* {title}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ *ക്വാളിറ്റി & ട്രസ്റ്റ് ഫീച്ചറുകൾ:*\n"
            f"• 🏆 100% Genuine Brand Product\n"
            f"• 🏬 Top Verified Sellers Only\n"
            f"• 🔄 Easy Returns Available\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 *ഓർഡർ ചെയ്യാൻ ലിങ്കിൽ ക്ലിക്ക് ചെയ്യുക:*\n"
            f"👉 [{platform_name}-ൽ നിന്ന് വാങ്ങൂ]({final_link})\n\n"
            f"💡 _മറ്റ് സാധനങ്ങൾ സെർച്ച് ചെയ്യാൻ ബോട്ടിന് പേര് അയക്കുക!_"
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
