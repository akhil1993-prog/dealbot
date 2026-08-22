import html
import io
import itertools
import os
import re
import threading
import time
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import requests

# --- പ്രധാന വിവരങ്ങൾ ---
BOT_TOKEN = "8996059238:AAGW7IbrwajkVTAd9vK-niLqGYWRyQqpdio"
CHANNEL_ID = "@primefinder_in"
AMAZON_TAG = "primefinder03-21"
EARNKARO_USER_ID = "5561136"

# 100% കൃത്യമായ തത്സമയ ഉൽപ്പന്നങ്ങളുടെ കാറ്റലോഗ്
VERIFIED_DEALS = [
    {
        "title": "Surf Excel Matic Top Load Liquid Detergent Pouch, 2L",
        "price": "₹385",
        "mrp": "<s>₹470</s>",
        "discount": "(18% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹85",
        "direct_url": f"https://www.amazon.in/dp/B084G47746?tag={AMAZON_TAG}",
        "img_url": "https://m.media-amazon.com/images/I/61Nl5zGZ3IL._SX679_.jpg"
    },
    {
        "title": "Tata Tea Gold Leaf Tea, 1kg Poly Pack with Long Leaves",
        "price": "₹465",
        "mrp": "<s>₹600</s>",
        "discount": "(22% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹135",
        "direct_url": f"https://www.amazon.in/dp/B07DYP6QNW?tag={AMAZON_TAG}",
        "img_url": "https://m.media-amazon.com/images/I/61tPqT5Q+sL._SX679_.jpg"
    },
    {
        "title": "boAt Airdopes 141 Bluetooth Truly Wireless Earbuds (42H Playtime)",
        "price": "₹999",
        "mrp": "<s>₹4,490</s>",
        "discount": "(78% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹3,491",
        "direct_url": f"https://www.amazon.in/dp/B09N3ZNHTY?tag={AMAZON_TAG}",
        "img_url": "https://m.media-amazon.com/images/I/51HBom8xz7L._SX679_.jpg"
    },
    {
        "title": "Noise Pulse 2 Max 1.85'' TFT LCD Smart Watch (Bluetooth Calling)",
        "price": "₹1,199",
        "mrp": "<s>₹5,999</s>",
        "discount": "(80% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹4,800",
        "direct_url": f"https://www.amazon.in/dp/B0B6BNMVL9?tag={AMAZON_TAG}",
        "img_url": "https://m.media-amazon.com/images/I/61SSVxTSs3L._SX679_.jpg"
    },
    {
        "title": "Cadbury Celebrations Premium Assorted Chocolate Gift Pack, 183.6g",
        "price": "₹120",
        "mrp": "<s>₹160</s>",
        "discount": "(25% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹40",
        "direct_url": f"https://www.amazon.in/dp/B00TX84620?tag={AMAZON_TAG}",
        "img_url": "https://m.media-amazon.com/images/I/71N7-w4u76L._SX679_.jpg"
    },
    {
        "title": "Dettol Liquid Handwash Refill, 1500ml Value Saver Pack",
        "price": "₹219",
        "mrp": "<s>₹299</s>",
        "discount": "(27% OFF)",
        "savings": "💵 നേരിട്ടുള്ള ലാഭം: ₹80",
        "direct_url": f"https://www.amazon.in/dp/B07P41S8X1?tag={AMAZON_TAG}",
        "img_url": "https://m.media-amazon.com/images/I/61-M0gYxTfL._SX679_.jpg"
    }
]

registered_users = set()
last_update_id = 0

# --- 1. Render 24/7 വെബ് സെർവർ ---
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- ടെലിഗ്രാം ഫോട്ടോ മെസ്സേജ് ---
def send_telegram_photo(chat_id, photo_url, caption, reply_markup=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        img_resp = requests.get(photo_url, headers=headers, timeout=12)
        if img_resp.status_code == 200:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            files = {'photo': ('product.jpg', io.BytesIO(img_resp.content), 'image/jpeg')}
            data = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            if reply_markup:
                data['reply_markup'] = str(reply_markup).replace("'", '"')
            
            r = requests.post(url, data=data, files=files, timeout=15)
            return r.status_code == 200
    except Exception as e:
        print(f"⚠️ ഫോട്ടോ എറർ: {e}")
    return False

# --- ടെലിഗ്രാം ടെക്സ്റ്റ് മെസ്സേജ് ---
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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ മെസ്സേജ് എറർ: {e}")

# --- സമ്പൂർണ്ണ പൊതുജന സേവന കീബോർഡ് ---
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "🛒 പലചരക്ക് വില താരതമ്യം"}, {"text": "⚡ ₹1, ₹9 & ₹49 ബഡ്ജറ്റ് ഡീലുകൾ"}],
            [{"text": "📚 വിദ്യാർത്ഥി സഹായി (സ്റ്റേഷനറി)"}, {"text": "🌴 കേരള സീസണൽ ഓഫറുകൾ"}],
            [{"text": "💳 റീചാർജ് & ബിൽ ക്യാഷ്ബാക്ക്"}, {"text": "📉 ലൈവ് പ്രൈസ് ട്രാക്കർ"}]
        ],
        "resize_keyboard": True
    }

