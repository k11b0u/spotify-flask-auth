from flask import Flask, redirect, request
import requests, urllib.parse, json

app = Flask(__name__)

# ==== Spotifyアプリ情報 ====
CLIENT_ID = "7838a0cf003644ae8b5f3f75b9eb534e"
CLIENT_SECRET = "d2d93b5ce2b7403f91125a0ea8685697"
REDIRECT_URI = "https://spotify-flask-auth.onrender.com/callback"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# ==== プレイリストマッピング（自由に変更OK） ====
emotion_to_playlist = {
    "tension":  "https://open.spotify.com/playlist/6lEP2HI9ecRpSoHQNRTok7?si=d274100286104ac8",  # Deep Focus
    "relax":    "https://open.spotify.com/playlist/2m9HoHfpO0tk5eky1fopVu?si=8f63fa29aa524aac",  # Chill Vibes
    "depress":  "https://open.spotify.com/playlist/0TFRed2ZNnofW4uGxjytvT?si=88ce9ebba33c43f9",  # Life Sucks
}

# ==== ルート：Spotify認証にリダイレクト ====
@app.route("/")
def index():
    query = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "user-read-playback-state user-modify-playback-state",
    }
    auth_redirect = f"{AUTH_URL}?{urllib.parse.urlencode(query)}"
    return redirect(auth_redirect)

# ==== callback：アクセストークン・リフレッシュトークン取得 ====
@app.route("/callback")
def callback():
    code = request.args.get("code")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=data, headers=headers)

    if response.status_code == 200:
        token_info = response.json()
        access_token = token_info["access_token"]
        refresh_token = token_info["refresh_token"]

        with open("tokens.json", "w") as f:
            json.dump({
                "access_token": access_token,
                "refresh_token": refresh_token
            }, f, indent=2)

        return f"""
        <h2>✅ アクセストークン取得成功！</h2>
        <p><b>以下をコピーして使ってもOK：</b></p>
        <textarea rows="6" cols="100">{access_token}</textarea>
        <p>※ refresh_token は tokens.json に保存済みです</p>
        """
    else:
        return f"❌ トークン取得失敗: {response.status_code}<br>{response.text}"

# ==== トークン自動更新関数 ====
def refresh_access_token():
    with open("tokens.json", "r") as f:
        tokens = json.load(f)

    refresh_token = tokens["refresh_token"]

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=data, headers=headers)

    if response.status_code == 200:
        new_token = response.json()["access_token"]
        tokens["access_token"] = new_token

        with open("tokens.json", "w") as f:
            json.dump(tokens, f, indent=2)

        print("🔄 アクセストークンを更新しました")
        return new_token
    else:
        print(f"❌ 更新失敗: {response.status_code} {response.text}")
        return None

# ==== 再生テスト：感情に応じてプレイリストを再生 ====
@app.route("/play/<emotion>")
def play_music(emotion):
    playlist_uri = emotion_to_playlist.get(emotion)
    if not playlist_uri:
        return f"❌ 未定義の感情：{emotion}"

    access_token = refresh_access_token()

    # 手動でSpotifyアプリを起動し、デバイスをアクティブにしておくこと
    DEVICE_ID = "5ccf7df3476b07622cbff5277b7222aef4e43fa4"

    url = f"https://api.spotify.com/v1/me/player/play?device_id={DEVICE_ID}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "context_uri": playlist_uri,
        "offset": {"position": 0},
        "position_ms": 0
    }

    response = requests.put(url, headers=headers, json=data)

    if response.status_code == 204:
        return f"✅ 『{emotion}』 に対応するプレイリストを再生しました！"
    else:
        return f"❌ 再生失敗: {response.status_code} {response.text}"

@app.route("/download_tokens")
def download_tokens():
    try:
        with open("tokens.json", "r") as f:
            return f"<pre>{f.read()}</pre>"
    except FileNotFoundError:
        return "❌ tokens.json が見つかりません。まず認証を行ってください。"


# ==== ローカル用起動設定 ====
if __name__ == "__main__":
    app.run(debug=True, port=5000)
