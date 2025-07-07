import os
import numpy as np
from transformers import pipeline
import soundfile as sf
import sounddevice as sd
import traceback

try:
    # ===== プロンプトと設定 =====
    prompt = "calm and relaxing ambient music, soft piano and gentle atmosphere"
    duration = 10    # 1曲の長さ（秒）
    num_segments = 3 # つなげたい曲数

    os.makedirs("output", exist_ok=True)
    segment_files = []

    # 1. MusicGenで音楽を生成＆保存
    pipe = pipeline("text-to-audio", model="facebook/musicgen-small")

    for i in range(num_segments):
        print(f"Generating segment {i+1} / {num_segments} ...")
        audio = pipe(prompt, forward_params={"do_sample": True, "max_new_tokens": int(duration * 50)})
        print(f"audio['audio'] type: {type(audio['audio'])}")
        print(f"audio['audio'] shape: {np.array(audio['audio']).shape}")
        audio_data = np.array(audio["audio"])
        # 2次元の場合は1次元にする
        if audio_data.ndim > 1:
            audio_data = audio_data.squeeze()
        # float32 → int16に変換して保存
        audio_int16 = (audio_data * 32767).astype(np.int16)
        fname = f"output/music_{i+1:03d}.wav"
        sf.write(fname, audio_int16, audio["sampling_rate"])
        segment_files.append(fname)
    print("各セグメントの音楽ファイルを保存しました。")


    # 2. 複数WAVをつなげる
    audios = []
    for fname in segment_files:
        data, rate = sf.read(fname)
        audios.append(data)
    merged = np.concatenate(audios, axis=0)
    merged_path = "output/merged.wav"
    sf.write(merged_path, merged, rate)
    print("全セグメントを連結 → merged.wavとして保存しました。")

    # 3. 音楽を再生
    print("再生中 ...")
    data, samplerate = sf.read(merged_path)
    sd.play(data, samplerate)
    sd.wait()
    print("再生終了！")

except Exception as e:
    print("===== 例外発生 =====")
    print(e)
    input("Enterキーで終了します")
