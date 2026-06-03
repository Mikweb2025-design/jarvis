#!/usr/bin/env python3
"""Genera video placeholder 'Un attimo, accendo i neuroni' usando Edge TTS + Wav2Lip."""
import sys, os, time, subprocess

sys.path.insert(0, os.path.dirname(__file__))

# 1. Edge TTS
text = "Un attimo, accendo i neuroni."
audio_path = "/tmp/waiting_neurons.mp3"
print(f"[waiting] Edge TTS: {text}")
t0 = time.time()
subprocess.run(
    ["edge-tts", "--voice", "it-IT-ElsaNeural", "--text", text, "--write-media", audio_path],
    capture_output=True, check=True
)
print(f"[waiting] TTS done in {time.time()-t0:.1f}s")

# 2. Convert to 16kHz mono WAV per Wav2Lip
wav_path = "/tmp/waiting_neurons.wav"
subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ac", "1", "-ar", "16000", wav_path],
               capture_output=True)

# 3. Wav2Lip
face_path = os.path.join(os.path.dirname(__file__), "holographic_avatar.png")
out_path = os.path.join(os.path.dirname(__file__), "waiting_neurons.mp4")
from wav2lip_run import run as wav2lip_run
print(f"[waiting] Wav2Lip...")
t0 = time.time()
wav2lip_run(face_path, wav_path, out_path, fps=20)
print(f"[waiting] Done in {time.time()-t0:.1f}s: {out_path}")
print(f"[waiting] Size: {os.path.getsize(out_path)} bytes")

# 4. Cleanup
os.unlink(audio_path)
os.unlink(wav_path)
