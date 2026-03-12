import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import os
import threading
import requests
from flask import Flask
from bakong_khqr import KHQR

# --- 1. ការកំណត់ WEB SERVER (សម្រាប់ KOYEB/RENDER) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    # Koyeb ប្រើ Port 8000 ជា Default
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

# --- 2. ការកំណត់ TELEGRAM BOT & BAKONG ---
TOKEN = '8614978833:AAFbiZkZCarmUWZjJBKFoe18lyqUVzbSSls'
bot = telebot.TeleBot(TOKEN)

# Bakong Token របស់អ្នក
BAKONG_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiMWUyN2QzM2NiYzNiNDkzNCJ9LCJpYXQiOjE3NzMzMjkxODMsImV4cCI6MTc4MTEwNTE4M30.tQaFRnrhJD1sMxh_dQLuPwHYEQrEKo-XCyUtPUCAb2M"

# បញ្ជីផលិតផល (Product Key ត្រូវតែដូចឈ្មោះ File .txt)
PRODUCTS = {
    'noverify': {'name': 'Acc Form No Verify', 'price': 0.01},
    'fullset_no2fa': {'name': 'Full Set No 2FA', 'price': 0.30},
    'fullset': {'name': 'Full Set (មាន 2FA)', 'price': 0.50}
}

user_orders = {}

# --- 3. អនុគមន៍គ្រប់គ្រងស្តុក (STOCK MANAGEMENT) ---
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
    
    # Update ស្តុកដែលនៅសល់
    with open(source_file, 'w', encoding='utf-8') as f:
        f.writelines(remaining_accounts)
        
    # បង្កើត File ថ្មីសម្រាប់ផ្ញើឱ្យភ្ញៀវ
    buyer_file_name = f"Order_{product_key}_{int(time.time())}.txt"
    with open(buyer_file_name, 'w', encoding='utf-8') as f:
        f.writelines(buyer_accounts)
        
    return buyer_file_name

