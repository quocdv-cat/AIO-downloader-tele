import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
import os
from flask import Flask
from threading import Thread

# Import service TikTok (Đảm bảo bạn vẫn giữ file services/tiktok.py)
from services import tiktok

# =====================================================
# SERVER ẢO (KEEP ALIVE)
# =====================================================
app = Flask(__name__)
@app.route('/')
def home(): return "<h1>TikTok Bot Stable is Running!</h1>"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_web).start()

# =====================================================
# CẤU HÌNH BOT
# =====================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN: BOT_TOKEN = "TOKEN_TEST_CUA_BAN"

bot = telebot.TeleBot(BOT_TOKEN)
MAX_FILE_SIZE = 48 * 1024 * 1024 # 48MB

# Cache lưu link nhạc
msg_cache = {}

def music_btn(vid_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎵 Tải Nhạc (MP3)", callback_data=f"aud_{vid_id}"))
    return markup

# =====================================================
# XỬ LÝ TIN NHẮN
# =====================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, 
                 "👋 **Chào bạn!**\n\n"
                 "Gửi link TikTok (Video hoặc Slide ảnh) vào đây, mình sẽ tải bản đẹp nhất không logo.",
                 parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_tiktok_link(message):
    url = message.text.strip()
    
    # 1. Kiểm tra link
    if "tiktok.com" not in url:
        bot.reply_to(message, "⚠️ Vui lòng gửi link TikTok hợp lệ.")
        return

    # 2. Thông báo đang xử lý
    status_msg = bot.reply_to(message, "🔎 **Bước 1/3:** Đang kết nối TikTok...", parse_mode="Markdown")

    try:
        # Gọi Service TikTok
        data = tiktok.get_tiktok_data(url)

        if not data:
            bot.edit_message_text("❌ Lỗi: Không tìm thấy nội dung (Link hỏng hoặc Private).", 
                                  chat_id=message.chat.id, message_id=status_msg.message_id)
            return

        # Lưu cache nhạc
        msg_cache[data['id']] = data['music']
        caption = f"🎬 **{data.get('title', 'TikTok Content')}**\n👤: {data['author']}\n🤖 Bot by Quoc Dong"

        # --- TRƯỜNG HỢP VIDEO ---
        if data['type'] == 'video':
            bot.edit_message_text("⬇️ **Bước 2/3:** Đang tải về Server...", 
                                  chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
            # Tải file về RAM
            file_res = requests.get(data['video_url'], stream=True)
            
            if int(file_res.headers.get('Content-Length', 0)) > MAX_FILE_SIZE:
                bot.edit_message_text(f"⚠️ Video quá nặng (>50MB). [Tải trực tiếp tại đây]({data['video_url']})",
                                      chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
                return

            bot.edit_message_text("⬆️ **Bước 3/3:** Đang gửi cho bạn...", 
                                  chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
            # Gửi Video + Nút nhạc
            bot.send_video(
                message.chat.id, 
                file_res.content, 
                caption=caption, 
                parse_mode="Markdown",
                reply_markup=music_btn(data['id'])
            )
            bot.delete_message(message.chat.id, status_msg.message_id)

        # --- TRƯỜNG HỢP SLIDE ẢNH ---
        elif data['type'] == 'slide':
            bot.edit_message_text("📸 Đang xử lý Album ảnh...", 
                                  chat_id=message.chat.id, message_id=status_msg.message_id)
            
            # Xử lý album (tối đa 10 ảnh)
            album = []
            for i, img_url in enumerate(data['images'][:10]):
                if i == 0:
                    album.append(InputMediaPhoto(img_url, caption=caption, parse_mode="Markdown"))
                else:
                    album.append(InputMediaPhoto(img_url))
            
            bot.send_media_group(message.chat.id, album)
            # Gửi nút nhạc riêng
            bot.send_message(message.chat.id, "👇 Nhạc nền của Slide:", reply_markup=music_btn(data['id']))
            bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        print(f"Lỗi: {e}")
        bot.edit_message_text("❌ Lỗi hệ thống.", chat_id=message.chat.id, message_id=status_msg.message_id)

# XỬ LÝ NÚT TẢI NHẠC
@bot.callback_query_handler(func=lambda call: True)
def callback_audio(call):
    if call.data.startswith("aud_"):
        vid_id = call.data.split("_")[1]
        music_url = msg_cache.get(vid_id)
        
        if music_url:
            bot.answer_callback_query(call.id, "🚀 Đang tải nhạc...")
            try:
                audio_content = requests.get(music_url).content
                bot.send_audio(call.message.chat.id, audio_content, caption="🎵 Audio Extracted")
            except:
                bot.send_message(call.message.chat.id, "❌ Lỗi tải nhạc.")
        else:
            bot.answer_callback_query(call.id, "❌ Link hết hạn.")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()