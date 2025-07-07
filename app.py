import os
import threading
import time
import random
import numpy as np
import sounddevice as sd
import soundfile as sf
from transformers import pipeline

# ========== 設定 ==========
emotions = ["relax", "uplift", "sad"]
loop_files = {
    "relax": ["output/loop_relax1.wav", "output/loop_relax2.wav", "output/loop_relax3.wav"],
    "uplift": ["output/loop_uplift1.wav", "output/loop_uplift2.wav"],
    "sad": ["output/loop_sad1.wav", "output/loop_sad2.wav"]
}

musicgen_pipe = pipeline("text-to-audio", model="facebook/musicgen-small",device=0)

# 「進化的プロンプト」構成：イントロ→盛り上がり→落ち着き…など
progress_variants = {
    "relax": [
        "intro: chill R&B, mellow chords, smooth beats, lofi, gentle pads",
        "add jazzy harmonies, soft hiphop drums, warm textures, soulful feel",
        "subtle groove, relaxing lofi elements, lush Rhodes, airy vocals",
        "texture evolves, laid-back rhythm, chillhop flow, calming synths",
        "fade to gentle outro, dreamy lofi, soft R&B chords, peaceful"
    ],
    "uplift": [
        "intro: energetic hiphop beat, bright synth, urban vibe, groovy bass",
        "techno groove, driving rhythm, punchy drums, synth arpeggios",
        "house music drop, strong 4/4 kick, electronic hooks, club feeling",
        "trap-influenced section, modern hi-hats, EDM build-up, massive drop",
        "fade out with positive techno riff, catchy hiphop hook, uplifting"
    ],
    "sad": [
        "intro: sparse piano, lots of space",
        "strings enter, gentle sadness, cinematic",
        "melody develops, subtle harmony changes",
        "slight intensification, deeper emotion",
        "return to solo piano, reflective ending"
    ]
}
evolution_steps = 5

# ====== 進化型プロンプト自動生成 ======
mood_base = {
    "relax": ["gentle", "warm", "lo-fi", "soft", "nature", "ambient","acoustic", "peaceful", "mellow", "R&B", "soul", "chill", "jazzy", "lofi beats", "dreamy"],
    "uplift": ["hiphop", "techno", "house", "pop", "energy", "groovy", "happy","rhythmic", "dance", "uplifting", "fun", "EDM", "trap", "electronic", "club"],
    "sad": ["melancholic", "cinematic", "minimal", "slow", "reflective", "emotional", "nostalgic", "rainy"]
}

def dynamic_progress_prompt(emotion, step, prev_keywords=None):
    extra = random.sample(mood_base[emotion], 2)
    stage = progress_variants[emotion][step]
    prompt = f"{emotion} music, 60-90 BPM, {stage}, {', '.join(extra)}"
    if prev_keywords:
        prompt += ", " + prev_keywords
    return prompt

# ========== フェード・クロスフェード ==========
def fade_in(data, fade_len=5000):
    if data.dtype != np.float32 and data.dtype != np.float64:
        data = data.astype(np.float32)
    fade = np.linspace(0, 1, min(fade_len, len(data)))
    data[:len(fade)] *= fade
    return data

def fade_out(data, fade_len=5000):
    if data.dtype != np.float32 and data.dtype != np.float64:
        data = data.astype(np.float32)
    fade = np.linspace(1, 0, min(fade_len, len(data)))
    data[-len(fade):] *= fade
    return data

def crossfade_segments(seg1, seg2, fade_len=5000):
    seg1 = seg1.astype(np.float32)
    seg2 = seg2.astype(np.float32)
    fade_len = min(fade_len, len(seg1), len(seg2))
    fade_out_curve = np.linspace(1, 0, fade_len)
    fade_in_curve = np.linspace(0, 1, fade_len)
    cross = seg1[-fade_len:] * fade_out_curve + seg2[:fade_len] * fade_in_curve
    return np.concatenate([seg1[:-fade_len], cross, seg2[fade_len:]])

# ========== 進化型MusicGen生成 ==========（ここが進化！）
def musicgen_generate_evolution(emotion, tokens=1024):
    """進化的プロンプトで複数セグメント生成し連結。進化を感じる曲に！"""
    progress_list = progress_variants[emotion]
    segs = []
    rate = None
    prev_keywords = ""
    for idx, stage in enumerate(progress_list):
        prompt = dynamic_progress_prompt(emotion, idx, prev_keywords)
        print(f"MusicGen進化生成 {idx+1}/{len(progress_list)}: {prompt}")
        audio = musicgen_pipe(prompt, forward_params={"do_sample": True, "max_new_tokens": tokens})
        if isinstance(audio, list):
            audio = audio[0]
        audio_data = np.squeeze(audio["audio"])
        audio_data = fade_in(audio_data)
        audio_data = fade_out(audio_data)
        if rate is None:
            rate = audio["sampling_rate"]
        segs.append(audio_data)
        # 今回のextraキーワードを次回にも引き継ぐ（より有機的な進化へ）
        prev_keywords = ", ".join(random.sample(mood_base[emotion], 2))
    # セグメントをcrossfadeで順につなぐ
    full = segs[0]
    for s in segs[1:]:
        full = crossfade_segments(full, s)
    return full, rate

# ========== 感情切り替え/バッファ/再生系（ここは前回のまま） ==========

def get_current_emotion():
    t = int(time.time() / 360) % len(emotions)
    return emotions[t]

class SegmentBuffer:
    def __init__(self):
        self.buffer = []
        self.lock = threading.Lock()
        self.emotion = get_current_emotion()
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
        now_emotion = get_current_emotion()
        if now_emotion != buffer.emotion:
            print(f"感情 {buffer.emotion}→{now_emotion} に切り替わりました（バッファ消去）")
            buffer.clear()
            buffer.emotion = now_emotion
        print(f"新しい進化型AI曲を生成中...（emotion={buffer.emotion}）")
        audio_data, rate = musicgen_generate_evolution(buffer.emotion, tokens=1024)
        buffer.append(audio_data, rate)
        time.sleep(2)

def play_preset_bgm_crossfade_random(emotion, rate, fade_len=5000, stop_event=None):
    file_list = loop_files[emotion]
    last_idx = -1
    play_rate = rate
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
            seg_cf = crossfade_segments(last_data, data, fade_len)
        else:
            seg_cf = fade_in(data, fade_len)
            seg_cf = fade_out(seg_cf, fade_len)
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

os.makedirs("output", exist_ok=True)
segment_buffer = SegmentBuffer()
bg_thread = threading.Thread(target=background_generate, args=(segment_buffer,), daemon=True)
bg_thread.start()

try:
    while True:
        seg = segment_buffer.pop()
        if seg is not None:
            print(f"AI進化曲を再生（buffer残り={len(segment_buffer.buffer)}）")
            sd.play(seg, segment_buffer.rate)
            sd.wait()
        else:
            print("生成待ち→多曲ランダムクロスフェードBGM再生")
            stop_event = threading.Event()
            th = threading.Thread(target=play_preset_bgm_crossfade_random,
                                  args=(get_current_emotion(), segment_buffer.rate, 5000, stop_event))
            th.start()
            while segment_buffer.pop() is None:
                time.sleep(0.5)
            stop_event.set()
            th.join()
except KeyboardInterrupt:
    segment_buffer.running = False
    sd.stop()
    print("終了")
