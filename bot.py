import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
import os
from flask import Flask
from threading import Thread
import tiktok_service  # Import module xử lý bên trên

# =====================================================
# PHẦN 1: CẤU HÌNH SERVER ẢO (Để chạy 24/7 Free)
# =====================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Bot đang chạy ngon lành! (24/7)</h1>"

def run_web():
    # Render sẽ cấp port qua biến môi trường, mặc định là 8080 nếu chạy local
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# =====================================================
# PHẦN 2: LOGIC BOT TELEGRAM
# =====================================================

# Lấy Token bảo mật từ biến môi trường
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    # Token dự phòng khi chạy test trên máy (Nhớ xóa khi deploy thật)
    BOT_TOKEN = "TOKEN_CỦA_BẠN_DÁN_VÀO_ĐÂY_NẾU_TEST_LOCAL"

bot = telebot.TeleBot(BOT_TOKEN)
MAX_FILE_SIZE = 48 * 1024 * 1024  # Giới hạn 48MB để an toàn

# Cache tạm để lưu link nhạc (Dùng cho nút bấm)
msg_cache = {}

# Hàm tạo nút tải nhạc
def create_music_btn(vid_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎵 Tải Nhạc (Audio)", callback_data=f"aud_{vid_id}"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, 
                 "👋 **Chào bạn!**\n"
                 "Gửi link TikTok (Video hoặc Slide ảnh) vào đây, mình sẽ tải bản đẹp nhất cho bạn.",
                 parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_tiktok(message):
    url = message.text.strip()
    
    if "tiktok.com" not in url:
        bot.reply_to(message, "⚠️ Link không hợp lệ.")
        return

    # Gửi tin nhắn chờ
    wait_msg = bot.reply_to(message, "🔎 Đang xử lý dữ liệu...")

    # Gọi Service
    data = tiktok_service.get_tiktok_data(url)

    if not data:
        bot.edit_message_text("❌ Không tìm thấy nội dung. Link có thể bị lỗi hoặc Private.", 
                              chat_id=message.chat.id, message_id=wait_msg.message_id)
        return

    # Lưu link nhạc vào cache
    msg_cache[data['id']] = data['music']
    
    caption = f"🎬 **{data['title']}**\n👤 Kênh: {data['author']}\n🤖 Bot by Quoc Dong"

    try:
        # --- TRƯỜNG HỢP 1: VIDEO ---
        if data['type'] == 'video':
            # Tải về RAM trước
            video_content = requests.get(data['video_url']).content
            
            if len(video_content) > MAX_FILE_SIZE:
                bot.edit_message_text(f"⚠️ Video quá nặng. [Tải tại đây]({data['video_url']})",
                                      chat_id=message.chat.id, message_id=wait_msg.message_id, parse_mode="Markdown")
            else:
                bot.delete_message(message.chat.id, wait_msg.message_id)
                bot.send_video(
                    message.chat.id, 
                    video_content, 
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=create_music_btn(data['id']) # Luôn có nút nhạc
                )

        # --- TRƯỜNG HỢP 2: SLIDE ẢNH ---
        elif data['type'] == 'slide':
            # Telegram cho phép tối đa 10 ảnh/nhóm
            album = []
            for i, img_url in enumerate(data['images'][:10]):
                if i == 0:
                    album.append(InputMediaPhoto(img_url, caption=caption, parse_mode="Markdown"))
                else:
                    album.append(InputMediaPhoto(img_url))
            
            bot.delete_message(message.chat.id, wait_msg.message_id)
            bot.send_media_group(message.chat.id, album)
            # Vì Album không gắn nút được, nên gửi nút nhạc riêng ngay bên dưới
            bot.send_message(message.chat.id, "👇 Nhạc nền của Slide:", reply_markup=create_music_btn(data['id']))

    except Exception as e:
        print(f"Lỗi: {e}")
        bot.edit_message_text("❌ Có lỗi khi gửi file.", chat_id=message.chat.id, message_id=wait_msg.message_id)

# Xử lý khi bấm nút tải nhạc
@bot.callback_query_handler(func=lambda call: True)
def callback_music(call):
    if call.data.startswith("aud_"):
        vid_id = call.data.split("_")[1]
        music_url = msg_cache.get(vid_id)
        
        if music_url:
            bot.answer_callback_query(call.id, "🚀 Đang tải nhạc...")
            try:
                bot.send_audio(call.message.chat.id, music_url, caption="🎵 Audio Extracted")
            except:
                bot.send_message(call.message.chat.id, "❌ Lỗi tải nhạc.")
        else:
            bot.answer_callback_query(call.id, "❌ Link hết hạn.")

# =====================================================
# PHẦN 3: CHẠY (MAIN)
# =====================================================
if __name__ == "__main__":
    keep_alive()  # Bật Web Server giả
    bot.infinity_polling() # Bật Bot