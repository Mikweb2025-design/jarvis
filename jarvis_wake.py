#!/usr/bin/env python3
"""jarvis_wake.py — wake word avanzato con VAD, hotkey globale, PyAudio streaming v2.0"""
import subprocess, sys, threading, time, os, struct, math
from pathlib import Path

class WakeWordDetector:
    """Wake word detection con Energy-based VAD + Google Speech Recognition"""
    
    def __init__(self, callback=None, wake_word="jarvis", sensitivity=0.6):
        self.wake_word = wake_word.lower()
        self.callback = callback
        self.running = False
        self.thread = None
        self.sensitivity = sensitivity
        self._recognition = None
        self._hotkey_thread = None
        
    def start(self):
        """Avvia wake word con hotkey Fn + ascolto continuo"""
        try:
            import speech_recognition as sr
            self._recognition = sr
        except ImportError:
            print("[WakeWord] pip install SpeechRecognition pyaudio webrtcvad")
            return False
            
        self.running = True
        
        # Thread 1: hotkey globale (Fn o Option+Space)
        self._hotkey_thread = threading.Thread(target=self._hotkey_listener, daemon=True, name="wake-hotkey")
        self._hotkey_thread.start()
        
        # Thread 2: ascolto continuo con VAD
        cont = threading.Thread(target=self._continuous_listen, daemon=True, name="wake-continuous")
        cont.start()
        
        print(f"[WakeWord] Avviato — hotkey Fn/Option+Space oppure di '{self.wake_word}'")
        return True
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[WakeWord] Fermato")
    
    def _hotkey_listener(self):
        """Ascolta hotkey globale usando karabiner/grabber o Carbon"""
        try:
            import Quartz
        except ImportError:
            # Fallback: usa karabiner event tap
            self._hotkey_karabiner()
            return
        
        print("[WakeWord] Hotkey: Option+Space per attivare")
        
        def tap_callback(proxy, type, event, refcon):
            if type == Quartz.kCGEventKeyDown:
                keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                flags = Quartz.CGEventGetFlags(event)
                # Option (0x00800) + Space (0x31)
                if keycode == 0x31 and flags & 0x00800:
                    print("[WakeWord] Hotkey attivato!")
                    self._trigger("hotkey")
            return event
        
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
            tap_callback,
            None
        )
        if tap:
            loop = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), loop, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            Quartz.CFRunLoopRun()
    
    def _hotkey_karabiner(self):
        """Fallback: monitora input da file descriptor"""
        print("[WakeWord] Hotkey mode: premi invio nel terminale per attivare manualmente")
        while self.running:
            try:
                import select
                r, _, _ = select.select([sys.stdin], [], [], 0.5)
                if r:
                    line = sys.stdin.readline().strip()
                    if line:
                        self._trigger(f"manual:{line}")
            except:
                time.sleep(0.5)
    
    def _continuous_listen(self):
        """Ascolto continuo con VAD per wake word"""
        import speech_recognition as sr
        
        r = sr.Recognizer()
        r.energy_threshold = 300
        r.dynamic_energy_threshold = True
        r.pause_threshold = 0.8
        
        mic = sr.Microphone(sample_rate=16000)
        
        with mic as source:
            print("[WakeWord] Calibrazione rumore ambiente...")
            r.adjust_for_ambient_noise(source, duration=1.5)
            print("[WakeWord] Pronto — ascolto continuo attivo")
        
        while self.running:
            try:
                with mic as source:
                    audio = r.listen(source, timeout=3, phrase_time_limit=4)
                
                # Quick energy check (VAD)
                if self._is_speech(audio, r):
                    text = r.recognize_google(audio, language="it-IT").lower()
                    if self.wake_word in text or "jarvis" in text:
                        print(f"[WakeWord] Rilevato! ('{text}')")
                        self._trigger(f"wake:{text}")
                        
            except Exception:
                pass
    
    def _is_speech(self, audio, recognizer):
        """Energy-based VAD per filtrare silenzio"""
        try:
            raw_data = audio.get_raw_data()
            if len(raw_data) < 1000:
                return False
            samples = struct.unpack(f"{len(raw_data)//2}h", raw_data[:len(raw_data)//2*2])
            rms = math.sqrt(sum(s*s for s in samples) / len(samples))
            return rms > 200
        except:
            return True
    
    def _trigger(self, source):
        """Attiva il callback"""
        if self.callback:
            try:
                self.callback(source)
            except Exception as e:
                print(f"[WakeWord] Callback error: {e}")
    
    def is_running(self):
        return self.running
