from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time

# 曲のTunebatページのURLリスト（例：最大5～10曲までが安定）
tunebat_urls = [
    "https://tunebat.com/Info/with-ease-Joon/2TFUY0H6adpoF91yYi9Z74",
    # 他の曲のURLもここに追加
]

# 音響特徴量を抽出する関数（Seleniumでページ描画後に抽出）
def extract_features(url):
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(url)
        time.sleep(3)  # ページ描画待ち

        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()

        def get_value(label):
            divs = soup.find_all("div")
            for i in range(len(divs) - 1):
                if divs[i].text.strip() == label:
                    return divs[i + 1].text.strip()
            return "N/A"

        # タイトルとアーティストの抽出（titleタグから）
        title_tag = soup.find("title")
        title_text = title_tag.text if title_tag else "N/A"
        if " - " in title_text:
            parts = title_text.split(" - ")
            track_name = parts[0].strip()
            artist_name = parts[1].split("|")[0].strip()
        else:
            track_name = "N/A"
            artist_name = "N/A"

        return {
            "曲名": track_name,
            "アーティスト": artist_name,
            "URL": url,
            "BPM": get_value("BPM"),
            "Key": get_value("Key"),
            "Energy": get_value("Energy"),
            "Danceability": get_value("Danceability"),
            "Valence (Happiness)": get_value("Happiness")
        }

    except Exception as e:
        return {"URL": url, "Error": str(e)}

# 各曲の情報を順に取得（過負荷防止のため1秒sleep）
results = []
for url in tunebat_urls:
    features = extract_features(url)
    results.append(features)
    time.sleep(1)  # マナーとして必須

# データフレーム化＆表示
df = pd.DataFrame(results)
print(df)
