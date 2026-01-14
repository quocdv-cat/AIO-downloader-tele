import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
import os
from flask import Flask
from threading import Thread
<<<<<<< HEAD

# Import các service từ thư mục services
from services import tiktok
from services import cobalt

# =====================================================
# SERVER ẢO
=======
import tiktok_service  # Module xử lý API

# =====================================================
# PHẦN 1: SERVER ẢO
>>>>>>> 14c027baad252521247520326edac8041752131c
# =====================================================
app = Flask(__name__)
@app.route('/')
<<<<<<< HEAD
def home(): return "<h1>Bot Multi-Platform Online</h1>"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run_web).start()

# =====================================================
# BOT CONFIG
# =====================================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN: BOT_TOKEN = "TOKEN_TEST_CUA_BAN"

bot = telebot.TeleBot(BOT_TOKEN)
MAX_FILE_SIZE = 48 * 1024 * 1024 # 48MB

# Lưu trạng thái người dùng đang chọn nền tảng nào
# Ví dụ: {123456: 'tiktok', 987654: 'youtube'}
user_modes = {} 

# --- HÀM TẠO MENU CHÍNH ---
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    btn_tt = InlineKeyboardButton("🎵 TikTok", callback_data="mode_tiktok")
    btn_yt = InlineKeyboardButton("▶️ YouTube", callback_data="mode_youtube")
    btn_fb = InlineKeyboardButton("📘 Facebook", callback_data="mode_facebook")
    markup.add(btn_tt, btn_fb, btn_yt)
=======
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
>>>>>>> 14c027baad252521247520326edac8041752131c
    return markup

# --- HÀM TẠO NÚT NHẠC ---
def music_btn(vid_id, platform):
    # Chỉ TikTok mới hỗ trợ tách nhạc xịn, các cái khác tạm bỏ qua hoặc update sau
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
    # Mặc định set là TikTok
    user_modes[message.chat.id] = 'tiktok'
    
    bot.reply_to(message, 
<<<<<<< HEAD
                 "👋 **Chào bạn! Bot hỗ trợ đa nền tảng.**\n\n"
                 "👇 Hãy chọn nền tảng bạn muốn tải:",
                 reply_markup=main_menu(),
=======
                 "👋 **Chào bạn!**\n"
                 "Gửi link TikTok vào đây để xem tiến trình xử lý nhé!",
>>>>>>> 14c027baad252521247520326edac8041752131c
                 parse_mode="Markdown")

# Xử lý khi bấm nút chọn chế độ
@bot.callback_query_handler(func=lambda call: call.data.startswith("mode_"))
def handle_mode_selection(call):
    mode = call.data.split("_")[1] # Lấy chữ tiktok, youtube, hoặc facebook
    user_modes[call.message.chat.id] = mode
    
    platform_name = mode.upper()
    bot.answer_callback_query(call.id, f"Đã chuyển sang chế độ {platform_name}")
    
    bot.edit_message_text(f"✅ **Đã chọn: {platform_name}**\n\n👉 Hãy gửi link {platform_name} vào đây.",
                          chat_id=call.message.chat.id,
                          message_id=call.message.message_id,
                          reply_markup=main_menu(), # Giữ menu để đổi lại nếu muốn
                          parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_links(message):
    url = message.text.strip()
    chat_id = message.chat.id
    
    # Lấy chế độ hiện tại (Mặc định là tiktok nếu chưa chọn)
    current_mode = user_modes.get(chat_id, 'tiktok')

    # Validate sơ bộ
    if current_mode == 'tiktok' and "tiktok.com" not in url:
        bot.reply_to(message, "⚠️ Bạn đang ở chế độ TikTok. Vui lòng gửi link TikTok (hoặc bấm menu để đổi).")
        return
    elif current_mode == 'youtube' and ("youtube.com" not in url and "youtu.be" not in url):
        bot.reply_to(message, "⚠️ Bạn đang ở chế độ YouTube. Link không hợp lệ.")
        return
    elif current_mode == 'facebook' and "facebook.com" not in url and "fb.watch" not in url:
        bot.reply_to(message, "⚠️ Bạn đang ở chế độ Facebook. Link không hợp lệ.")
        return

<<<<<<< HEAD
    status_msg = bot.reply_to(message, f"🔎 Đang xử lý link {current_mode.upper()}...\n(Vui lòng đợi 5-10s)")

    try:
        data = None
        
        # PHÂN LUỒNG XỬ LÝ
        if current_mode == 'tiktok':
            data = tiktok.get_tiktok_data(url)
        else:
            # Facebook và Youtube dùng chung Cobalt
            data = cobalt.get_cobalt_data(url)

        if not data:
            bot.edit_message_text("❌ Lỗi: Không tải được. Link Private hoặc Server bận.", chat_id=chat_id, message_id=status_msg.message_id)
            return

        # XỬ LÝ GỬI FILE (Chung cho các nền tảng)
        caption = f"🎬 **{data.get('title', 'Video Download')}**\nSource: {current_mode.upper()}"
        
        if data['type'] == 'video':
            bot.edit_message_text("⬇️ Đang tải về Server...", chat_id=chat_id, message_id=status_msg.message_id)
            
            # Tải nội dung
            file_res = requests.get(data['video_url'], stream=True)
            
            # Kiểm tra dung lượng
            if int(file_res.headers.get('Content-Length', 0)) > MAX_FILE_SIZE:
                bot.edit_message_text(f"⚠️ **File quá nặng (>50MB)!**\nTelegram không cho phép bot gửi.\n\n🔗 [Bấm vào đây để tải trực tiếp]({data['video_url']})",
                                      chat_id=chat_id, message_id=status_msg.message_id, parse_mode="Markdown")
                return

            bot.edit_message_text("⬆️ Đang upload...", chat_id=chat_id, message_id=status_msg.message_id)
            
            bot.send_video(
                chat_id, 
                file_res.content, 
                caption=caption, 
                parse_mode="Markdown",
                reply_markup=music_btn(data.get('id'), current_mode)
            )
            bot.delete_message(chat_id, status_msg.message_id)

        elif data['type'] == 'slide' and current_mode == 'tiktok':
            # Chỉ TikTok mới có logic slide này
            bot.delete_message(chat_id, status_msg.message_id)
            album = [InputMediaPhoto(img, caption=caption if i==0 else '') for i, img in enumerate(data['images'][:10])]
            bot.send_media_group(chat_id, album)

    except Exception as e:
        print(e)
        bot.edit_message_text(f"❌ Lỗi hệ thống: {str(e)}", chat_id=chat_id, message_id=status_msg.message_id)

# (Giữ nguyên phần callback nhạc của TikTok ở bài trước nếu muốn, hoặc bỏ qua)

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
=======
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
>>>>>>> 14c027baad252521247520326edac8041752131c
