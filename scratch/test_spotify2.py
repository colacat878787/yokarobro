import requests
import re
import json

def get_spotify(url):
    html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}).text
    with open('spotify.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Done")

get_spotify('https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M')
