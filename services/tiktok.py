import requests

# =========================================================
# PROVIDER 1: TIKWM (Ưu tiên số 1 - Hỗ trợ cả Video & Slide)
# =========================================================
def api_tikwm(url):
    try:
        response = requests.post("https://www.tikwm.com/api/", data={'url': url, 'hd': 1}, timeout=10)
        data = response.json()
        
        if data.get('code') != 0:
            return None
            
        res = data['data']
        output = {
            'id': res['id'],
            'title': res.get('title', 'TikTok Content'),
            'author': res['author']['nickname'],
            'music': res.get('music'),
            'type': 'video', # Mặc định
            'source': 'TikWM'
        }

        # Kiểm tra Slide ảnh
        if 'images' in res and res['images']:
            output['type'] = 'slide'
            output['images'] = res['images']
        else:
            output['video_url'] = res.get('hdplay') or res.get('play')
            
        return output
    except Exception:
        return None

# =========================================================
# PROVIDER 2: LOVETIK (Dự phòng - Chuyên trị Video)
# =========================================================
def api_lovetik(url):
    try:
        # LoveTik yêu cầu giả lập trình duyệt (User-Agent)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        
        response = requests.post("https://lovetik.com/api/ajax/search", data={'q': url}, headers=headers, timeout=10)
        data = response.json()

        if data.get('status') != 'ok':
            return None

        output = {
            'id': data.get('vid', 'unknown_id'),
            'title': data.get('desc', 'TikTok Content'),
            'author': data.get('author', 'Unknown'),
            'music': None, # LoveTik ít khi tách nhạc riêng
            'type': 'video',
            'source': 'LoveTik'
        }

        # Tìm link download không logo (no watermark)
        video_url = None
        for link in data.get('links', []):
            # Ưu tiên link có chữ 'no watermark'
            if 'no watermark' in link.get('t', '').lower() or 'nwm' in link.get('type', ''):
                video_url = link.get('a')
                break
        
        # Nếu không tìm thấy, lấy đại link đầu tiên
        if not video_url and data.get('links'):
            video_url = data['links'][0].get('a')
            
        if not video_url:
            return None

        output['video_url'] = video_url
        return output

    except Exception:
        return None

# =========================================================
# CONTROLLER: ĐIỀU PHỐI LUÂN CHUYỂN
# =========================================================
def get_tiktok_data(url):
    # Danh sách các API theo thứ tự ưu tiên
    providers = [api_tikwm, api_lovetik]
    
    for provider in providers:
        # Thử từng cái một
        result = provider(url)
        if result:
            # Nếu thành công thì trả về ngay
            return result
            
    # Nếu chạy hết danh sách mà vẫn lỗi
    return None