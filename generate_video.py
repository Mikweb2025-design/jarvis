import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import subprocess
import os
import json
import math
from pathlib import Path
import jarvis_musicgen

BASE = Path(__file__).parent
AVATAR_PATH = str(BASE / "holographic_avatar.png")
OUTPUT_DIR = str(BASE)
FRAMES_DIR = str(BASE / "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

avatar = Image.open(AVATAR_PATH).convert("RGBA")
W, H = avatar.size

def add_scanlines(img, intensity=0.08):
    arr = np.array(img, dtype=np.float32)
    for y in range(0, H, 3):
        arr[y, :, :3] *= (1 - intensity)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def add_glow(img, color=(0, 255, 255), radius=15):
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.rectangle([0, 0, W, H], outline=color + (80,), width=4)
    draw.rectangle([2, 2, W - 3, H - 3], outline=color + (40,), width=1)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=radius))
    return Image.alpha_composite(img, glow)

def add_hud_elements(img, t, phase=0):
    draw = ImageDraw.Draw(img, "RGBA")
    cyan = (0, 255, 255, 120)
    green = (0, 255, 0, 180)

    cx, cy = W // 2, H // 2

    for i in range(4):
        angle = phase + i * math.pi / 2
        r1, r2 = 300, 340
        x1 = cx + r1 * math.cos(angle)
        y1 = cy + r1 * math.sin(angle)
        x2 = cx + r2 * math.cos(angle)
        y2 = cy + r2 * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=cyan, width=1)

    draw.arc([cx - 350, cy - 350, cx + 350, cy + 350], 0, 360, fill=cyan, width=1)

    for i in range(6):
        angle = phase * 2 + i * math.pi / 3
        x = cx + 280 * math.cos(angle)
        y = cy + 280 * math.sin(angle)
        draw.point((int(x), int(y)), fill=green)

    return img

def draw_mouth_on_avatar(base_img, openness):
    img = base_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)

    cx, cy = W // 2, H // 2 + 60
    mouth_w = 60
    mouth_h = int(4 + openness * 28)

    mouth_y1 = cy - mouth_h // 2
    mouth_y2 = cy + mouth_h // 2

    color = (0, 255, 255, int(150 + 105 * openness))
    draw.ellipse(
        [cx - mouth_w // 2, mouth_y1, cx + mouth_w // 2, mouth_y2],
        fill=color, outline=(0, 255, 255, 200), width=2
    )

    if openness > 0.3:
        inner_h = int(mouth_h * 0.5)
        inner_y1 = cy - inner_h // 2
        inner_y2 = cy + inner_h // 2
        draw.ellipse(
            [cx - mouth_w // 3, inner_y1, cx + mouth_w // 3, inner_y2],
            fill=(0, 200, 255, 80)
        )

    return img

def generate_audio_edge(text, output_path):
    result = subprocess.run(
        ["edge-tts", "--voice", "en-US-JennyNeural", "--text", text, "--write-media", output_path],
        capture_output=True, text=True
    )
    return result.returncode == 0

def extract_audio_envelope(audio_path, num_frames):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=channels,sample_rate",
         "-of", "json", audio_path],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout)
    sr = int(info["streams"][0]["sample_rate"])
    channels = int(info["streams"][0]["channels"])

    duration_result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    duration = float(duration_result.stdout.strip())

    temp_wav = audio_path.replace(".mp3", "_temp.wav")
    subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ac", "1",
                    "-ar", str(sr), temp_wav], capture_output=True)

    import wave
    with wave.open(temp_wav, "rb") as wf:
        frames_data = wf.readframes(wf.getnframes())
        audio_arr = np.frombuffer(frames_data, dtype=np.int16).astype(np.float32)

    os.unlink(temp_wav)

    hop = max(1, len(audio_arr) // num_frames)
    envelope = []
    for i in range(0, len(audio_arr), hop):
        chunk = audio_arr[i:i + hop]
        envelope.append(float(np.sqrt(np.mean(chunk ** 2))))

    envelope = np.array(envelope[:num_frames])
    if len(envelope) < num_frames:
        envelope = np.pad(envelope, (0, num_frames - len(envelope)))

    max_val = envelope.max() if envelope.max() > 0 else 1
    envelope = envelope / max_val

    return envelope, duration

def main():
    text = "Hello. I am Jarvis, your artificial intelligence assistant. How can I help you today?"

    audio_path = os.path.join(OUTPUT_DIR, "jarvis_voice.mp3")
    print("Generating voice...")
    generate_audio_edge(text, audio_path)
    print("Voice generated.")

    fps = 24
    duration_sec = 5
    num_frames = fps * duration_sec

    envelope, audio_dur = extract_audio_envelope(audio_path, num_frames)

    print("Generating background music...")
    music_result = jarvis_musicgen.generate_music(
        "Cinematic background music for AI avatar video, subtle and atmospheric",
        duration=int(audio_dur) + 1,
        genre="cinematic"
    )
    music_path = music_result.get("local_path") or music_result.get("fallback", {}).get("local_path")
    if music_path and os.path.exists(music_path):
        print(f"Background music generated: {music_path}")
    else:
        print("Background music not available, proceeding without it")
        music_path = None

    os.makedirs(FRAMES_DIR, exist_ok=True)

    print(f"Generating {num_frames} frames...")
    for i in range(num_frames):
        t = i / fps
        openness = float(np.clip(envelope[i] * 1.8, 0.0, 1.0))
        phase = t * 0.5

        mouth_img = draw_mouth_on_avatar(avatar, openness)

        hud_img = add_hud_elements(mouth_img, t, phase)

        glow_img = add_glow(hud_img, color=(0, 200, 255), radius=12)

        scanline_img = add_scanlines(glow_img, intensity=0.06 + 0.04 * math.sin(t * 3))

        frame_path = os.path.join(FRAMES_DIR, f"frame_{i:04d}.png")
        scanline_img.save(frame_path)

        if i % (fps * 2) == 0:
            print(f"  Frame {i}/{num_frames}")

    print("Frames generated. Creating video...")

    video_path = os.path.join(OUTPUT_DIR, "holographic_avatar_animated.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(FRAMES_DIR, "frame_%04d.png"),
        "-i", audio_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-shortest",
        video_path
    ], capture_output=True)

    for f in os.listdir(FRAMES_DIR):
        os.unlink(os.path.join(FRAMES_DIR, f))
    os.rmdir(FRAMES_DIR)

    print(f"\nVideo saved to: {video_path}")

if __name__ == "__main__":
    main()
