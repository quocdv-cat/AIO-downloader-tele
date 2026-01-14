import requests

def get_cobalt_data(url):
    """
    Sử dụng Cobalt API để tải YouTube, Facebook, Instagram...
    Docs: https://github.com/imputnet/cobalt
    """
    # Sử dụng public instance của Cobalt (hoặc tự host nếu muốn)
    api_url = "https://api.cobalt.tools/api/json"
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; MyTelegramBot/1.0)"
    }
    
    payload = {
        "url": url,
        "vCodec": "h264",    # Codec phổ biến để Telegram đọc được
        "vQuality": "720",   # Chọn 720p để cân bằng dung lượng (tránh >50MB)
        "aFormat": "mp3",    # Định dạng âm thanh
        "isAudioOnly": False
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        data = response.json()

        # Cobalt trả về nhiều trạng thái, cần kiểm tra kỹ
        if data.get('status') == 'error':
            return None
        
        # Cobalt thường trả về link trực tiếp (stream) hoặc link picker
        download_url = data.get('url')
        if not download_url and data.get('picker'):
            # Nếu có nhiều lựa chọn, lấy cái đầu tiên
            download_url = data['picker'][0]['url']
            
        if not download_url:
            return None

        return {
            'type': 'video', # Cobalt chủ yếu trả về video
            'video_url': download_url,
            'title': data.get('filename', 'Video Downloaded'), # Cobalt đôi khi không trả tên
            'author': 'Social Platform'
        }

    except Exception as e:
        print(f"Lỗi Cobalt: {e}")
        return None