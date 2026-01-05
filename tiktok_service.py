import requests

# =========================================================
# 1. API GỐC (Ưu tiên số 1 - TikWM)
# =========================================================
def api_tikwm(url):
    try:
        # print("Debug: Đang thử TikWM...") # Dòng này chỉ hiện trong Log server, user không thấy
        response = requests.post("https://www.tikwm.com/api/", data={'url': url, 'hd': 1}, timeout=10)
        data = response.json()
        
        if data.get('code') != 0:
            return None
            
        res = data['data']
        output = {
            'id': res['id'],
            'title': res.get('title', 'TikTok Video'),
            'author': res['author']['nickname'],
            'music': res.get('music'),
            'cover': res.get('cover'),
            'type': 'video',
            'source': 'Server 1' # Đánh dấu nguồn (User không thấy, chỉ dùng để debug nếu cần)
        }

        if 'images' in res and res['images']:
            output['type'] = 'slide'
            output['images'] = res['images']
        else:
            output['video_url'] = res.get('hdplay') or res.get('play')
            
        return output
    except Exception:
        return None

# =========================================================
# 2. API DỰ PHÒNG (Backup - LoveTik)
# =========================================================
def api_lovetik(url):
    try:
        # print("Debug: TikWM lỗi, đang chuyển sang LoveTik...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        }
        payload = {'q': url}
        response = requests.post("https://lovetik.com/api/ajax/search", data=payload, headers=headers, timeout=10)
        data = response.json()

        if data.get('status') != 'ok':
            return None

        output = {
            'id': data.get('vid', 'unknown'),
            'title': data.get('desc', 'TikTok Video'),
            'author': data.get('author', 'Unknown'),
            'cover': data.get('cover'),
            'type': 'video',
            'source': 'Server 2'
        }

        # Lấy link video sạch từ LoveTik
        # LoveTik trả về nhiều link, ta cần tìm link nào không có watermark
        found_link = None
        for link in data.get('links', []):
            if 'no watermark' in link.get('t', '').lower() or 'nwm' in link.get('type', ''):
                found_link = link['a']
                break
        
        if not found_link and data.get('links'):
            found_link = data['links'][0]['a']

        if not found_link:
            return None

        output['video_url'] = found_link
        
        # LoveTik ít khi trả về link nhạc riêng, nên ta để None hoặc dùng link mặc định
        output['music'] = None 
        
        return output
    except Exception:
        return None

# =========================================================
# 3. LOGIC LUÂN CHUYỂN NGẦM (Controller)
# =========================================================

# Danh sách ưu tiên: TikWM đứng đầu, LoveTik đứng sau
PROVIDERS = [api_tikwm, api_lovetik]

def get_tiktok_data(url):
    """
    Hàm này sẽ im lặng thử từng server.
    Cái nào được thì lấy luôn, không báo gì cho người dùng.
    """
    for api_func in PROVIDERS:
        result = api_func(url)
        if result:
            return result
            
    # Nếu chạy hết vòng lặp mà không cái nào được thì mới trả về None
    return None