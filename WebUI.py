from flask import Flask, render_template, jsonify
import pandas as pd
import os

app = Flask(__name__)

LOG_FILE = "emotion_log.csv"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    if not os.path.exists(LOG_FILE):
        return jsonify([])

    df = pd.read_csv(LOG_FILE, encoding="utf-8")

    # JST変換（日本時間に変換して「月/日 時:分」形式で出力）
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Tokyo")
    df["timestamp"] = df["timestamp"].dt.strftime("%m/%d %H:%M")

    # 数値化・NaN対策
    df["heart_rate"] = pd.to_numeric(df["heart_rate"], errors="coerce")
    df["rmssd"] = pd.to_numeric(df["rmssd"], errors="coerce").fillna(0)

    data = {
        "labels": df["timestamp"].tolist(),
        "heart_rate": df["heart_rate"].tolist(),
        "rmssd": df["rmssd"].tolist(),
        "emotion": df["emotion"].tolist()
    }
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