def extract_asin(url):
    match = re.search(r'(?:/dp/|/gp/product/|/d/|/ASIN/|/product/)([A-Z0-9]{10})', url)
    return match.group(1) if match else None

# --- ചാറ്റ് മെസ്സേജ് പ്രോസസ്സിംഗ് ---
def process_user_message(message):
    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text", "").strip()

    if not chat_id or not user_text:
        return

    registered_users.add(chat_id)

    # 1. Start കമാൻഡ്
    if user_text == "/start":
        welcome_text = (
            "🙏 <b>നമസ്കാരം! Prime Finder ജനസേവന സേവിംഗ്സ് അസിസ്റ്റന്റിലേക്ക് സ്വാഗതം.</b>\n\n"
            "സാധാരണക്കാർക്ക് നിത്യജീവിതത്തിൽ പണം ലാഭിക്കാൻ ആവശ്യമായ എല്ലാ സേവനങ്ങളും താഴെ ലഭ്യമാണ്:\n\n"
            "• പലചരക്ക് സാധനങ്ങളുടെ വില താരതമ്യം\n"
            "• ₹1, ₹9 പോക്കറ്റ് ഡീലുകൾ\n"
            "• പഠന സാമഗ്രികളുടെ വിലക്കുറവ്\n"
            "• റീചാർജ് & ബിൽ പേയ്‌മെന്റ് ഓഫറുകൾ\n"
            "• സാധനങ്ങളുടെ യഥാർത്ഥ വില അറിയാൻ ആമസോൺ ലിങ്ക് അയക്കുക!"
        )
        send_telegram_message(chat_id, welcome_text, get_main_keyboard())
        return

    # 2. പലചരക്ക് വില താരതമ്യം
    if "പലചരക്ക് വില താരതമ്യം" in user_text:
        msg = (
            "🛒 <b>പലചരക്ക് സാധനങ്ങൾ വില താരതമ്യം ചെയ്ത് വാങ്ങാം:</b>\n\n"
            "അരി, എണ്ണ, പഞ്ചസാര, സോപ്പ് തുടങ്ങിയവയ്ക്ക് Amazon Fresh, Flipkart Grocery എന്നിവയിലെ ഇന്നത്തെ ഏറ്റവും കുറഞ്ഞ വിലകൾ ചുവടെ പരിശോധിക്കുക 👇"
        )
        buttons = {
            "inline_keyboard": [
                [{"text": "🟠 Amazon Fresh സൂപ്പർ ഓഫറുകൾ", "url": f"https://www.amazon.in/alm/storefront?almBrandId=ctnow&tag={AMAZON_TAG}"}],
                [{"text": "🔵 Flipkart Grocery ഡീലുകൾ", "url": "https://www.flipkart.com/grocery-supermart-store"}]
            ]
        }
        send_telegram_message(chat_id, msg, buttons)
        return

    # 3. ₹1, ₹9 & ₹49 ബഡ്ജറ്റ് ഡീലുകൾ
    if "ബഡ്ജറ്റ് ഡീലുകൾ" in user_text:
        msg = (
            "⚡ <b>പോക്കറ്റ് ഫ്രണ്ട്‌ലി ബഡ്ജറ്റ് ഡീലുകൾ:</b>\n\n"
            "സാധാരണക്കാർക്ക് ₹1, ₹9, ₹49, ₹99 നിരക്കിൽ ദിവസേന ലഭിക്കുന്ന ചെറിയ വീട്ടുസാധനങ്ങളുടെയും ഓഫറുകളുടെയും തത്സമയ ലിങ്ക് താഴെ നൽകുന്നു 👇"
        )
        buttons = {
            "inline_keyboard": [
                [{"text": "🔥 ₹99-ൽ താഴെയുള്ള മികച്ച ഡീലുകൾ", "url": f"https://www.amazon.in/s?k=under+99+daily+essentials&tag={AMAZON_TAG}"}],
                [{"text": "⚡ Amazon ₹1 & ₹9 ഫ്ലാഷ് ഡീലുകൾ", "url": f"https://www.amazon.in/deals?tag={AMAZON_TAG}&pct-off=70-"}]
            ]
        }
        send_telegram_message(chat_id, msg, buttons)
        return

    # 4. വിദ്യാർത്ഥി സഹായി (സ്റ്റേഷനറി)
    if "വിദ്യാർത്ഥി സഹായി" in user_text:
        msg = (
            "📚 <b>വിദ്യാർത്ഥികൾക്കും രക്ഷിതാക്കൾക്കും ഉപകാരപ്രദമായ ഓഫറുകൾ:</b>\n\n"
            "നോട്ട്ബുക്കുകൾ, പേനകൾ, സ്കൂൾ ബാഗുകൾ, കാൽക്കുലേറ്ററുകൾ, മറ്റ് സ്റ്റഡി മെറ്റീരിയലുകൾ എന്നിവ ഹോൾസെയിൽ വിലക്കുറവിൽ വാങ്ങാം 👇"
        )
        buttons = {
            "inline_keyboard": [
                [{"text": "✏️ നോട്ട്ബുക്ക് & പേന കോമ്പോകൾ (വിലക്കുറവിൽ)", "url": f"https://www.amazon.in/s?k=school+stationery+combo+pack&tag={AMAZON_TAG}"}],
                [{"text": "🎒 സ്കൂൾ & കോളേജ് ബാഗുകൾ (Up to 70% Off)", "url": f"https://www.amazon.in/s?k=school+college+backpacks&tag={AMAZON_TAG}"}]
            ]
        }
        send_telegram_message(chat_id, msg, buttons)
        return

    # 5. കേരള സീസണൽ ഓഫറുകൾ
    if "കേരള സീസണൽ ഓഫറുകൾ" in user_text:
        msg = (
            "🌴 <b>കേരള സ്പെഷ്യൽ & സീസണൽ സേവിംഗ്സ്:</b>\n\n"
            "മഴക്കാല സാമഗ്രികൾ (കുട, റെയിൻകോട്ട്), അടുക്കള ഉപകരണങ്ങൾ, എൽഇഡി ലൈറ്റുകൾ, കൊതുക് നിവാരണ ഉപാധികൾ എന്നിവ വിലക്കുറവിൽ ലഭിക്കുന്ന ലിങ്കുകൾ 👇"
        )
        buttons = {
            "inline_keyboard": [
                [{"text": "☔ കുടകൾ & റെയിൻകോട്ടുകൾ", "url": f"https://www.amazon.in/s?k=umbrella+raincoat+waterproof&tag={AMAZON_TAG}"}],
                [{"text": "🍳 കിച്ചൺ & വീട്ടുപകരണങ്ങൾ (വമ്പൻ ഓഫറുകൾ)", "url": f"https://www.amazon.in/s?k=home+kitchen+appliances+deals&tag={AMAZON_TAG}"}]
            ]
        }
        send_telegram_message(chat_id, msg, buttons)
        return

    # 6. റീചാർജ് & ബിൽ ക്യാഷ്ബാക്ക്
    if "റീചാർജ് & ബിൽ ക്യാഷ്ബാക്ക്" in user_text:
        msg = (
            "💳 <b>മൊബൈൽ റീചാർജ് & ബിൽ പേയ്‌മെന്റ് ക്യാഷ്ബാക്ക്:</b>\n\n"
            "മൊബൈൽ റീചാർജ്, കറന്റ് ബിൽ, ഗ്യാസ് സിലിണ്ടർ എന്നിവ പേ ചെയ്യുമ്പോൾ ക്യാഷ്ബാക്ക് റിവാർഡുകൾ ലഭിക്കുന്ന ഔദ്യോഗിക പേജ് താഴെ നൽകുന്നു 👇"
        )
        buttons = {
            "inline_keyboard": [
                [{"text": "⚡ Amazon Pay റീചാർജ് & ബിൽ ഓഫറുകൾ", "url": f"https://www.amazon.in/amazonpay/home?tag={AMAZON_TAG}"}]
            ]
        }
        send_telegram_message(chat_id, msg, buttons)
        return

    # 7. പ്രൈസ് ട്രാക്കർ നിർദ്ദേശം
    if "ലൈവ് പ്രൈസ് ട്രാക്കർ" in user_text:
        help_msg = (
            "📉 <b>ആമസോൺ പ്രൈസ് ട്രാക്കർ ഉപയോഗിക്കേണ്ട വിധം:</b>\n\n"
            "1. ആമസോണിൽ നിങ്ങൾ വാങ്ങാൻ ഉദ്ദേശിക്കുന്ന സാധനത്തിന്റെ <b>ലിങ്ക് (Share Link)</b> കോപ്പി ചെയ്യുക.\n"
            "2. ആ ലിങ്ക് ഈ ചാറ്റിലേക്ക് പേസ്റ്റ് ചെയ്ത് അയക്കുക.\n"
            "3. ബോട്ട് ഉടൻ തന്നെ ആ സാധനത്തിന്റെ മുൻകാലങ്ങളിലെ ഏറ്റവും കുറഞ്ഞ വില പരിശോധിക്കാനുള്ള ഗ്രാഫ് നൽകും!"
        )
        send_telegram_message(chat_id, help_msg)
        return

    # 8. ആമസോൺ ലിങ്ക് ട്രാക്കിംഗ് (Live URL)
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

    # 9. മറ്റ് ജനറൽ സെർച്ചുകൾ
    encoded = urllib.parse.quote_plus(user_text)
    amazon_url = f"https://www.amazon.in/s?k={encoded}&rh=p_72%3A1318476031&tag={AMAZON_TAG}"
    flipkart_url = f"https://www.flipkart.com/search?q={encoded}&sort=popularity"

    buttons = {
        "inline_keyboard": [
            [{"text": "🟠 Amazon-ൽ 4★+ ഓഫറുകൾ കാണുക", "url": amazon_url}],
            [{"text": "🔵 Flipkart-ൽ പരിശോധിക്കുക", "url": flipkart_url}]
        ]
    }
    send_telegram_message(chat_id, f"✅ <b>'{html.escape(user_text)}'</b> എന്നിവയിലെ ഏറ്റവും മികച്ച ഓഫറുകൾ താഴെ ലഭ്യമാണ്:", buttons)

