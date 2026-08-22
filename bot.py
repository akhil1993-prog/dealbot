import asyncio
import re
import feedparser
from telegram import Bot

BOT_TOKEN = "8996059238:AAEkf-zvMgRqUFG0Q-oJ39alhTcOfrldwuA"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"

RSS_FEED_URL = "https://www.desidime.com/feed"

posted_deals = set()
bot = Bot(token=BOT_TOKEN)


def detect_and_convert_link(text_or_url):
    """വിവിധ പ്ലാറ്റ്‌ഫോമുകൾ കണ്ടെത്തി അഫിലിയേറ്റ് ലിങ്കിലേക്ക് മാറ്റുന്നു"""
    if not text_or_url:
        return None, None

    # 1. Amazon
    amazon_match = re.search(
        r"https?://(?:www\.)?amazon\.in/[^\s\"\'>]+", text_or_url
    )
    if amazon_match:
        clean_url = amazon_match.group(0).split("?")[0]
        return f"{clean_url}?tag={AMAZON_TAG}", "Amazon"

    # 2. Flipkart
    flipkart_match = re.search(
        r"https?://(?:www\.)?flipkart\.com/[^\s\"\'>]+", text_or_url
    )
    if flipkart_match:
        clean_url = flipkart_match.group(0).split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", (
            "Flipkart"
        )

    # 3. Myntra
    myntra_match = re.search(
        r"https?://(?:www\.)?myntra\.com/[^\s\"\'>]+", text_or_url
    )
    if myntra_match:
        clean_url = myntra_match.group(0).split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", (
            "Myntra"
        )

    # 4. Ajio
    ajio_match = re.search(
        r"https?://(?:www\.)?ajio\.com/[^\s\"\'>]+", text_or_url
    )
    if ajio_match:
        clean_url = ajio_match.group(0).split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", (
            "Ajio"
        )

    # 5. Nykaa
    nykaa_match = re.search(
        r"https?://(?:www\.)?nykaa\.com/[^\s\"\'>]+", text_or_url
    )
    if nykaa_match:
        clean_url = nykaa_match.group(0).split("?")[0]
        return f"https://earnkaro.com?r={EARNKARO_USER_ID}&link={clean_url}", (
            "Nykaa"
        )

    return None, None


async def send_deal_to_telegram(title, final_link, platform_name):
    """ടെലിഗ്രാം ചാനലിലേക്ക് ഭംഗിയായി ഫോർമാറ്റ് ചെയ്ത് അയക്കുന്നു"""
    try:
        # പ്ലാറ്റ്‌ഫോം അനുസരിച്ചുള്ള ബാഡ്ജുകൾ
        badges = {
            "Amazon": "🟠 *Amazon Deal*",
            "Flipkart": "🔵 *Flipkart Deal*",
            "Myntra": "🔴 *Myntra Fashion Deal*",
            "Ajio": "🟡 *Ajio Offer*",
            "Nykaa": "🌸 *Nykaa Beauty Deal*",
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

        for entry in feed.entries[:15]:
            title = getattr(entry, "title", "Special Deal")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")

            combined_text = f"{link} {summary}"
            final_link, platform = detect_and_convert_link(combined_text)

            if final_link and final_link not in posted_deals:
                await send_deal_to_telegram(title, final_link, platform)
                posted_deals.add(final_link)
                await asyncio.sleep(5)  # 5 സെക്കൻഡ് ഗ്യാപ്പ്
    except Exception as e:
        print(f"⚠️ ഫീഡ് എറർ: {e}")


async def main():
    print("🚀 Prime Finder Multi-Store Bot വിജയകരമായി ആരംഭിച്ചു...")
    while True:
        await check_all_deals()
        await asyncio.sleep(1800)  # ഓരോ 30 മിനിറ്റിലും പരിശോധിക്കും


if __name__ == "__main__":
    asyncio.run(main())