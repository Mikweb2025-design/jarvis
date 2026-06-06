#!/usr/bin/env python3
"""jarvis_wake.py — wake word locale + dictation mode v3.0
Usa faster-whisper + sounddevice + Quartz event tap.
Niente cloud, niente API key."""
import subprocess, sys, threading, time, os, math, json, queue, struct, difflib
from pathlib import Path

_WHISPER_MODEL = None
_MODEL_LOCK = threading.Lock()

def _get_whisper():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        with _MODEL_LOCK:
            if _WHISPER_MODEL is None:
                from faster_whisper import WhisperModel
                _WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
                try:
                    _WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
                except:
                    _WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _WHISPER_MODEL

def _transcribe(audio_bytes, sample_rate=16000):
    import numpy as np
    arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if len(arr) == 0: return ""
    model = _get_whisper()
    segs, _ = model.transcribe(arr, beam_size=1, language=None)
    return " ".join(s.text.strip() for s in segs).strip()

def _rms(data):
    if len(data) < 2: return 0
    samples = struct.unpack(f"{len(data)//2}h", data[:len(data)//2*2])
    return math.sqrt(sum(s*s for s in samples) / len(samples))

def _paste_text(text):
    subprocess.run(["pbcopy"], input=text.encode("utf-8"))
    subprocess.run(["osascript", "-e",
        'tell application "System Events" to keystroke "v" using command down'])

class JarvisWake:
    def __init__(self, chat_callback=None, log_callback=None):
        self.chat_callback = chat_callback
        self.log_callback = log_callback
        self.running = False
        self._threads = []
        self._dictating = False
        self._dictate_queue = queue.Queue()

    def log(self, msg):
        if self.log_callback: self.log_callback(msg)
        else:
            print(f"[Wake] {msg}")
            sys.stdout.flush()

    def start(self):
        self.running = True
        t1 = threading.Thread(target=self._wake_loop, daemon=True, name="wake-loop")
        t2 = threading.Thread(target=self._dictate_hotkey, daemon=True, name="dictate-hotkey")
        t3 = threading.Thread(target=self._dictate_worker, daemon=True, name="dictate-worker")
        t1.start(); t2.start(); t3.start()
        self._threads = [t1, t2, t3]
        self.log("Wake word + Dictation avviati (tasto Option per dettatura)")
        return True

    def stop(self):
        self.running = False

    def _wake_loop(self):
        """Ascolto continuo: VAD → whisper → keyword spotting 'jarvis'"""
        try:
            import sounddevice as sd
        except ImportError:
            self.log("sounddevice non installato")
            return

        devices = sd.query_devices()
        default_input = sd.default.device
        self.log(f"Dispositivo input default: {default_input} — {sd.query_devices(default_input, 'input')['name'] if default_input else 'N/A'}")
        self.log("Calibrazione silenzio ambiente (2s)...")
        try:
            calm = sd.rec(int(32000), samplerate=16000, channels=1, dtype="int16")
            sd.wait()
            chunks = [calm[i:i+1600] for i in range(0, len(calm), 1600)]
            rmses = sorted(_rms(c.tobytes()) for c in chunks if len(c) == 1600)
            baseline = rmses[len(rmses)//4] if rmses else 0
        except Exception as e:
            self.log(f"Calibrazione fallita: {e}")
            baseline = 0
        threshold = max(baseline * 2.5, 300)
        threshold = min(threshold, 3000)
        self.log(f"Soglia VAD: {threshold:.0f} (baseline={baseline:.0f})")

        buf = []
        buf_ms = 0
        speech_ms = 0
        silence_ms = 0
        sample_count = 0
        callback_exc = None
        audio_queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            nonlocal buf, buf_ms, speech_ms, silence_ms, sample_count, threshold
            try:
                data = indata.copy().tobytes()
                rms = _rms(data)
                is_speech = rms > threshold
                sample_count += 1

                if sample_count % 50 == 0:
                    self.log(f"RMS: {rms:.0f} / soglia: {threshold:.0f} — {'PARLA' if is_speech else 'silenzio'}")

                if is_speech:
                    buf.append(data)
                    buf_ms += 100
                    speech_ms += 100
                    silence_ms = 0
                else:
                    silence_ms += 100
                    if buf_ms > 0 and speech_ms > 300 and silence_ms > 600:
                        audio = b"".join(buf)
                        self.log(f"Accodato {buf_ms}ms di audio (RMS picco ~{_rms(audio):.0f})...")
                        audio_queue.put(audio)
                        buf = []; buf_ms = 0; speech_ms = 0; silence_ms = 0
                    elif buf_ms > 3000 and silence_ms > 600:
                        buf = []; buf_ms = 0; speech_ms = 0; silence_ms = 0
                        self.log("Buffer scaduto (3s+)")
            except Exception as e:
                self.log(f"Errore callback: {e}")

        try:
            stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16",
                                    blocksize=1600, callback=callback)
            stream.start()
            self.log("Stream audio continuo avviato (mic non lampeggia)")
        except Exception as e:
            self.log(f"Stream fallito: {e}")
            return

        while self.running:
            try:
                audio = audio_queue.get(timeout=0.5)
                text = _transcribe(audio, 16000)
                if text:
                    lower = text.lower()
                    words = lower.split()
                    _TARGETS = ["jarvis", "jervis", "giarvis"]
                    matched_word = None
                    for w in words:
                        clean = w.strip(".,!?")
                        if difflib.get_close_matches(clean, _TARGETS, n=1, cutoff=0.4):
                            matched_word = clean
                            break
                    if not matched_word:
                        for w in words:
                            for part in w.split("'"):
                                if difflib.get_close_matches(part, _TARGETS, n=1, cutoff=0.4):
                                    matched_word = part
                                    break
                    if matched_word:
                        cmd = lower.replace(matched_word, "").strip(" .,!?")
                        if cmd:
                            self.log(f"Wake: '{cmd}'")
                            if self.chat_callback:
                                self.chat_callback(cmd)
                        else:
                            self.log("Wake word rilevata (senza comando)")
                            if self.chat_callback:
                                self.chat_callback("")
                    else:
                        self.log(f"Sentito (ignorato): '{text[:60]}'")
                else:
                    self.log("Trascrizione vuota (nessun testo rilevato)")
            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"Errore wake loop: {e}")

        stream.stop()
        stream.close()

    def _dictate_hotkey(self):
        """Quartz event tap per Option key → start/stop dettatura"""
        try:
            import Quartz
        except ImportError:
            self.log("pyobjc non installato, dictation non disponibile")
            return

        option_down = False

        def tap_cb(proxy, etype, event, refcon):
            nonlocal option_down
            if etype == Quartz.kCGEventFlagsChanged:
                flags = Quartz.CGEventGetFlags(event)
                keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                # Option key = keycode 58 (left) / 61 (right)
                is_option = keycode in (58, 61)
                if not is_option: return event
                if flags & 0x000800:
                    if not option_down:
                        option_down = True
                        self._start_dictation()
                else:
                    if option_down:
                        option_down = False
                        self._stop_dictation()
            return event

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
            tap_cb, None
        )
        if not tap:
            self.log("Event Tap fallito (servono permessi Accessibility)")
            return
        loop = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), loop,
                                  Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        self.log("Dictation: tieni premuto Option per dettare")
        Quartz.CFRunLoopRun()

    def _start_dictation(self):
        if self._dictating: return
        self._dictating = True
        self._dictate_buffer = []
        self._dictate_thread = threading.Thread(target=self._dictate_record,
                                                 daemon=True)
        self._dictate_thread.start()
        self.log("Dettatura: in ascolto...")

    def _stop_dictation(self):
        if not self._dictating: return
        self._dictating = False
        if hasattr(self, '_dictate_thread') and self._dictate_thread:
            self._dictate_thread.join(timeout=3)
        self.log("Dettatura: fermata, trascrizione in corso...")

    def _dictate_record(self):
        try:
            import sounddevice as sd
            buf = []
            while self._dictating:
                block = sd.rec(int(1600), samplerate=16000, channels=1, dtype="int16")
                sd.wait()
                buf.append(block.tobytes())
            audio = b"".join(buf)
            if len(audio) < 3200:  # < 100ms
                self.log("Dettatura: audio troppo corto")
                return
            self.log(f"Dettatura: {len(audio)/320:.0f}ms di audio")
            text = _transcribe(audio, 16000)
            if text:
                _paste_text(text)
                self.log(f"Dettatura: '{text[:80]}'")
            else:
                self.log("Dettatura: nessun testo rilevato")
        except Exception as e:
            self.log(f"Dettatura error: {e}")

    def _dictate_worker(self):
        while self.running:
            try:
                item = self._dictate_queue.get(timeout=1)
                if item: _paste_text(item)
            except: pass
