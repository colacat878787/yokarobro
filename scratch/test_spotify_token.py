import requests

html = requests.get('https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M', headers={'User-Agent': 'Mozilla/5.0'}).text
try:
    token = html.split('accessToken":"')[1].split('"')[0]
    print("Token found:", token[:10] + "...")
    r = requests.get("https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks", headers={"Authorization": f"Bearer {token}"})
    print(r.status_code)
    data = r.json()
    for i, item in enumerate(data.get('items', [])[:5]):
        t = item.get('track', {})
        print(f"{i+1}. {t.get('name')} - {t.get('artists', [{}])[0].get('name')}")
except Exception as e:
    print("Error:", e)
