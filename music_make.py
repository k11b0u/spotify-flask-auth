import os
import random
import numpy as np
import soundfile as sf
from transformers import pipeline
import torch

# 保存先
os.makedirs("output", exist_ok=True)

# GPUが使える場合はcuda:0、なければcpu
device = 0 if torch.cuda.is_available() else -1

# MusicGenパイプライン（GPU指定！）
pipe = pipeline("text-to-audio", model="facebook/musicgen-small", device=device)

preset_prompts = {
    "relax": [
        "lo-fi beats, acoustic guitar, 60 BPM, gentle melody, background textures, relaxing",
        "soft piano, ambient pad, 60 BPM, warm and mellow, peaceful",
        "chill synth, electric piano, 60 BPM, vinyl noise, soft rhythm, comfort"
    ],
    "uplift": [
        "hard techno groove, powerful 4/4 kick, deep bassline, percussive synths, club atmosphere",
        "energetic techno, pounding kick drum, hypnotic synth arpeggios, minimal electronic, warehouse vibe",
        "fast-paced techno, metallic percussion, driving rhythm, futuristic synth stabs, underground party",
        "upbeat techno track, pulsing bass, shimmering hi-hats, repetitive electronic motifs, dancefloor energy",
        "intense techno, sharp drum machine, evolving synth textures, relentless tempo, rave feeling"
    ],
    "sad": [
        "melancholic piano, 70 BPM, expressive, cinematic, gentle sadness",
        "ambient guitar, slow delay, 70 BPM, minimal, delicate, rain sounds"
    ]
}

num_per_emotion = {
    "relax": 3,
    "uplift": 2,
    "sad": 2
}

for emotion, prompts in preset_prompts.items():
    for i in range(num_per_emotion[emotion]):
        prompt = random.choice(prompts)
        print(f"{emotion} のプリセットBGM {i+1}曲目生成: {prompt}")
        audio = pipe(prompt, forward_params={"do_sample": True, "max_new_tokens": 1024})
        if isinstance(audio, list):
            audio = audio[0]
        audio_data = np.squeeze(audio["audio"])
        # ショートフェードでつなぎも滑らかに
        def fade(data, fade_len=3000):
            if data.dtype != np.float32 and data.dtype != np.float64:
                data = data.astype(np.float32)
            fadein = np.linspace(0, 1, min(fade_len, len(data)))
            fadeout = np.linspace(1, 0, min(fade_len, len(data)))
            data[:len(fadein)] *= fadein
            data[-len(fadeout):] *= fadeout
            return data
        audio_data = fade(audio_data)
        sf.write(f"output/loop_{emotion}{i+1}.wav", (audio_data * 32767).astype(np.int16), audio["sampling_rate"])
        print(f"output/loop_{emotion}{i+1}.wav 保存完了！\n")
