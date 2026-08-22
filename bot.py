import asyncio
import datetime
import os
import re
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
import google.generativeai as genai
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
GEMINI_API_KEY = (
    "AQ.Ab8RN6IY541GeWsvH8LYPBo0mcQHMvpNIir9Ji2SBReyEH8F-Q"  # നിങ്ങളുടെ Gemini Key
)

# Gemini AI കോൺഫിഗറേഷൻ
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

FEED_URLS = ["https://www.desidime.com/feed", "https://freekaamaal.com/feed"]

posted_deals = set()


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()


# --- 1. AI ഷോപ്പിംഗ് അസിസ്റ്റന്റ് ചാറ്റ്ബോട്ട് ---
async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if user_text == "/start":
        await update.message.reply_text(
            "👋 *Prime Finder AI Shopping Assistant-ലേക്ക് സ്വാഗതം!*\n\n"
            "ഷോപ്പിംഗുമായി ബന്ധപ്പെട്ട എന്ത് സംശയങ്ങളും എന്നോട് ചോദിക്കാം. (ഉദാഹരണത്തിന്: *'15000 രൂപയിൽ താഴെ നല്ല ക്യാമറ ഫോൺ ഏതാണ്?'*, *'ബെസ്റ്റ് ബ്ലൂടൂത്ത് സ്പീക്കർ സജസ്റ്റ് ചെയ്യാമോ?'*).\n\n"
            "നിങ്ങൾക്കായി മികച്ച ഉൽപ്പന്നങ്ങൾ ഞാൻ നിർദ്ദേശിക്കാം!",
            parse_mode="Markdown",
        )
        return

    # ഉപഭോക്താവിന് ടൈപ്പിംഗ് സ്റ്റാറ്റസ് കാണിക്കുന്നു
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        # AI പ്രോംപ്റ്റ്
        prompt = (
            f"You are Prime Finder, an expert, friendly AI shopping assistant for Kerala users. "
            f"The user asks: '{user_text}'. "
            f"Reply in a polite, helpful way (use Malayalam or Manglish if the user asks in Malayalam/Manglish, otherwise English). "
            f"Recommend 1 or 2 top-quality, best-rated products for their need in 2-3 short bullet points. "
            f"At the very end, extract the exact search keyword for this product on a new line starting with 'KEYWORD:' so I can create affiliate links."
        )

        response = ai_model.generate_content(prompt)
        ai_reply = response.text

        # കീവേഡ് എക്സ്ട്രാക്റ്റ് ചെയ്യുന്നു
        search_keyword = user_text
        if "KEYWORD:" in ai_reply:
            parts = ai_reply.split("KEYWORD:")
            main_answer = parts[0].strip()
            search_keyword = parts[1].strip()
        else:
            main_answer = ai_reply.strip()

        encoded_query = urllib.parse.quote_plus(search_keyword)
        amazon_url = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
        flipkart_url = f"https://earnkaro.com?r={EARNKARO_USER_ID}&link=https://www.flipkart.com/search?q={encoded_query}"

        final_message = (
            f"{main_answer}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍️ *Verified Buying Links (4★+ Rating):*\n"
            f"👉 [Amazon-ൽ നിന്ന് വാങ്ങൂ]({amazon_url})\n"
            f"👉 [Flipkart-ൽ നിന്ന് വാങ്ങൂ]({flipkart_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ _100% Genuine Brand Warranty & Replacement Available!_"
        )

        await update.message.reply_text(
            final_message, parse_mode="Markdown", disable_web_page_preview=True
        )

    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        # AI എറർ വന്നാൽ ഡയറക്റ്റ് സ്മാർട്ട് സെർച്ച് പ്രവർത്തിക്കും
        encoded_query = urllib.parse.quote_plus(user_text)
        amazon_url = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
        await update.message.reply_text(
            f"🔍 *{user_text}* തിരഞ്ഞതിനുള്ള ഫലങ്ങൾ:\n👉 [Amazon Verified Deals]({amazon_url})",
            parse_mode="Markdown",
        )


# --- 2. ഷെഡ്യൂൾഡ് ഓട്ടോ-പോസ്റ്റിംഗ് (ബയിംഗ് ഗൈഡ് & ഗാഡ്‌ജെറ്റ്സ്) ---
async def scheduled_curated_posts(bot):
    while True:
        now = datetime.datetime.now()
        day = now.weekday()
        try:
            if day in [0, 2]:
                guide_url = f"https://www.amazon.in/s?k=boat+airdopes&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
                msg = (
                    "🎧 *Weekly Top Picks: Best Earbuds Under ₹1,500* ⭐⭐⭐⭐⭐\n\n"
                    "മികച്ച സൗണ്ട് ക്വാളിറ്റിയും ഉയർന്ന ബാറ്ററിയുമുള്ള ചോയ്‌സുകൾ:\n"
                    f"👉 [4★+ മികച്ച ഇയർബഡ്സ് കാണുക]({guide_url})\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ _100% Original Brand Warranty!_"
                )
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
        except Exception as e:
            print(f"⚠️ ഷെഡ്യൂൾഡ് എറർ: {e}")
        await asyncio.sleep(86400)


# --- 3. ചാനൽ ലൈവ് ഡീലുകൾ ---
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
            f"🤖 _എന്ത് സംശയങ്ങൾക്കും ബോട്ടിനോട് നേരിട്ട് ചോദിക്കൂ!_"
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
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_ai_chat)
    )
    application.add_handler(CommandHandler("start", handle_ai_chat))

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
