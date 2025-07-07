import os
import threading
import time
import random
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import traceback
from transformers import pipeline

# ================ 基本設定 ================
os.makedirs("output", exist_ok=True)
device = 0 if torch.cuda.is_available() else -1
pipe = pipeline("text-to-audio", model="facebook/musicgen-small", device=device)

emotions = ["uplift", "relax", "sad"]
EMOTION_INTERVAL = 360  # 6分（360秒）

preset_files = {
    "uplift": ["output/loop_uplift1.wav", "output/loop_uplift2.wav"],
    "relax":  ["output/loop_relax1.wav",  "output/loop_relax2.wav" ],
    "sad":    ["output/loop_sad1.wav",    "output/loop_sad2.wav"   ]
}

emotion_parts = {
    "uplift": [
        ("intro",  "moody hiphop intro, dark jazz chords, laid-back groove, 90 BPM, anxious, urban vibe"),
        ("verse",  "hiphop verse, tight beats, jazzy keys, tense atmosphere, 100 BPM, restless, modern"),
        ("chorus", "energetic hiphop chorus, sharp snare, electric piano, cool but edgy, 110 BPM, stylish tension"),
        ("outro",  "jazzy outro, minor chords, mellow hiphop beat, slow 90 BPM, anxious, night city")
    ],
    "relax": [
        ("intro",  "lofi intro, chill R&B guitar, vinyl noise, slow 60 BPM, peaceful, gentle, elegant"),
        ("verse",  "smooth jazz verse, soft lofi beat, rhodes piano, 70 BPM, warm, comfortable, stylish"),
        ("chorus", "happy chorus, mellow R&B chords, groovy lofi drums, 90 BPM, uplifting, elegant, positive"),
        ("outro",  "relaxing outro, soft jazz guitar, slow fade, 60 BPM, gentle, beautiful, calm")
    ],
    "sad": [
        ("intro",  "melancholic intro, soft jazz piano, rainy ambience, slow 60 BPM, emotional, lonely"),
        ("verse",  "sad lofi verse, gentle electric piano, sparse R&B drums, 70 BPM, sentimental, night mood"),
        ("chorus", "emotional chorus, jazzy chords, smooth R&B vocals, 80 BPM, deep, beautiful, soulful"),
        ("outro",  "lonely outro, faded jazz guitar, echoing piano, slow 60 BPM, sorrowful, quiet ending")
    ]
}

def fade(data, fade_len=3000):
    if data.dtype != np.float32 and data.dtype != np.float64:
        data = data.astype(np.float32)
    fadein = np.linspace(0, 1, min(fade_len, len(data)))
    fadeout = np.linspace(1, 0, min(fade_len, len(data)))
    data[:len(fadein)] *= fadein
    data[-len(fadeout):] *= fadeout
    return data

def crossfade(a, b, fade_len=3000):
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    fade_len = min(fade_len, len(a), len(b))
    fade_out = np.linspace(1, 0, fade_len)
    fade_in = np.linspace(0, 1, fade_len)
    cross = a[-fade_len:] * fade_out + b[:fade_len] * fade_in
    return np.concatenate([a[:-fade_len], cross, b[fade_len:]])

def musicgen_generate_story(emotion, tokens=1024):
    parts = emotion_parts[emotion]
    segs = []
    sample_rate = None
    for name, prompt in parts:
        try:
            print(f"{emotion}: {name} 生成中: {prompt}")
            audio = pipe(prompt, forward_params={"do_sample": True, "max_new_tokens": tokens})
            if isinstance(audio, list):
                audio = audio[0]
            data = np.squeeze(audio["audio"])
            data = fade(data)
            segs.append(data)
            sample_rate = audio["sampling_rate"]
        except Exception as e:
            print(f"=== {emotion}: {name} の生成で例外発生 ===")
            print(traceback.format_exc())
            segs.append(np.zeros(32000, dtype=np.float32))
            sample_rate = 32000
    song = segs[0]
    for seg in segs[1:]:
        song = crossfade(song, seg)
    return song, sample_rate

class SegmentBuffer:
    def __init__(self):
        self.buffer = []
        self.lock = threading.Lock()
        self.emotion = emotions[0]
        self.running = True
        self.rate = None

    def append(self, seg, rate):
        with self.lock:
            self.buffer.append(seg)
            self.rate = rate

    def pop(self):
        with self.lock:
            if self.buffer:
                return self.buffer.pop(0)
            else:
                return None

    def clear(self):
        with self.lock:
            self.buffer = []