# --- 4. អនុគមន៍ឆែកការបង់ប្រាក់ (PAYMENT CHECK) ---
def check_payment_status(p_hash):
    url = "https://api-bakong.nbc.gov.kh/v1/check_transaction_by_md5" 
    
    # ប្រាកដថា Token ថ្មី ហើយគ្មានដកឃ្លាខុសបច្ចេកទេស
    headers = {
        "Authorization": f"Bearer {BAKONG_TOKEN.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {"md5": p_hash} 
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        # បន្ថែមការ Print ដើម្បីមើលក្នុង Logs ថាវាលោត 403 មែនអត់
        print(f"DEBUG: Bakong Check -> Status: {response.status_code} | Body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("responseCode") == 0 or data.get("responseCode") == "0":
                return True
    except Exception as e:
        print(f"DEBUG: Error -> {e}")
    return False

def auto_payment_worker(chat_id, message_id, p_hash, product_key, qty):
    timeout = 300 # ៥ នាទី
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_payment_status(p_hash):
            try: bot.delete_message(chat_id, message_id)
            except: pass
            
            bot.send_message(chat_id, "✅ **បង់ប្រាក់ជោគជ័យ!** កំពុងរៀបចំទិន្នន័យជូន...", parse_mode="Markdown")
            
            buyer_file = extract_account_to_file(product_key, quantity=qty)
            if buyer_file:
                with open(buyer_file, 'rb') as doc:
                    bot.send_document(chat_id, doc, caption=f"🎉 អរគុណសម្រាប់ការជាវ! នេះជា {qty} គណនីរបស់អ្នក។")
                os.remove(buyer_file)
            else:
                bot.send_message(chat_id, "❌ សុំទោស មានបញ្ហាក្នុងការទាញស្តុក។ សូមទាក់ទង Admin។")
            return 
        time.sleep(7) # ឆែករៀងរាល់ ៧ វិនាទី
    
    try:
        bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption="❌ វិក្កយបត្រនេះផុតកំណត់ (៥ នាទី)។")
    except: pass

# --- 5. TELEGRAM BOT HANDLERS ---
def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    for key, p in PRODUCTS.items():
        stock = get_stock(key)
        markup.add(InlineKeyboardButton(f"🛒 {p['name']} - ${p['price']} (ស្តុក: {stock})", callback_data=f"buy_{key}"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "🛒 សួស្តី! សូមជ្រើសរើសប្រភេទគណនីដែលចង់ទិញ៖", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy_click(call):
    chat_id = call.message.chat.id
    product_key = call.data.replace('buy_', '')
    stock = get_stock(product_key)
    
    if stock > 0:
        user_orders[chat_id] = {'product_key': product_key}
        msg = bot.send_message(chat_id, f"📝 អ្នកជ្រើសរើស: **{PRODUCTS[product_key]['name']}**\n👉 សូមបញ្ចូល **ចំនួន** ដែលចង់ទិញ (មានក្នុងស្តុក: {stock}):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_quantity)
    else:
        bot.answer_callback_query(call.id, "❌ សុំទោស ផលិតផលនេះអស់ពីស្តុកហើយ។", show_alert=True)

def process_quantity(message):
    chat_id = message.chat.id
    if chat_id not in user_orders: return
    
    try:
        qty = int(message.text.strip())
        product_key = user_orders[chat_id]['product_key']
        stock = get_stock(product_key)
        
        if qty <= 0 or qty > stock:
            msg = bot.send_message(chat_id, f"❌ ចំនួនមិនត្រឹមត្រូវ (មានក្នុងស្តុក: {stock})។ សូមបញ្ជូលម្តងទៀត:")
            bot.register_next_step_handler(msg, process_quantity)
            return
            
        total_price = qty * PRODUCTS[product_key]['price']
        user_orders[chat_id].update({'qty': qty, 'total_price': total_price})
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("✅ យល់ព្រមទិញ", callback_data="confirm_order"), 
                   InlineKeyboardButton("❌ បោះបង់", callback_data="cancel_order"))
        
        bot.send_message(chat_id, f"🛍 **ការបញ្ជាទិញ**\n📌 ប្រភេទ: {PRODUCTS[product_key]['name']}\n🔢 ចំនួន: {qty} គណនី\n💵 សរុប: ${total_price:.2f}\n\nបន្តការទូទាត់?", 
                         reply_markup=markup, parse_mode="Markdown")
    except:
        msg = bot.send_message(chat_id, "❌ សូមបញ្ចូលជាលេខ។")
        bot.register_next_step_handler(msg, process_quantity)

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_order', 'cancel_order'])
def handle_checkout(call):
    chat_id = call.message.chat.id
    if call.data == 'cancel_order':
        bot.edit_message_text("🚫 ការបញ្ជាទិញត្រូវបានបោះបង់។", chat_id, call.message.message_id)
        return

    order = user_orders.get(chat_id)
    if not order: return
    
    bot.edit_message_text("🔄 កំពុងបង្កើត KHQR...", chat_id, call.message.message_id)
    
    try:
        khqr_tool = KHQR(BAKONG_TOKEN)
        bill_no = f"INV{int(time.time())}"
        
        # កែសម្រួលឱ្យត្រូវតាម Library Version ថ្មី
        qr_string = khqr_tool.create_qr(
            bank_account="ngim_bunrith1@bkrt",
            merchant_name="BUNRITH NGIM",
            merchant_city="Phnom Penh",
            amount=float(order['total_price']),
            currency="USD",
            store_label="Digital Accounts",
            phone_number="855974249441",
            bill_number=bill_no,
            terminal_label="BotShop",
            static=False
        )
        
        p_hash = khqr_tool.generate_md5(qr_string)
        img_path = khqr_tool.qr_image(qr_string)

        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                bot.delete_message(chat_id, call.message.message_id)
                msg = bot.send_photo(
                    chat_id, photo, 
                    caption=f"💸 តម្លៃសរុប: **${order['total_price']:.2f}**\n\n🔔 ប្រព័ន្ធនឹងផ្ញើទិន្នន័យឱ្យអូតូក្រោយបង់រួច! ⏳",
                    parse_mode="Markdown"
                )
            os.remove(img_path)
            
            threading.Thread(target=auto_payment_worker, 
                             args=(chat_id, msg.message_id, p_hash, order['product_key'], order['qty']), 
                             daemon=True).start()
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ បញ្ហាបង្កើត QR: {str(e)}")

# --- 6. ចាប់ផ្តើម BOT ជាមួយ ERROR HANDLING LOOP ---
if __name__ == "__main__":
    # រត់ Web Server ក្នុង Thread ផ្សេង
    threading.Thread(target=run_web, daemon=True).start()
    
    print("Bot លក់គណនី Auto-Pay កំពុងដំណើរការ...")
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot Polling Error: {e}")
            time.sleep(15) # រង់ចាំ ១៥ វិនាទី រួច Restart
