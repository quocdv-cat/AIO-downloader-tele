import html
import io
import logging
import os
from collections import OrderedDict
from threading import Lock, Thread

import telebot
from flask import Flask, jsonify
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from services import tiktok

# =====================================================
# CẤU HÌNH LOGGING
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("AIO-Bot")

# =====================================================
# SERVER ẢO (KEEP ALIVE)
# =====================================================
app = Flask(__name__)


@app.route("/")
def home():
    return "<h1>TikTok Bot Stable is Running!</h1>"


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "AIO-down"}), 200


def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


def keep_alive():
    server_thread = Thread(target=run_web, daemon=True)
    server_thread.start()


# =====================================================
# CẤU HÌNH BOT & BỘ NHỚ ĐỆM AN TOÀN (BOUNDED LRU CACHE)
# =====================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "TOKEN_TEST_CUA_BAN"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=8)

MAX_FILE_SIZE = 48 * 1024 * 1024  # 48MB (Giới hạn Bot API của Telegram là 50MB)
MAX_CAPTION_LENGTH = 1024  # Giới hạn độ dài caption của Telegram
MAX_CACHE_ITEMS = 500  # Giới hạn số lượng item lưu trong RAM để chống tràn bộ nhớ


class BoundedCache:
    """Bộ nhớ đệm giới hạn kích thước (LRU) an toàn cho đa luồng (Thread-safe)."""

    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._store: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = value
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def get(self, key: str) -> dict | None:
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]


media_cache = BoundedCache(max_size=MAX_CACHE_ITEMS)


# =====================================================
# HÀM TIỆN ÍCH (HELPERS)
# =====================================================
def build_caption(data: dict) -> str:
    """Tạo caption định dạng HTML an toàn, tự động cắt ngắn nếu vượt quá 1024 ký tự."""
    raw_title = (data.get("title") or "TikTok Content").strip()
    raw_author = (data.get("author") or "Unknown").strip()

    safe_author = html.escape(raw_author)
    footer = f"\n👤: <b>{safe_author}</b>\n🤖 Bot by Quoc Dong"

    # Đảm bảo tổng chiều dài không vượt quá giới hạn 1024 ký tự của Telegram
    max_title_len = max(100, MAX_CAPTION_LENGTH - len(footer) - 20)
    if len(raw_title) > max_title_len:
        raw_title = raw_title[: max_title_len - 3] + "..."

    safe_title = html.escape(raw_title)
    return f"🎬 <b>{safe_title}</b>{footer}"


def build_action_markup(data: dict) -> InlineKeyboardMarkup | None:
    """Tạo bàn phím nút bấm (Tải nhạc MP3, Video HD) chỉ khi có link hợp lệ."""
    vid_id = str(data.get("id") or "")
    has_music = bool(data.get("music"))
    hd_url = data.get("hd_video_url")
    normal_url = data.get("video_url")

    buttons = []
    if has_music and vid_id:
        buttons.append(InlineKeyboardButton("🎵 Tải Nhạc (MP3)", callback_data=f"aud_{vid_id}"))

    # Thêm nút mở link HD trực tiếp nếu có
    if hd_url and hd_url != normal_url:
        buttons.append(InlineKeyboardButton("✨ Link HD Gốc", url=hd_url))

    if not buttons:
        return None

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(*buttons)
    return markup


def safe_edit_text(chat_id: int, message_id: int, text: str, **kwargs) -> None:
    """Chỉnh sửa tin nhắn an toàn, bỏ qua lỗi nếu tin nhắn không thay đổi hoặc đã bị xóa."""
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, **kwargs)
    except Exception as e:
        logger.debug("Ignored edit_message_text error: %s", e)


def safe_delete_message(chat_id: int, message_id: int) -> None:
    """Xóa tin nhắn trạng thái an toàn."""
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.debug("Ignored delete_message error: %s", e)


def download_stream_to_memory(url: str, max_bytes: int = MAX_FILE_SIZE) -> io.BytesIO | None:
    """
    Tải file theo từng chunk (64KB) với kiểm soát dung lượng chặt chẽ và timeout.
    Trả về None nếu file vượt quá giới hạn max_bytes để bảo vệ RAM.
    """
    with tiktok.http_session.get(url, stream=True, timeout=(10, 45)) as res:
        res.raise_for_status()
        content_length = int(res.headers.get("Content-Length") or 0)
        if content_length > max_bytes:
            return None

        buffer = io.BytesIO()
        downloaded = 0
        for chunk in res.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            downloaded += len(chunk)
            if downloaded > max_bytes:
                buffer.close()
                return None
            buffer.write(chunk)

        buffer.seek(0)
        return buffer


