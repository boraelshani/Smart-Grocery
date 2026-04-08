import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# Simple memory cache to speed things up and avoid redundant requests
CACHE = {}

def fetch_bing_image(query):
    """
    Fetches the highest quality, unwatermarked food photography
    URL for a given recipe dynamically from Bing Images.
    """
    q = query.lower().strip()
    if not q:
        return None
        
    if q in CACHE:
        return CACHE[q]
    
    try:
        # Ask explicitly for 'food photography' or 'recipe dish'
        url = f"https://www.bing.com/images/search?q={urllib.parse.quote(q + ' recipe dish food photography')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=5)
        
        # Bing embeds media urls as `murl":"https://domain.com/img.jpg"`
        murls = re.findall(r'murl&quot;:&quot;([^&"]+)&quot;', res.text)
        
        for murl in murls:
            lower_url = murl.lower()
            # Skip tiny thumbnails, watermarked sites, and Pinterest (since it blocks hotlinking frequently)
            if any(x in lower_url for x in ['150x150', '200x150', 'shutterstock', 'istock', 'alamy', '123rf', 'pinterest', 'pinimg']):
                continue
            if lower_url.endswith('.jpg') or lower_url.endswith('.png') or lower_url.endswith('.jpeg'):
                CACHE[q] = murl
                return murl
        
        # Fallback
        if murls:
            CACHE[q] = murls[0]
            return murls[0]
            
    except Exception as e:
        print(f"Bing scrape failed for {q}: {e}")
        pass
    
    return None
