import os
import asyncio
import csv
import time
import numpy as np
from bleak import BleakClient

# ==== 設定 ====
HR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
target_address = "E3:09:61:D7:D7:A8"  # ← あなたのCOOSPOのBLEアドレス
log_file = "emotion_log.csv"
rr_list = []

# ==== 初回のみ：ヘッダー行を作成 ====
if not os.path.exists(log_file):
    with open(log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "heart_rate", "rr_ms", "rmssd", "emotion"])

# ==== データ受信処理 ====
def handle_heart_rate(sender, data):
    global rr_list
    data = list(data)
    timestamp = time.time()

    if len(data) < 2:
        return

    hr_value = data[1]
    flags = data[0]
    rr_values = []

    # RR間隔が含まれるか確認（フラグの0x10ビット）
    if flags & 0x10:
        for i in range(2, len(data), 2):
            if i + 1 < len(data):
                rr = data[i] + (data[i + 1] << 8)
                rr_ms = rr / 1024 * 1000
                rr_values.append(rr_ms)
        if rr_values:
            rr_list.extend(rr_values)

    # HRV（RMSSD）計算
    rmssd = None
    if len(rr_list) >= 4:
        rr_array = np.array(rr_list[-10:])
        diff = np.diff(rr_array)
        rmssd = np.sqrt(np.mean(diff ** 2))

    # 感情分類
    emotion = "分類不能"
    if rmssd is not None:
        if hr_value >= 85 and rmssd < 30:
            emotion = "緊張系"
        elif hr_value <= 65 and rmssd < 30:
            emotion = "落ち込み系"
        elif rmssd >= 30:
            emotion = "鎮静系"

    # 表示
    print("🟢 HR:", hr_value, "bpm")
    if rr_values:
        print("📏 RR:", rr_values)
    if rmssd is not None:
        print(f"📈 RMSSD: {rmssd:.2f} → 感情: {emotion}")

    # ✅ ログ追記（RRもRMSSDも取得できたときのみ）
    if rr_values and rmssd is not None:
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                hr_value,
                rr_values,
                f"{rmssd:.2f}",
                emotion
            ])

# ==== メイン処理 ====
async def main():
    async with BleakClient(target_address) as client:
        print("✅ COOSPO接続成功、記録開始")
        await client.start_notify(HR_UUID, handle_heart_rate)
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("🛑 終了検出 → 通知停止")
            await client.stop_notify(HR_UUID)

asyncio.run(main())
