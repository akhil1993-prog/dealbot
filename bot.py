import asyncio
from datetime import datetime, timezone, timedelta
import html
import os
import re
import threading
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
import requests

# --- പ്രധാന വിവരങ്ങൾ ---
BOT_TOKEN = "8996059238:AAGW7IbrwajkVTAd9vK-niLqGYWRyQqpdio"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"

# നേരിട്ടുള്ള ഡീൽ ഫീഡുകൾ
FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed",
    "https://indiafreestuff.in/feed"
]

posted_deals = set()
registered_users = set()
last_update_id = 0

IST = timezone(timedelta(hours=5, minutes=30))

# ഒഴിവാക്കേണ്ട ബ്ലോഗ് / അനാവശ്യ വാക്കുകൾ (Article Filter)
IGNORE_WORDS = [
    "review", "how to", "guide", "top 10", "best budget hosting", 
    "meaning than size", "coupon code", "promo code", "hostinger",
    "domain", "server", "web hosting", "tips", "tricks"
]

# --- വെബ് സെർവർ ---
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- ടെലിഗ്രാം മെസ്സേജ് (HTML) ---
def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        print(f"⚠️ മെസ്സേജ് എറർ: {e}")

# --- ടെലിഗ്രാം ഫോട്ടോ ---
def send_telegram_photo(chat_id, photo_url, caption, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=12)
        return resp.status_code == 200
    except Exception:
        return False

# --- മെനു കീബോർഡ് ---
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "🛒 നിത്യോപയോഗ സാധനങ്ങൾ (പലചരക്ക്)"}, {"text": "🧼 ക്ലീനിംഗ് & സോപ്പുകൾ"}],
            [{"text": "☕ ചായപ്പൊടി & പലഹാരങ്ങൾ"}, {"text": "🧴 പേഴ്സണൽ കെയർ & ഷാംപൂ"}],
            [{"text": "📱 മൊബൈൽ & ഇലക്ട്രോണിക്സ്"}, {"text": "🔥 ഇന്നത്തെ വമ്പൻ പ്രൈസ് ഡ്രോപ്പുകൾ"}],
            [{"text": "📉 പ്രൈസ് ട്രാക്കർ (വില ഹിസ്റ്ററി പരിശോധിക്കാൻ)"}]
        ],
        "resize_keyboard": True
    }

def extract_asin(url):
    match = re.search(r'(?:/dp/|/gp/product/|/d/|/ASIN/|/product/)([A-Z0-9]{10})', url)
    return match.group(1) if match else None

def detect_category_and_query(text):
    text_lower = text.lower()
    if any(w in text_lower for w in ["പലചരക്ക്", "വെളിച്ചെണ്ണ", "പഞ്ചസാര", "അരി", "ഓയിൽ", "grocery", "oil", "rice", "sugar"]):
        return "grocery", "grocery daily essentials cooking oil sugar tea", "നിത്യോപയോഗ പലചരക്ക് സാധനങ്ങൾ"
    elif any(w in text_lower for w in ["ക്ലീനിംഗ്", "സോപ്പ്", "വാഷിംഗ്", "soap", "surf", "detergent", "vim", "ariel"]):
        return "cleaning", "washing powder detergent soap liquid vim surf excel", "ക്ലീനിംഗ് & സോപ്പുകൾ"
    elif any(w in text_lower for w in ["ചായ", "കാപ്പി", "ബിസ്ക്കറ്റ്", "tea", "coffee", "biscuit", "snacks"]):
        return "food", "tea powder coffee biscuits snacks cadbury", "ചായപ്പൊടി & ഭക്ഷ്യോൽപ്പന്നങ്ങൾ"
    elif any(w in text_lower for w in ["ഷാംപൂ", "പേസ്റ്റ്", "shampoo", "toothpaste", "care", "dettol"]):
        return "personal_care", "shampoo toothpaste body wash dettol soap", "പേഴ്സണൽ കെയർ ഉൽപ്പന്നങ്ങൾ"
    elif any(w in text_lower for w in ["മൊബൈൽ", "ഫോൺ", "phone", "mobile", "5g"]):
        return "electronics", "5g smartphone electronics", "സ്മാർട്ട്ഫോണുകൾ & ഇലക്ട്രോണിക്സ്"
    elif any(w in text_lower for w in ["ഡ്രോപ്പ്", "പ്രൈസ്", "വമ്പൻ", "loot", "deal"]):
        return "price_drop", "amazon deals 50% to 80% discount", "ഇന്നത്തെ വലിയ പ്രൈസ് ഡ്രോപ്പുകൾ"
    else:
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        return "general", f"{clean} deals".strip(), text