def background_generate(buffer: SegmentBuffer):
    while buffer.running:
        emotion = buffer.emotion
        try:
            print(f"AI曲（物語型）を生成中...（emotion={emotion}）")
            audio_data, rate = musicgen_generate_story(emotion, tokens=1024)
            print(f"[DEBUG] 生成AI曲データ型: {type(audio_data)}, shape: {audio_data.shape}")
            print(f"[DEBUG] サンプリングレート: {rate}")
            buffer.append(audio_data, rate)
        except Exception as e:
            print("=== AI曲生成で例外発生 ===")
            print(traceback.format_exc())
        while buffer.running and buffer.emotion == emotion and buffer.buffer:
            time.sleep(1)

def play_preset_bgm_crossfade_random(emotion, rate, fade_len=3000, stop_event=None):
    file_list = preset_files[emotion]
    last_idx = -1
    play_rate = rate or 32000
    while True:
        idx_candidates = [i for i in range(len(file_list)) if i != last_idx]
        idx = random.choice(idx_candidates)
        data, bgm_rate = sf.read(file_list[idx])
        if data.dtype != np.float32 and data.dtype != np.float64:
            data = data.astype(np.float32)
        if play_rate is None:
            play_rate = bgm_rate
        if last_idx != -1:
            last_data, _ = sf.read(file_list[last_idx])
            if last_data.dtype != np.float32 and last_data.dtype != np.float64:
                last_data = last_data.astype(np.float32)
            seg_cf = crossfade(last_data, data, fade_len)
        else:
            seg_cf = fade(data, fade_len)
            seg_cf = fade(seg_cf, fade_len)
        sd.play(seg_cf, play_rate)
        start = time.time()
        duration = len(seg_cf) / play_rate
        while time.time() - start < duration:
            if stop_event and stop_event.is_set():
                sd.stop()
                return
            time.sleep(0.1)
        if stop_event and stop_event.is_set():
            sd.stop()
            return
        last_idx = idx

def next_emotion_idx(idx):
    return (idx + 1) % len(emotions)

segment_buffer = SegmentBuffer()
bg_thread = threading.Thread(target=background_generate, args=(segment_buffer,), daemon=True)
bg_thread.start()

cur_emotion_idx = 0
cur_emotion = emotions[cur_emotion_idx]
next_change_time = time.time() + EMOTION_INTERVAL

last_ai_track = None
last_ai_rate = None

try:
    while True:
        now = time.time()
        if now >= next_change_time:
            cur_emotion_idx = next_emotion_idx(cur_emotion_idx)
            cur_emotion = emotions[cur_emotion_idx]
            next_change_time = now + EMOTION_INTERVAL
            segment_buffer.clear()
            segment_buffer.emotion = cur_emotion
            last_ai_track = None
            print(f"\n感情切り替え: {cur_emotion}\n")

        if last_ai_track is not None:
            print(f"AI生成曲を再生（感情: {cur_emotion}）")
            sd.play(last_ai_track, last_ai_rate)
            sd.wait()
            while time.time() < next_change_time:
                print("AI曲をリピート再生中…")
                sd.play(last_ai_track, last_ai_rate)
                sd.wait()
                if time.time() >= next_change_time:
                    break
            last_ai_track = None
        else:
            seg = segment_buffer.pop()
            print(f"[DEBUG] popしたデータ: {type(seg)}, None? {seg is None}")
            if seg is not None:
                last_ai_track = seg
                last_ai_rate = segment_buffer.rate
                continue
            print("生成待ち→プリセットBGMランダムクロスフェード再生")
            stop_event = threading.Event()
            th = threading.Thread(target=play_preset_bgm_crossfade_random,
                                  args=(cur_emotion, segment_buffer.rate, 3000, stop_event))
            th.start()
            while last_ai_track is None and time.time() < next_change_time:
                seg = segment_buffer.pop()
                print(f"[DEBUG] popしたデータ（待機ループ）: {type(seg)}, None? {seg is None}")
                if seg is not None:
                    last_ai_track = seg
                    last_ai_rate = segment_buffer.rate
                    break
                time.sleep(0.5)
            stop_event.set()
            th.join()
except KeyboardInterrupt:
    segment_buffer.running = False
    sd.stop()
    print("終了")
