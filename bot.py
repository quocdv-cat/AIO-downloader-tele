import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
import os
from flask import Flask
from threading import Thread

# Import các service
from services import tiktok
from services import cobalt

# =====================================================
# SERVER ẢO
# =====================================================
app = Flask(__name__)
@app.route('/')
def home(): return "<h1>Bot Multi-Platform Online</h1>"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_web).start()

# =====================================================
# BOT CONFIG
# =====================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN: BOT_TOKEN = "TOKEN_TEST_CUA_BAN"

bot = telebot.TeleBot(BOT_TOKEN)
MAX_FILE_SIZE = 48 * 1024 * 1024 

user_modes = {} 

def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    btn_tt = InlineKeyboardButton("🎵 TikTok", callback_data="mode_tiktok")
    btn_yt = InlineKeyboardButton("▶️ YouTube", callback_data="mode_youtube")
    btn_fb = InlineKeyboardButton("📘 Facebook", callback_data="mode_facebook")
    markup.add(btn_tt, btn_fb, btn_yt)
    return markup

def music_btn(vid_id, platform):
    if platform == 'tiktok':
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🎵 Tải Nhạc (MP3)", callback_data=f"aud_{vid_id}"))
        return markup
    return None

# =====================================================
# HANDLERS
# =====================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_modes[message.chat.id] = 'tiktok'
    bot.reply_to(message, 
                 "👋 **Chào bạn! Bot hỗ trợ đa nền tảng.**\n\n"
                 "👇 Hãy chọn nền tảng bạn muốn tải:",
                 reply_markup=main_menu(),
                 parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("mode_"))
def handle_mode_selection(call):
    mode = call.data.split("_")[1]
    user_modes[call.message.chat.id] = mode
    platform_name = mode.upper()
    bot.answer_callback_query(call.id, f"Đã chuyển sang chế độ {platform_name}")
    bot.edit_message_text(f"✅ **Đã chọn: {platform_name}**\n\n👉 Hãy gửi link {platform_name} vào đây.",
                          chat_id=call.message.chat.id,
                          message_id=call.message.message_id,
                          reply_markup=main_menu(),
                          parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_links(message):
    url = message.text.strip()
    chat_id = message.chat.id
    current_mode = user_modes.get(chat_id, 'tiktok')

    if current_mode == 'tiktok' and "tiktok.com" not in url:
        bot.reply_to(message, "⚠️ Bạn đang ở chế độ TikTok. Vui lòng gửi link TikTok.")
        return
    elif current_mode == 'youtube' and ("youtube.com" not in url and "youtu.be" not in url):
        bot.reply_to(message, "⚠️ Bạn đang ở chế độ YouTube. Link không hợp lệ.")
        return
    elif current_mode == 'facebook' and "facebook.com" not in url and "fb.watch" not in url:
        bot.reply_to(message, "⚠️ Bạn đang ở chế độ Facebook. Link không hợp lệ.")
        return

    status_msg = bot.reply_to(message, f"🔎 Đang xử lý link {current_mode.upper()}...")

    try:
        data = None
        if current_mode == 'tiktok':
            data = tiktok.get_tiktok_data(url)
        else:
            data = cobalt.get_cobalt_data(url)

        if not data:
            bot.edit_message_text("❌ Lỗi: Không tải được.", chat_id=chat_id, message_id=status_msg.message_id)
            return

        caption = f"🎬 **{data.get('title', 'Video Download')}**\nSource: {current_mode.upper()}"
        
        if data['type'] == 'video':
            bot.edit_message_text("⬇️ Đang tải về Server...", chat_id=chat_id, message_id=status_msg.message_id)
            file_res = requests.get(data['video_url'], stream=True)
            
            if int(file_res.headers.get('Content-Length', 0)) > MAX_FILE_SIZE:
                bot.edit_message_text(f"⚠️ File quá nặng. [Tải trực tiếp]({data['video_url']})",
                                      chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
                return

            bot.edit_message_text("⬆️ Đang upload...", chat_id=chat_id, message_id=status_msg.message_id)
            bot.send_video(chat_id, file_res.content, caption=caption, parse_mode="Markdown",
                           reply_markup=music_btn(data.get('id'), current_mode))
            bot.delete_message(chat_id, status_msg.message_id)

        elif data['type'] == 'slide' and current_mode == 'tiktok':
            bot.delete_message(chat_id, status_msg.message_id)
            album = [InputMediaPhoto(img, caption=caption if i==0 else '') for i, img in enumerate(data['images'][:10])]
            bot.send_media_group(chat_id, album)

    except Exception as e:
        print(e)
        bot.edit_message_text("❌ Lỗi hệ thống.", chat_id=chat_id, message_id=status_msg.message_id)

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()