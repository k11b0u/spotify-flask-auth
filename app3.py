from flask import Flask, redirect, request
import requests
import urllib.parse

app = Flask(__name__)

# === Spotifyアプリ情報（あなたのIDとSecretを入れてください） ===
CLIENT_ID = "7838a0cf003644ae8b5f3f75b9eb534e"
CLIENT_SECRET = "d2d93b5ce2b7403f91125a0ea8685697"
REDIRECT_URI = "https://spotify-flask-app-pduk.onrender.com/callback"  # ← ここ重要

SCOPE = "user-read-playback-state user-modify-playback-state"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# === グローバルトークン保存用 ===
global_token = None

@app.route("/")
def index():
    query = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    }
    auth_redirect = f"{AUTH_URL}?{urllib.parse.urlencode(query)}"
    return redirect(auth_redirect)

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
        return f"""
        <h2>✅ アクセストークン取得成功！</h2>
        <p><b>以下をコピーして使ってください：</b></p>
        <textarea rows="6" cols="100">{access_token}</textarea>
        <br><br>
        <p>（このトークンは1時間有効です）</p>
        """
    else:
        return f"❌ トークン取得失敗: {response.status_code}<br>{response.text}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # Render用に公開ポートを指定
