import urllib.request
try:
    req = urllib.request.Request('https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M', headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, timeout=10).read().decode()
    print("Downloaded HTML length:", len(html))
    with open('spotify_embed.html', 'w', encoding='utf-8') as f:
        f.write(html)
except Exception as e:
    print(e)
