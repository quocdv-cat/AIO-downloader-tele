import logging
import re
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Tạo HTTP Session dùng chung để tối ưu tốc độ kết nối (Connection Pooling) và tự động Retry
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


http_session = create_session()

# Regex nhận diện mọi định dạng link TikTok & Douyin trong văn bản bất kỳ
TIKTOK_URL_PATTERN = re.compile(
    r"(https?://(?:(?:www|vm|vt|m|t)\.)?(?:tiktok\.com|douyin\.com)/[^\s<>\"']+)",
    re.IGNORECASE,
)


def extract_tiktok_url(text: str) -> str | None:
    """Trích xuất URL TikTok/Douyin đầu tiên tìm thấy trong tin nhắn."""
    if not text:
        return None
    match = TIKTOK_URL_PATTERN.search(text)
    if not match:
        return None
    # Loại bỏ các dấu câu vô tình dính ở cuối link (.,;!)
    return match.group(1).rstrip(".,;!)'\"")


def _normalize_url(base: str, url: str | None) -> str | None:
    """Đảm bảo URL luôn là đường dẫn tuyệt đối (có http/https)."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(base, url)
    return url


# =========================================================
# PROVIDER 1: TIKWM (Ưu tiên số 1 - Hỗ trợ cả Video & Slide)
# =========================================================
def api_tikwm(url: str) -> dict | None:
    base_url = "https://www.tikwm.com"
    try:
        response = http_session.post(
            f"{base_url}/api/",
            data={"url": url, "hd": 1},
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0 or not data.get("data"):
            return None

        res = data["data"]
        author_info = res.get("author") or {}
        music_info = res.get("music_info") or {}

        vid_id = str(res.get("id") or "")
        if not vid_id:
            return None

        music_url = _normalize_url(
            base_url,
            res.get("music") or music_info.get("play"),
        )
        play_url = _normalize_url(base_url, res.get("play") or res.get("wmplay"))
        hd_url = _normalize_url(base_url, res.get("hdplay")) or play_url

        output = {
            "id": vid_id,
            "title": (res.get("title") or "TikTok Content").strip(),
            "author": author_info.get("nickname") or author_info.get("unique_id") or "Unknown",
            "music": music_url,
            "music_title": music_info.get("title") or "TikTok Audio",
            "cover": _normalize_url(base_url, res.get("cover") or res.get("origin_cover")),
            "duration": res.get("duration") or 0,
            "type": "video",
            "source": "TikWM",
        }

        # Kiểm tra Slide ảnh
        images = res.get("images")
        if isinstance(images, list) and len(images) > 0:
            valid_images = [
                _normalize_url(base_url, img)
                for img in images
                if _normalize_url(base_url, img)
            ]
            if valid_images:
                output["type"] = "slide"
                output["images"] = valid_images
                return output

        # Trường hợp Video
        video_url = play_url or hd_url
        if not video_url:
            return None

        output["video_url"] = video_url
        output["hd_video_url"] = hd_url
        return output

    except Exception as e:
        logger.warning("TikWM provider error for %s: %s", url, e)
        return None


# =========================================================
# PROVIDER 2: LOVETIK (Dự phòng - Chuyên trị Video)
# =========================================================
def api_lovetik(url: str) -> dict | None:
    try:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://lovetik.com",
            "Referer": "https://lovetik.com/",
        }

        response = http_session.post(
            "https://lovetik.com/api/ajax/search",
            data={"q": url},
            headers=headers,
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            return None

        links = data.get("links") or []
        video_url = None
        hd_url = None
        music_url = None

        for link in links:
            link_text = str(link.get("t") or "").lower()
            link_type = str(link.get("type") or "").lower()
            href = link.get("a")
            if not href:
                continue

            if "mp3" in link_type or "audio" in link_text or "music" in link_text:
                if not music_url:
                    music_url = href
            elif "hd" in link_text:
                hd_url = href
            elif "no watermark" in link_text or "nwm" in link_type:
                if not video_url:
                    video_url = href

        # Dự phòng nếu không khớp bộ lọc trên
        if not video_url:
            video_url = hd_url or (links[0].get("a") if links else None)

        # Kiểm tra nếu LoveTik trả về danh sách ảnh (Slide)
        images = data.get("images")
        if isinstance(images, list) and len(images) > 0:
            return {
                "id": str(data.get("vid") or abs(hash(url))),
                "title": (data.get("desc") or "TikTok Content").strip(),
                "author": data.get("author") or "Unknown",
                "music": music_url,
                "music_title": "TikTok Audio",
                "cover": data.get("cover"),
                "duration": 0,
                "type": "slide",
                "images": images,
                "source": "LoveTik",
            }

        if not video_url:
            return None

        return {
            "id": str(data.get("vid") or abs(hash(url))),
            "title": (data.get("desc") or "TikTok Content").strip(),
            "author": data.get("author") or "Unknown",
            "music": music_url,
            "music_title": "TikTok Audio",
            "cover": data.get("cover"),
            "duration": 0,
            "type": "video",
            "video_url": video_url,
            "hd_video_url": hd_url or video_url,
            "source": "LoveTik",
        }

    except Exception as e:
        logger.warning("LoveTik provider error for %s: %s", url, e)
        return None


# =========================================================
# CONTROLLER: ĐIỀU PHỐI LUÂN CHUYỂN
# =========================================================
def get_tiktok_data(url: str) -> dict | None:
    """Thử lần lượt các provider để lấy thông tin video/slide TikTok."""
    clean_url = extract_tiktok_url(url) or url.strip()
    providers = [api_tikwm, api_lovetik]

    for provider in providers:
        result = provider(clean_url)
        if result:
            logger.info("Fetched TikTok data via %s (id=%s)", result.get("source"), result.get("id"))
            return result

    return None
