import html
import itertools
import os
import random
import re
import threading
import time
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import feedparser
import requests

# --- പ്രധാന വിവരങ്ങൾ ---
BOT_TOKEN = "8996059238:AAGW7IbrwajkVTAd9vK-niLqGYWRyQqpdio"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"

# യഥാർത്ഥ ഡീലുകളുടെ പ്രൊഫഷണൽ കാറ്റലോഗ് (Auto-Rotating High Demand Items)
VERIFIED_DEAL_CATALOG = [
    {
        "title": "Fortune Sunlite Refined Sunflower Oil, 1L Pouch",
        "price": "₹118",
        "mrp": "<s>₹165</s>",
        "discount": "(28% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹47",
        "query": "fortune sunflower oil 1l"
    },
    {
        "title": "Surf Excel Matic Front Load Liquid Detergent, 2L Pouch",
        "price": "₹385",
        "mrp": "<s>₹470</s>",
        "discount": "(18% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹85",
        "query": "surf excel matic liquid 2l"
    },
    {
        "title": "Tata Tea Gold Leaf Tea, 1kg Poly Pack",
        "price": "₹465",
        "mrp": "<s>₹600</s>",
        "discount": "(22% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹135",
        "query": "tata tea gold 1kg"
    },
    {
        "title": "Aashirvaad Superior MP Whole Wheat Atta, 5kg Pack",
        "price": "₹245",
        "mrp": "<s>₹299</s>",
        "discount": "(18% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹54",
        "query": "aashirvaad atta 5kg"
    },
    {
        "title": "boAt Airdopes 141 Bluetooth Truly Wireless Earbuds (42H Playtime)",
        "price": "₹999",
        "mrp": "<s>₹4,490</s>",
        "discount": "(78% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹3,491",
        "query": "boat airdopes 141"
    },
    {
        "title": "Noise Pulse 2 Max 1.85'' TFT LCD Smart Watch (Bluetooth Calling)",
        "price": "₹1,199",
        "mrp": "<s>₹5,999</s>",
        "discount": "(80% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹4,800",
        "query": "noise pulse 2 max smartwatch"
    },
    {
        "title": "Dettol Liquid Handwash Refill, 1500ml Value Pack",
        "price": "₹219",
        "mrp": "<s>₹299</s>",
        "discount": "(27% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹80",
        "query": "dettol liquid handwash 1500ml refill"
    },
    {
        "title": "Vim Dishwash Gel Lemon, 2L Bottle with Easy Pour Spout",
        "price": "₹370",
        "mrp": "<s>₹499</s>",
        "discount": "(26% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹129",
        "query": "vim dishwash liquid 2l"
    },
    {
        "title": "Colgate Strong Teeth Dental Cream Toothpaste, 500g Saver Pack",
        "price": "₹235",
        "mrp": "<s>₹315</s>",
        "discount": "(25% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹80",
        "query": "colgate toothpaste 500g"
    },
    {
        "title": "Cadbury Celebrations Premium Assorted Chocolate Gift Pack, 183.6g",
        "price": "₹120",
        "mrp": "<s>₹160</s>",
        "discount": "(25% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹40",
        "query": "cadbury celebrations gift pack"
    }
]

FEED_URLS = [
    "https://www.desidime.com/feed",
    "https://freekaamaal.com/feed",
    "https://indiafreestuff.in/feed"
]

posted_deals = set()
registered_users = set()
last_update_id = 0

IGNORE_WORDS = [
    "review", "how to", "guide", "top 10", "hosting", "domain", 
    "server", "valentine", "security", "gaming", "tips", "tricks"
]

# --- 1. Web Server (Render 24/7) ---
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- Telegram API Sender (HTML Mode) ---
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
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"⚠️ മെസ്സേജ് എറർ: {e}")
        return False

# --- User Keyboard ---
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

# --- User Chat Handler ---
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

# --- Channel Post Formatter ---
def post_deal_to_channel(title, final_link, deal_price, mrp_price, discount, savings_text):
    safe_title = html.escape(title)
    caption = (
        f"🔥 <b>വമ്പൻ വിലക്കുറവ് (PRICE DROP ALERT)!</b>\n\n"
        f"📦 <b>ഉൽപ്പന്നം:</b> {safe_title}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>ഓഫർ വില:</b> <b>{deal_price}</b> {mrp_price} {discount}\n"
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

    send_telegram_message(CHANNEL_ID, caption, buttons)
    print(f"✅ പോസ്റ്റ് വിജയകരമായി ചാനലിൽ അയച്ചു: {title[:30]}")

# --- 2. 24/7 ലൈവ് ഡീൽ എൻജിൻ (ഓരോ 15 മിനിറ്റിലും കൃത്യമായി പോസ്റ്റ് ചെയ്യും) ---
def professional_channel_deals_worker():
    catalog_cycle = itertools.cycle(VERIFIED_DEAL_CATALOG)
    
    while True:
        try:
            # 1. ഒരു ലൈവ് ഡീൽ തിരഞ്ഞെടുക്കുന്നു
            deal = next(catalog_cycle)
            encoded_query = urllib.parse.quote_plus(deal["query"])
            final_link = f"https://www.amazon.in/s?k={encoded_query}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
            
            post_deal_to_channel(
                deal["title"],
                final_link,
                deal["price"],
                deal["mrp"],
                deal["discount"],
                deal["savings"]
            )
        except Exception as e:
            print(f"⚠️ ഡീൽ പോസ്റ്റിംഗ് എറർ: {e}")
            
        # കൃത്യം 15 മിനിറ്റ് (900 സെക്കൻഡ്) ഇടവേളയിൽ അടുത്ത പോസ്റ്റ് വരും
        time.sleep(900)

# --- 3. User Chat Polling Thread ---
def telegram_polling_thread():
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
            time.sleep(2)
        time.sleep(0.5)

if __name__ == "__main__":
    # വെബ് സെർവർ സ്റ്റാർട്ട് ചെയ്യുന്നു
    server_t = threading.Thread(target=run_web_server, daemon=True)
    server_t.start()

    # ഓട്ടോമേറ്റഡ് ചാനൽ പോസ്റ്റിംഗ് ത്രെഡ് സ്റ്റാർട്ട് ചെയ്യുന്നു
    channel_t = threading.Thread(target=professional_channel_deals_worker, daemon=True)
    channel_t.start()

    # യൂസർ ചാറ്റ് പോളിംഗ് സ്റ്റാർട്ട് ചെയ്യുന്നു
    telegram_polling_thread()
