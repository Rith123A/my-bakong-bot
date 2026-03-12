import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import os
import threading
import requests
from flask import Flask
from bakong_khqr import KHQR

# --- ផ្នែកសម្រាប់ Koyeb (Web Server) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    # Koyeb ប្រើ Port 8000 ជា Default
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

# --- ការកំណត់ Bot ---
TOKEN = '8614978833:AAHLO26tvHuxzufMWw6epc_mSPuEnzIoDwA'
bot = telebot.TeleBot(TOKEN)

# Bakong Token
BAKONG_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiMWUyN2QzM2NiYzNiNDkzNCJ9LCJpYXQiOjE3NzI5NTM5MDcsImV4cCI6MTc4MDcyOTkwN30.lPQ5rXUPyoyA2WCDMTfBFex9prg2MF6VOanKuBbArWU"

# បញ្ជីផលិតផល
PRODUCTS = {
    'noverify': {'name': 'Acc Form No Verify', 'price': 0.01},
    'fullset_no2fa': {'name': 'Full Set No 2FA', 'price': 5.00},
    'fullset': {'name': 'Full Set (មាន 2FA)', 'price': 7.00}
}

user_orders = {}

# --- Functions គ្រប់គ្រងស្តុក ---
def get_stock(product_key):
    file_path = f"{product_key}.txt"
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f if line.strip()]
            return len(lines)
    return 0

def extract_account_to_file(product_key, quantity=1):
    source_file = f"{product_key}.txt"
    if not os.path.exists(source_file): return None
    with open(source_file, 'r', encoding='utf-8') as f:
        lines = [line for line in f if line.strip()]
    if len(lines) < quantity: return None
    
    buyer_accounts = lines[:quantity]
    remaining_accounts = lines[quantity:]
    
    with open(source_file, 'w', encoding='utf-8') as f:
        f.writelines(remaining_accounts)
        
    buyer_file_name = f"Order_{product_key}_{int(time.time())}.txt"
    with open(buyer_file_name, 'w', encoding='utf-8') as f:
        f.writelines(buyer_accounts)
    return buyer_file_name

# --- មុខងារឆែកការបង់ប្រាក់ ---
def check_payment_status(p_hash):
    url = "https://api-bakong.nbc.gov.kh/v1/check_transaction_by_md5" 
    headers = {
        "Authorization": f"Bearer {BAKONG_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"md5": p_hash} 
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("responseCode") == 0 or data.get("responseCode") == "0":
                return True
            if isinstance(data.get("data"), dict) and data["data"].get("status") == "SUCCESS":
                return True
    except Exception as e:
        print(f"Payment Check Error: {e}")
    return False

def auto_payment_worker(chat_id, message_id, p_hash, product_key, qty):
    timeout = 300 
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_payment_status(p_hash):
            try: bot.delete_message(chat_id, message_id)
            except: pass
            bot.send_message(chat_id, "✅ **បង់ប្រាក់ជោគជ័យ!** កំពុងផ្ញើគណនីជូន...", parse_mode="Markdown")
            
            buyer_file = extract_account_to_file(product_key, quantity=qty)
            if buyer_file:
                with open(buyer_file, 'rb') as doc:
                    bot.send_document(chat_id, doc, caption=f"🎉 នេះជា {qty} គណនីរបស់អ្នក។ អរគុណ!")
                os.remove(buyer_file)
            else:
                bot.send_message(chat_id, "❌ មានបញ្ហាក្នុងការទាញស្តុក។ សូមទាក់ទង Admin។")
            return 
        time.sleep(7)
    
    try: bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption="❌ វិក្កយបត្រផុតកំណត់។")
    except: pass

# --- Telegram Handlers ---
def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    for key, p in PRODUCTS.items():
        markup.add(InlineKeyboardButton(f"🛒 {p['name']} - ${p['price']} (ស្តុក: {get_stock(key)})", callback_data=f"buy_{key}"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "🛒 សួស្តី! សូមជ្រើសរើសផលិតផល៖", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    product_key = call.data.replace('buy_', '')
    stock = get_stock(product_key)
    if stock > 0:
        user_orders[call.message.chat.id] = {'product_key': product_key}
        msg = bot.send_message(call.message.chat.id, f"🔢 បញ្ចូលចំនួនដែលចង់ទិញ (ស្តុកមាន: {stock})")
        bot.register_next_step_handler(msg, process_quantity)
    else:
        bot.answer_callback_query(call.id, "❌ អស់ស្តុក")

def process_quantity(message):
    chat_id = message.chat.id
    try:
        qty = int(message.text)
        order = user_orders.get(chat_id)
        stock = get_stock(order['product_key'])
        if qty <= 0 or qty > stock:
            bot.send_message(chat_id, "❌ ចំនួនមិនត្រឹមត្រូវ")
            return
        
        total = qty * PRODUCTS[order['product_key']]['price']
        order.update({'qty': qty, 'total': total})
        
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ បញ្ជាក់", callback_data="confirm"), InlineKeyboardButton("❌ បោះបង់", callback_data="cancel"))
        bot.send_message(chat_id, f"🛍 សរុប: ${total:.2f}. បន្តទូទាត់?", reply_markup=markup)
    except:
        bot.send_message(chat_id, "❌ សូមបញ្ចូលជាលេខ")

@bot.callback_query_handler(func=lambda call: call.data in ['confirm', 'cancel'])
def handle_payment(call):
    chat_id = call.message.chat.id
    if call.data == 'cancel':
        bot.edit_message_text("❌ បោះបង់ការទិញ", chat_id, call.message.message_id)
        return

    order = user_orders.get(chat_id)
    bot.edit_message_text("🔄 កំពុងបង្កើត QR...", chat_id, call.message.message_id)
    
    try:
        khqr = KHQR(BAKONG_TOKEN)
        qr_str = khqr.create_qr(bank_account="ngim_bunrith1@bkrt", merchant_name="BUNRITH", amount=float(order['total']), currency="USD")
        p_hash = khqr.generate_md5(qr_str)
        img_path = khqr.qr_image(qr_str)
        
        with open(img_path, 'rb') as photo:
            msg = bot.send_photo(chat_id, photo, caption=f"💸 តម្លៃ: ${order['total']:.2f}\n🔔 ប្រព័ន្ធនឹងផ្ញើ Account ឱ្យអូតូក្រោយបង់រួច!")
            threading.Thread(target=auto_payment_worker, args=(chat_id, msg.message_id, p_hash, order['product_key'], order['qty']), daemon=True).start()
        os.remove(img_path)
    except Exception as e:
        bot.send_message(chat_id, f"Error: {e}")

# --- បើកដំណើរការ ---
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot is running...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except:
            time.sleep(10)