# --- ചാറ്റ് ഉപയോക്താക്കൾക്ക് മറുപടി ---
def process_user_message(message):
    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text", "").strip()

    if not chat_id or not user_text:
        return

    registered_users.add(chat_id)

    if user_text == "/start":
        welcome_text = (
            "🙏 <b>നമസ്കാരം! Prime Finder സേവിംഗ്സ് & പ്രൈസ് ട്രാക്കറിലേക്ക് സ്വാഗതം.</b>\n\n"
            "• നിത്യോപയോഗ സാധനങ്ങൾ വിലക്കുറവിൽ കണ്ടെത്താൻ താഴെയുള്ള മെനു ഉപയോഗിക്കുക.\n"
            "• ഏതെങ്കിലും ഒരു സാധനത്തിന്റെ കഴിഞ്ഞ മാസങ്ങളിലെ ഏറ്റവും കുറഞ്ഞ വില അറിയാൻ <b>ആമസോൺ ലിങ്ക് ഇവിടെ അയക്കുക!</b>"
        )
        send_telegram_message(chat_id, welcome_text, get_main_keyboard())
        return

    if "പ്രൈസ് ട്രാക്കർ" in user_text:
        help_msg = (
            "📉 <b>ആമസോൺ പ്രൈസ് ട്രാക്കർ ഉപയോഗിക്കേണ്ട വിധം:</b>\n\n"
            "1. ആമസോണിൽ നിങ്ങൾ വാങ്ങാൻ ഉദ്ദേശിക്കുന്ന സാധനത്തിന്റെ <b>ലിങ്ക് (Share Link)</b> കോപ്പി ചെയ്യുക.\n"
            "2. ആ ലിങ്ക് ഈ ചാറ്റിലേക്ക് പേസ്റ്റ് ചെയ്ത് അയക്കുക.\n"
            "3. ബോട്ട് ഉടൻ തന്നെ ആ സാധനത്തിന്റെ കഴിഞ്ഞ മാസങ്ങളിലെ ഏറ്റവും കുറഞ്ഞ വില പരിശോധിക്കാനുള്ള വിവരങ്ങൾ നൽകും!"
        )
        send_telegram_message(chat_id, help_msg)
        return

    if "amazon.in" in user_text or "amzn.to" in user_text:
        asin = extract_asin(user_text)
        clean_url = user_text.split('?')[0] if '?' in user_text else user_text
        buy_url = f"{clean_url}?tag={AMAZON_TAG}" if "amazon.in" in clean_url else clean_url

        price_history_url = f"https://pricehistoryapp.com/product/{asin}" if asin else f"https://pricehistoryapp.com/search?q={urllib.parse.quote_plus(user_text)}"

        buttons = {
            "inline_keyboard": [
                [{"text": "📊 മുൻകാല വില പരിശോധിക്കുക (Price History)", "url": price_history_url}],
                [{"text": "🛒 Amazon-ൽ മികച്ച ഓഫറിൽ വാങ്ങുക", "url": buy_url}]
            ]
        }
        tracker_msg = (
            "🔍 <b>ആമസോൺ ഉൽപ്പന്നം വിജയകരമായി ട്രാക്ക് ചെയ്തു!</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>സ്മാർട്ട് ഷോപ്പിംഗ് ടിപ്പ്:</b>\n"
            "ഇന്നത്തെ ഓഫർ വില യഥാർത്ഥത്തിൽ കുറവാണോ എന്ന് ഉറപ്പാക്കാൻ താഴെയുള്ള ബട്ടണിൽ ക്ലിക്ക് ചെയ്ത് <b>Price History Graph</b> പരിശോധിക്കുക.\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        send_telegram_message(chat_id, tracker_msg, buttons)
        return

    cat_type, search_query, display_name = detect_category_and_query(user_text)
    encoded = urllib.parse.quote_plus(search_query)

    amazon_grocery_url = f"https://www.amazon.in/s?k={encoded}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_grocery_url = f"https://www.flipkart.com/search?q={encoded}&sort=popularity"
    amazon_price_drops = f"https://www.amazon.in/deals?tag={AMAZON_TAG}&pct-off=40-"

    buttons = {
        "inline_keyboard": [
            [{"text": "🛒 Amazon-ൽ മികച്ച വിലയ്ക്ക് വാങ്ങുക", "url": amazon_grocery_url}],
            [{"text": "🔵 Flipkart ഓഫറുകൾ കാണുക", "url": flipkart_grocery_url}],
            [{"text": "🔥 40% മുതൽ 80% വരെ പ്രൈസ് ഡ്രോപ്പുകൾ", "url": amazon_price_drops}]
        ]
    }

    reply_msg = (
        f"✅ <b>{html.escape(display_name)} കണ്ടെത്താൻ സാധിച്ചു!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>പ്രത്യേകതകൾ:</b>\n"
        f"• കടകളിലേതിനേക്കാൾ വലിയ വിലക്കുറവ്\n"
        f"• 100% ഒറിജിനൽ വിശ്വസനീയ ബ്രാൻഡുകൾ\n"
        f"• നേരിട്ട് വീട്ടിലെത്തിക്കുന്ന സർവീസ്\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 <b>വില പരിശോധിക്കാനും വാങ്ങാനും താഴെ ക്ലിക്ക് ചെയ്യുക:</b>"
    )
    send_telegram_message(chat_id, reply_msg, buttons)

# --- ഡീൽ എക്സ്ട്രാക്ഷൻ & സ്മാർട്ട് ഫിൽട്ടറിംഗ് ---
def extract_deal_info(entry):
    raw_title = getattr(entry, 'title', '')
    clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
    clean_title = html.unescape(clean_title)

    content = f"{clean_title} {getattr(entry, 'summary', '')}".lower()

    # 1. ബ്ലോഗ് / ആർട്ടിക്കിളുകൾ ഒഴിവാക്കുന്നു
    if any(bad_word in content for bad_word in IGNORE_WORDS):
        return None, None, None, None, None, None, None

    # 2. വിലയും ഡിസ്കൗണ്ടും കണ്ടെത്തുന്നു
    prices = [int(p.replace(',', '')) for p in re.findall(r'(?:Rs\.?|INR|₹)\s?(\d+[\d,]*)', content, re.IGNORECASE)]
    discount_match = re.search(r'(\d+)%\s*off', content, re.IGNORECASE)

    # വിലയില്ലാത്ത വെറും ആർട്ടിക്കിളുകൾ പൂർണ്ണമായി ഒഴിവാക്കുന്നു
    if not prices or prices[0] == 0:
        return None, None, None, None, None, None, None

    deal_price_num = prices[0]
    mrp_num = prices[1] if len(prices) > 1 else 0

    deal_price = f"₹{deal_price_num}"
    mrp_price = f"<s>₹{mrp_num}</s>" if mrp_num > deal_price_num else ""

    savings_text = ""
    if mrp_num > deal_price_num:
        savings_text = f"💵 നേരിട്ടുള്ള ലാഭം: ₹{mrp_num - deal_price_num}"

    discount = f"({discount_match.group(1)}% OFF)" if discount_match else ""

    # ഇമേജ് കണ്ടെത്തൽ
    image_url = None
    if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
        image_url = entry.media_content[0].get('url')
    if not image_url and hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
        image_url = entry.enclosures[0].get('href')
    if not image_url:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', getattr(entry, 'summary', ''))
        if img_match:
            image_url = img_match.group(1)

    # ആമസോൺ ലിങ്ക് നിർമ്മാണം
    search_words = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
    short_search = " ".join(search_words.split()[:4])
    encoded_query = urllib.parse.quote_plus(short_search)
    final_link = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"

    return clean_title, final_link, image_url, deal_price, mrp_price, discount, savings_text

# --- ചാനൽ പോസ്റ്റിംഗ് ---
def post_deal_to_channel(title, final_link, image_url, deal_price, mrp_price, discount, savings_text):
    safe_title = html.escape(title)
    caption = (
        f"🔥 <b>വമ്പൻ വിലക്കുറവ് (PRICE DROP ALERT)!</b>\n\n"
        f"📦 <b>ഉൽപ്പന്നം:</b> {safe_title}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>ഇന്നത്തെ ഓഫർ വില:</b> <b>{deal_price}</b> {mrp_price} {discount}\n"
    )
    if savings_text:
        caption += f"🎉 <b>{savings_text}</b>\n"

    caption += (
        f"🛡️ 100% ഒറിജിനൽ ഗ്യാരണ്ടി | ടോപ്പ് റേറ്റിംഗ്\n"
        f"🚚 ഓർഡർ ചെയ്താൽ ഉടൻ വീട്ടിലെത്തും\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    buttons = {
        "inline_keyboard": [
            [{"text": "🛒 ഇപ്പോൾ തന്നെ ഓർഡർ ചെയ്യുക", "url": final_link}]
        ]
    }

    if image_url:
        if send_telegram_photo(CHANNEL_ID, image_url, caption, buttons):
            return

    send_telegram_message(CHANNEL_ID, caption, buttons)

def check_feeds_and_post():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for url in FEED_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:5]:
                    title, final_link, image_url, deal_price, mrp_price, discount, savings_text = extract_deal_info(entry)
                    if final_link and final_link not in posted_deals:
                        post_deal_to_channel(title, final_link, image_url, deal_price, mrp_price, discount, savings_text)
                        posted_deals.add(final_link)
        except Exception as e:
            print(f"⚠️ ഫീഡ് എറർ: {e}")

async def channel_deals_worker():
    await asyncio.sleep(2)
    while True:
        try:
            check_feeds_and_post()
        except Exception as e:
            print(f"⚠️ വർക്കർ എറർ: {e}")
        await asyncio.sleep(120)

async def poll_telegram_updates():
    global last_update_id
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=10"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("result", []):
                    last_update_id = item["update_id"]
                    if "message" in item:
                        process_user_message(item["message"])
        except Exception:
            await asyncio.sleep(2)
        await asyncio.sleep(0.5)

async def main():
    asyncio.create_task(channel_deals_worker())
    await poll_telegram_updates()

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    asyncio.run(main())
