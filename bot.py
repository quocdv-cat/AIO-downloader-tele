import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
import os
from flask import Flask
from threading import Thread
import tiktok_service  # Module xử lý API

# =====================================================
# PHẦN 1: SERVER ẢO
# =====================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Bot Status: ONLINE ✅</h1>"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# =====================================================
# PHẦN 2: LOGIC BOT & TIẾN TRÌNH
# =====================================================

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    BOT_TOKEN = "TOKEN_TEST_CUA_BAN"

bot = telebot.TeleBot(BOT_TOKEN)
MAX_FILE_SIZE = 48 * 1024 * 1024
msg_cache = {}

def create_music_btn(vid_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎵 Tải Nhạc (Audio)", callback_data=f"aud_{vid_id}"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, 
                 "👋 **Chào bạn!**\n"
                 "Gửi link TikTok vào đây để xem tiến trình xử lý nhé!",
                 parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_tiktok(message):
    url = message.text.strip()
    
    if "tiktok.com" not in url:
        bot.reply_to(message, "⚠️ Link không hợp lệ.")
        return

    # [BƯỚC 1] BẮT ĐẦU
    status_msg = bot.reply_to(message, "🔎 **Bước 1/3:** Đang kết nối API TikTok...", parse_mode="Markdown")

    # Gọi Service
    data = tiktok_service.get_tiktok_data(url)

    if not data:
        bot.edit_message_text("❌ **Lỗi:** Không tìm thấy nội dung. Link hỏng hoặc Private.", 
                              chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        return

    # Lưu cache
    msg_cache[data['id']] = data['music']
    
    caption = f"🎬 **{data['title']}**\n👤 Kênh: {data['author']}\n🤖 Bot by Quoc Dong"

    try:
        # --- XỬ LÝ VIDEO ---
        if data['type'] == 'video':
            # [BƯỚC 2] TẢI VỀ SERVER
            bot.edit_message_text(f"⬇️ **Bước 2/3:** Đang tải video về Server...\n(Video: {data['title'][:20]}...)",
                                  chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
            # Tải nội dung
            video_response = requests.get(data['video_url'])
            video_content = video_response.content
            
            if len(video_content) > MAX_FILE_SIZE:
                bot.edit_message_text(f"⚠️ Video quá nặng (>50MB). Telegram không cho gửi.\n🔗 [Bấm vào đây tải trực tiếp]({data['video_url']})",
                                      chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                return

            # [BƯỚC 3] UPLOAD LÊN TELEGRAM
            bot.edit_message_text("⬆️ **Bước 3/3:** Đang gửi video cho bạn...", 
                                  chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

            # Gửi file
            bot.send_video(
                message.chat.id, 
                video_content, 
                caption=caption,
                parse_mode="Markdown",
                reply_markup=create_music_btn(data['id'])
            )
            
            # Xóa tin nhắn trạng thái khi xong
            bot.delete_message(message.chat.id, status_msg.message_id)

        # --- XỬ LÝ SLIDE ẢNH ---
        elif data['type'] == 'slide':
            # Với Slide thì nhanh hơn nên gộp bước
            bot.edit_message_text("📸 **Đang xử lý Album ảnh...**", 
                                  chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
            album = []
            for i, img_url in enumerate(data['images'][:10]):
                if i == 0:
                    album.append(InputMediaPhoto(img_url, caption=caption, parse_mode="Markdown"))
                else:
                    album.append(InputMediaPhoto(img_url))
            
            bot.send_media_group(message.chat.id, album)
            bot.send_message(message.chat.id, "👇 Nhạc nền của Slide:", reply_markup=create_music_btn(data['id']))
            
            # Xóa tin nhắn chờ
            bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        print(f"Lỗi: {e}")
        bot.edit_message_text("❌ Lỗi hệ thống khi gửi file.", chat_id=message.chat.id, message_id=status_msg.message_id)

@bot.callback_query_handler(func=lambda call: True)
def callback_music(call):
    if call.data.startswith("aud_"):
        vid_id = call.data.split("_")[1]
        music_url = msg_cache.get(vid_id)
        
        if music_url:
            # Thông báo nhỏ dạng Toast (hiện lên rồi tắt)
            bot.answer_callback_query(call.id, "🚀 Đang tải nhạc, đợi xíu...")
            try:
                bot.send_audio(call.message.chat.id, music_url, caption="🎵 Audio Extracted")
            except:
                bot.send_message(call.message.chat.id, "❌ Lỗi tải nhạc.")
        else:
            bot.answer_callback_query(call.id, "❌ Link hết hạn.")

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
