import requests
import re
import json

def get_spotify(url):
    html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
    
    # 找尋 meta tags
    matches = re.findall(r'<meta name="music:song" content="(https://open\.spotify\.com/track/[a-zA-Z0-9]+)"', html)
    print("Found track URLs:", len(matches))
    
    if len(matches) > 0:
        return matches

get_spotify('https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M')