# --- ചാനൽ പോസ്റ്റിംഗ് എഞ്ചിൻ ---
def post_deal(deal):
    safe_title = html.escape(deal["title"])

    caption = (
        f"🔥 <b>വമ്പൻ വിലക്കുറവ് (PRICE DROP ALERT)!</b>\n\n"
        f"📦 <b>ഉൽപ്പന്നം:</b> {safe_title}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>ഇന്നത്തെ ഓഫർ വില:</b> <b>{deal['price']}</b> {deal['mrp']} {deal['discount']}\n"
        f"🎉 <b>{deal['savings']}</b>\n"
        f"🛡️ 100% ഒറിജിനൽ ഗ്യാരണ്ടി | ടോപ്പ് റേറ്റിംഗ്\n"
        f"🚚 ഓർഡർ ചെയ്താൽ ഉടൻ വീട്ടിലെത്തും\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    buttons = {
        "inline_keyboard": [
            [{"text": "🛒 ഇപ്പോൾ തന്നെ ഓർഡർ ചെയ്യുക", "url": deal["direct_url"]}]
        ]
    }

    success = send_telegram_photo(CHANNEL_ID, deal["img_url"], caption, buttons)
    if not success:
        send_telegram_message(CHANNEL_ID, caption, buttons)

    print(f"✅ ചാനൽ പോസ്റ്റ് അയച്ചു: {deal['title'][:30]}")

# --- ചാനൽ ഓട്ടോമേഷൻ (ഓരോ 15 മിനിറ്റിലും പോസ്റ്റ്) ---
def channel_worker():
    catalog_cycle = itertools.cycle(VERIFIED_DEALS)
    time.sleep(2)
    
    while True:
        try:
            deal = next(catalog_cycle)
            post_deal(deal)
        except Exception as e:
            print(f"⚠️ വർക്കർ എറർ: {e}")
        time.sleep(900)  # 15 മിനിറ്റ്

# --- ടെലിഗ്രാം യൂസർ പോളിംഗ് ത്രെഡ് ---
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
    server_t = threading.Thread(target=run_web_server, daemon=True)
    server_t.start()

    channel_t = threading.Thread(target=channel_worker, daemon=True)
    channel_t.start()

    telegram_polling_thread()
