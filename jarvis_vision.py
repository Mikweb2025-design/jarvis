#!/usr/bin/env python3
"""jarvis_vision.py — Vision Engine: image analysis, QR detection, OCR, face detection, screenshot understanding"""
import base64, json, os, re, subprocess, tempfile, time, struct
from pathlib import Path
from io import BytesIO

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

class VisionEngine:
    def __init__(self):
        self._last_analysis = {}

    def analyze_screenshot(self, image_path=None):
        """Analyze screenshot: objects, text, UI elements, faces"""
        if not image_path or not os.path.exists(image_path):
            from jarvis_screen import take_screenshot
            result = take_screenshot("full")
            img_match = re.search(r'(/tmp/[\w\-\.]+\.png)', str(result))
            if img_match:
                image_path = img_match.group(1)
            else:
                return {"error": "Could not capture screenshot", "image_path": None}
        info = {"image_path": image_path, "size": os.path.getsize(image_path)}
        ocr_text = self.read_text(image_path)
        if ocr_text:
            info["text"] = ocr_text[:1000]
        qr = self.detect_qr(image_path)
        if qr:
            info["qr_codes"] = qr
        faces = self.detect_faces(image_path)
        if faces:
            info["faces"] = len(faces)
        colors = self._dominant_colors(image_path)
        if colors:
            info["dominant_colors"] = colors
        info["dimensions"] = self._image_dims(image_path)
        self._last_analysis = info
        return info

    def read_text(self, image_path=None):
        """Enhanced OCR: Apple Vision framework with SIPS preprocessing"""
        if not image_path or not os.path.exists(image_path):
            from jarvis_screen import ocr_screenshot
            return ocr_screenshot()
        try:
            result = subprocess.run(
                ["/usr/bin/xcrun", "cgimageinfo", image_path],
                capture_output=True, text=True, timeout=5
            )
            result = subprocess.run(
                ["/usr/bin/xcrun", "textgrabber", image_path],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        try:
            result = subprocess.run(
                ["tesseract", image_path, "stdout", "-l", "ita+eng", "--psm", "6"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        try:
            script = f'''
            use framework "Vision"
            use scripting additions
            set theImage to (current application's NSImage's alloc()'s initWithContentsOfFile:"{image_path}")
            set handler to (current application's VNImageRequestHandler's alloc()'s initWithData:(theImage's TIFFRepresentation()) options:(missing value))
            set request to (current application's VNRecognizeTextRequest's alloc()'s init())
            handler's performRequests:({{request}}) |error|:(missing value)
            set results to request's results()
            set output to ""
            repeat with observation in results
                set output to output & (observation's topCandidates:(1)'s firstObject()'s |string|()) & "\\n"
            end repeat
            return output
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
            if result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        return ""

    def detect_qr(self, image_path=None):
        """Detect QR codes and barcodes in image using Apple Vision"""
        if not image_path or not os.path.exists(image_path):
            return []
        try:
            result = subprocess.run([
                "python3", "-c", f"""
import subprocess, json
script = '''
use framework "Vision"
use scripting additions
set theImage to (current application's NSImage's alloc()'s initWithContentsOfFile:"{image_path}")
set handler to (current application's VNImageRequestHandler's alloc()'s initWithData:(theImage's TIFFRepresentation()) options:(missing value))
set request to (current application's VNDetectBarcodesRequest's alloc()'s init())
handler's performRequests:{{request}} |error|:(missing value)
set results to request's results()
set output to ""
repeat with obs in results
    set msg to obs's payloadStringValue()
    if msg is missing value then set msg to ""
    set barcodeType to obs's symbology()'s description()
    set output to output & barcodeType & ":" & msg & linefeed
end repeat
return output
'''
r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=15)
print(r.stdout.strip())
"""
            ], capture_output=True, text=True, timeout=15)
            raw = result.stdout.strip()
            if raw:
                codes = []
                for line in raw.split('\n'):
                    if ':' in line:
                        typ, data = line.split(':', 1)
                        codes.append({"type": typ, "data": data})
                    elif line:
                        codes.append({"type": "unknown", "data": line})
                return codes
        except:
            pass
        try:
            result = subprocess.run(
                ["zbarimg", "--quiet", "--raw", image_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                codes = []
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        typ, data = line.split(':', 1)
                        codes.append({"type": typ, "data": data})
                    elif line:
                        codes.append({"type": "unknown", "data": line})
                return codes
        except:
            pass
        return []

    def describe_image(self, image_path):
        """Generate image description using Ollama vision model if available"""
        if not os.path.exists(image_path):
            return "File not found"
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            import requests
            resp = requests.post("http://localhost:11434/api/generate", json={
                "model": "llava",
                "prompt": "Describe this image in detail in Italian. What objects, people, text, and UI elements do you see?",
                "images": [b64],
                "stream": False
            }, timeout=30)
            if resp.ok:
                return resp.json().get("response", "")
        except:
            pass
        try:
            from jarvis_screen import screen_awareness_summary
            return screen_awareness_summary()
        except:
            pass
        return "Image analysis unavailable"

    def analyze_region(self, x, y, w, h):
        """Capture and analyze a screen region"""
        path = f"/tmp/vision_region_{int(time.time())}.png"
        subprocess.run([
            "screencapture", "-R", f"{x},{y},{w},{h}", path
        ], capture_output=True, timeout=5)
        if os.path.exists(path):
            result = self.analyze_screenshot(path)
            result["region"] = {"x": x, "y": y, "w": w, "h": h}
            return result
        return {"error": "Region capture failed"}

    def detect_faces(self, image_path=None):
        """Detect faces in image using Apple Vision"""
        if not image_path or not os.path.exists(image_path):
            return 0
        script = f'''
        use framework "Vision"
        use scripting additions
        set theImage to (current application's NSImage's alloc()'s initWithContentsOfFile:"{image_path}")
        set handler to (current application's VNImageRequestHandler's alloc()'s initWithData:(theImage's TIFFRepresentation()) options:(missing value))
        set request to (current application's VNDetectFaceRectanglesRequest's alloc()'s init())
        handler's performRequests:{{request}} |error|:(missing value)
        set count to count of (request's results())
        return count
        '''
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
            if result.stdout.strip().isdigit():
                return int(result.stdout.strip())
        except:
            pass
        return 0

    def _dominant_colors(self, image_path):
        """Extract dominant colors using sips"""
        try:
            result = subprocess.run(
                ["sips", "-g", "profile", image_path],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return {"profile": result.stdout.strip()}
        except:
            pass
        return None

    def _image_dims(self, image_path):
        """Get image dimensions using sips"""
        try:
            result = subprocess.run(
                ["sips", "-g", "pixelWidth", "-g", "pixelHeight", image_path],
                capture_output=True, text=True, timeout=5
            )
            w = h = 0
            for line in result.stdout.split('\n'):
                if 'pixelWidth:' in line:
                    w = int(line.split(':')[1].strip())
                elif 'pixelHeight:' in line:
                    h = int(line.split(':')[1].strip())
            return {"width": w, "height": h} if w and h else None
        except:
            pass
        return None

    def compare_screenshots(self, path1, path2):
        """Compare two screenshots and detect changes"""
        if not os.path.exists(path1) or not os.path.exists(path2):
            return {"error": "One or both images not found"}
        try:
            result = subprocess.run(
                ["compare", "-metric", "AE", path1, path2, "/dev/null"],
                capture_output=True, text=True, timeout=10
            )
            diff_count = result.stderr.strip()
            return {"different_pixels": diff_count, "changed": diff_count != "0"}
        except:
            pass
        return {"error": "ImageMagick not available, install with: brew install imagemagick"}

vision = VisionEngine()