# =====================================================
# XỬ LÝ TIN NHẮN
# =====================================================
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    welcome_text = (
        "👋 <b>Chào bạn!</b>\n\n"
        "Gửi link <b>TikTok</b> hoặc <b>Douyin</b> (Video hoặc Slide ảnh) vào đây, "
        "mình sẽ tự động tách link và tải bản đẹp nhất không logo cho bạn.\n\n"
        "💡 <i>Mẹo: Bạn có thể dán nguyên đoạn văn bản chia sẻ từ ứng dụng TikTok mà không cần xóa chữ thừa!</i>"
    )
    bot.reply_to(message, welcome_text, parse_mode="HTML")


@bot.message_handler( content_types=["text"], func=lambda message: True)
def handle_tiktok_link(message):
    text = (message.text or "").strip()

    # 1. Trích xuất link TikTok/Douyin bằng Regex
    url = tiktok.extract_tiktok_url(text)
    if not url:
        # Chỉ nhắc nhở nếu người dùng nhắn tin riêng (Private Chat) với Bot.
        # Trong Group Chat, bỏ qua tin nhắn trò chuyện thông thường để tránh spam.
        if message.chat.type == "private":
            bot.reply_to(
                message,
                "⚠️ Vui lòng gửi đường dẫn TikTok hoặc Douyin hợp lệ (ví dụ: <code>https://vt.tiktok.com/...</code>).",
                parse_mode="HTML",
            )
        return

    # 2. Thông báo đang xử lý
    status_msg = bot.reply_to(
        message,
        "🔎 <b>Bước 1/3:</b> Đang phân tích liên kết TikTok...",
        parse_mode="HTML",
    )

    try:
        data = tiktok.get_tiktok_data(url)

        if not data:
            safe_edit_text(
                message.chat.id,
                status_msg.message_id,
                "❌ <b>Không tìm thấy nội dung!</b>\nLiên kết có thể bị lỗi, ở chế độ Riêng tư (Private) hoặc máy chủ đang bận.",
                parse_mode="HTML",
            )
            return

        # Lưu thông tin vào bộ nhớ đệm giới hạn (LRU Cache)
        vid_id = str(data["id"])
        if data.get("music"):
            media_cache.set(
                vid_id,
                {
                    "music_url": data["music"],
                    "title": data.get("music_title") or data.get("title") or "TikTok Audio",
                    "author": data.get("author") or "TikTok",
                },
            )

        caption = build_caption(data)
        reply_markup = build_action_markup(data)

        # --- TRƯỜNG HỢP 1: VIDEO ---
        if data["type"] == "video":
            video_url = data["video_url"]
            hd_url = data.get("hd_video_url") or video_url

            safe_edit_text(
                message.chat.id,
                status_msg.message_id,
                "⚡ <b>Bước 2/3:</b> Đang xử lý và gửi Video...",
                parse_mode="HTML",
            )
            bot.send_chat_action(message.chat.id, "upload_video")

            # Chiến lược 1 (Zero-RAM): Để máy chủ Telegram tự tải trực tiếp từ URL CDN
            sent_directly = False
            try:
                bot.send_video(
                    message.chat.id,
                    video_url,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    supports_streaming=True,
                )
                sent_directly = True
            except Exception as direct_err:
                logger.info("Direct URL send failed, falling back to stream download: %s", direct_err)

            # Chiến lược 2 (Fallback): Tải theo luồng (Stream) có kiểm soát dung lượng về RAM rồi gửi lên
            if not sent_directly:
                safe_edit_text(
                    message.chat.id,
                    status_msg.message_id,
                    "⬇️ <b>Bước 2/3:</b> Đang tải Video về máy chủ...",
                    parse_mode="HTML",
                )
                video_buffer = download_stream_to_memory(video_url, max_bytes=MAX_FILE_SIZE)

                if video_buffer is None:
                    safe_url = html.escape(hd_url, quote=True)
                    safe_edit_text(
                        message.chat.id,
                        status_msg.message_id,
                        f"⚠️ Video có dung lượng quá lớn (&gt;48MB).\n👉 <a href=\"{safe_url}\">Nhấn vào đây để tải trực tiếp bản gốc</a>",
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                    return

                video_buffer.name = f"tiktok_{vid_id}.mp4"
                safe_edit_text(
                    message.chat.id,
                    status_msg.message_id,
                    "⬆️ <b>Bước 3/3:</b> Đang tải Video lên Telegram...",
                    parse_mode="HTML",
                )
                bot.send_chat_action(message.chat.id, "upload_video")

                try:
                    bot.send_video(
                        message.chat.id,
                        video_buffer,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                        supports_streaming=True,
                    )
                finally:
                    video_buffer.close()

            safe_delete_message(message.chat.id, status_msg.message_id)

        # --- TRƯỜNG HỢP 2: SLIDE ẢNH ---
        elif data["type"] == "slide":
            images = data.get("images") or []
            total_images = len(images)

            safe_edit_text(
                message.chat.id,
                status_msg.message_id,
                f"📸 Đang xử lý Album ảnh ({total_images} ảnh)...",
                parse_mode="HTML",
            )
            bot.send_chat_action(message.chat.id, "upload_photo")

            # Chia thành từng cụm tối đa 10 ảnh (Giới hạn của Telegram send_media_group)
            batch_size = 10
            for batch_start in range(0, total_images, batch_size):
                batch_urls = images[batch_start : batch_start + batch_size]
                album = []
                for idx, img_url in enumerate(batch_urls):
                    if batch_start == 0 and idx == 0:
                        album.append(InputMediaPhoto(img_url, caption=caption, parse_mode="HTML"))
                    else:
                        album.append(InputMediaPhoto(img_url))

                try:
                    bot.send_media_group(message.chat.id, album)
                except Exception as group_err:
                    logger.warning("Direct media_group failed, downloading images to memory: %s", group_err)
                    # Fallback: Tải ảnh về bộ nhớ nếu Telegram không truy cập trực tiếp được URL ảnh
                    fallback_album = []
                    buffers = []
                    try:
                        for idx, img_url in enumerate(batch_urls):
                            img_buf = download_stream_to_memory(img_url, max_bytes=10 * 1024 * 1024)
                            if not img_buf:
                                continue
                            img_buf.name = f"slide_{batch_start + idx}.jpg"
                            buffers.append(img_buf)
                            if batch_start == 0 and len(fallback_album) == 0:
                                fallback_album.append(
                                    InputMediaPhoto(img_buf, caption=caption, parse_mode="HTML")
                                )
                            else:
                                fallback_album.append(InputMediaPhoto(img_buf))
                        if fallback_album:
                            bot.send_media_group(message.chat.id, fallback_album)
                    finally:
                        for buf in buffers:
                            buf.close()

            # Gửi nút tải nhạc nếu Slide có nhạc nền
            if reply_markup:
                bot.send_message(
                    message.chat.id,
                    "👇 <b>Tùy chọn thêm cho Album:</b>",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            safe_delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        logger.exception("Unhandled error while processing TikTok URL %s: %s", url, e)
        safe_edit_text(
            message.chat.id,
            status_msg.message_id,
            "❌ <b>Đã xảy ra lỗi khi xử lý yêu cầu.</b> Vui lòng thử lại sau ít phút!",
            parse_mode="HTML",
        )


# =====================================================
# XỬ LÝ NÚT TẢI NHẠC (CALLBACK QUERY)
# =====================================================
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("aud_"))
def callback_audio(call):
    # Sử dụng split("_", 1) để không bị cắt nhầm nếu ID chứa dấu gạch dưới "_"
    vid_id = call.data.split("_", 1)[1]
    cached_info = media_cache.get(vid_id)

    if not cached_info or not cached_info.get("music_url"):
        bot.answer_callback_query(
            call.id,
            "❌ Liên kết nhạc đã hết hạn. Vui lòng gửi lại link TikTok!",
            show_alert=True,
        )
        return

    music_url = cached_info["music_url"]
    title = cached_info.get("title") or "TikTok Audio"
    performer = cached_info.get("author") or "TikTok"

    bot.answer_callback_query(call.id, "🚀 Đang trích xuất âm thanh MP3...")
    bot.send_chat_action(call.message.chat.id, "upload_voice")

    try:
        # Thử gửi trực tiếp URL âm thanh trước
        try:
            bot.send_audio(
                call.message.chat.id,
                music_url,
                caption="🎵 <b>Audio Extracted</b>",
                parse_mode="HTML",
                title=title[:64],
                performer=performer[:64],
            )
            return
        except Exception:
            pass

        # Fallback: Tải luồng âm thanh về RAM
        audio_buffer = download_stream_to_memory(music_url, max_bytes=MAX_FILE_SIZE)
        if not audio_buffer:
            bot.send_message(
                call.message.chat.id,
                "⚠️ File âm thanh quá lớn hoặc không khả dụng.",
            )
            return

        audio_buffer.name = f"audio_{vid_id}.mp3"
        try:
            bot.send_audio(
                call.message.chat.id,
                audio_buffer,
                caption="🎵 <b>Audio Extracted</b>",
                parse_mode="HTML",
                title=title[:64],
                performer=performer[:64],
            )
        finally:
            audio_buffer.close()

    except Exception as e:
        logger.error("Failed to send audio for vid_id=%s: %s", vid_id, e)
        bot.send_message(call.message.chat.id, "❌ Không thể tải nhạc lúc này. Vui lòng thử lại sau.")


if __name__ == "__main__":
    logger.info("Starting Keep-Alive web server and Telegram Bot polling...")
    keep_alive()
    bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
