"""
=============================================================================
VOICE ENGINE (SPEECH RECOGNITION & TTS AUDIO FEEDBACK)
=============================================================================
Provides voice-guided command and control for the RC Car:
  1. Microphone Audio Listening & STT (Speech-To-Text via SpeechRecognition / Whisper)
  2. Windows Native SAPI5 / pyttsx3 Text-To-Speech (TTS)
  3. Natural Language Intent Classifier & Duration Extractor
  4. Interactive Voice Console Fallback
=============================================================================
"""

import re
import os
import time
import subprocess
import threading
import logging
from typing import Optional, Tuple, Dict, Any, Callable

logger = logging.getLogger("VoiceEngine")

# Try importing speech_recognition & pyttsx3
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    sr = None
    SR_AVAILABLE = False



class VoiceEngine:
    def __init__(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.callback = callback
        self.is_listening = False
        self.recognizer = sr.Recognizer() if SR_AVAILABLE else None
        self.microphone = None
        self._listen_thread: Optional[threading.Thread] = None

    def speak(self, text: str, async_mode: bool = True):
        """Speaks a message out loud using Windows SAPI5 in an isolated subprocess to keep COM clean."""
        logger.info(f"[VOICE SYNTHESIS] '{text}'")

        def _speak_worker():
            if os.name == "nt":
                try:
                    escaped_text = text.replace("'", "''").replace('"', '`"')
                    ps_cmd = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{escaped_text}")'
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    logger.debug(f"PowerShell TTS error: {e}")

        if async_mode:
            t = threading.Thread(target=_speak_worker, daemon=True)
            t.start()
        else:
            _speak_worker()

    def parse_intent(self, text: str) -> Dict[str, Any]:
        """
        Parses spoken phrases into structured car commands & parameters.
        Examples:
          "go forward for 2 seconds" -> {"action": "forward", "duration": 2.0}
          "turn left a little bit"   -> {"action": "left", "duration": 0.5}
          "turn on headlights"       -> {"action": "lights", "value": True}
          "start tracking mode"      -> {"action": "mode", "value": "track"}
        """
        text = text.lower().strip()

        # Extract duration if mentioned (e.g. "for 2 seconds", "1.5 sec", "500 ms")
        duration = 1.0  # default duration in seconds
        sec_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:seconds|second|secs|sec|s\b)', text)
        ms_match = re.search(r'(\d+)\s*(?:milliseconds|millisecond|ms\b)', text)
        if sec_match:
            duration = float(sec_match.group(1))
        elif ms_match:
            duration = float(ms_match.group(1)) / 1000.0

        # Intent Matching
        if any(k in text for k in ["stop", "halt", "freeze", "brake", "cancel", "wait"]):
            return {"action": "stop", "raw": text}

        if any(k in text for k in ["forward", "ahead", "straight", "front", "go go"]):
            steer = None
            if "left" in text:
                steer = "left"
            elif "right" in text:
                steer = "right"
            return {"action": "forward", "steer": steer, "duration": duration, "raw": text}

        if any(k in text for k in ["backward", "reverse", "back", "back up"]):
            steer = None
            if "left" in text:
                steer = "left"
            elif "right" in text:
                steer = "right"
            return {"action": "backward", "steer": steer, "duration": duration, "raw": text}

        if any(k in text for k in ["left", "turn left", "steer left", "port"]):
            return {"action": "left", "duration": duration or 0.6, "raw": text}

        if any(k in text for k in ["right", "turn right", "steer right", "starboard"]):
            return {"action": "right", "duration": duration or 0.6, "raw": text}

        # Features & Accessories
        if "light" in text or "headlight" in text:
            if any(k in text for k in ["on", "enable", "open", "flash"]):
                return {"action": "lights", "value": True, "raw": text}
            elif any(k in text for k in ["off", "disable", "close"]):
                return {"action": "lights", "value": False, "raw": text}
            return {"action": "toggle_lights", "raw": text}

        if "spray" in text or "smoke" in text or "exhaust" in text:
            if any(k in text for k in ["on", "enable", "start"]):
                return {"action": "spray", "value": True, "raw": text}
            elif any(k in text for k in ["off", "disable", "stop"]):
                return {"action": "spray", "value": False, "raw": text}
            return {"action": "toggle_spray", "raw": text}

        # Autopilot Modes
        if any(k in text for k in ["track", "follow", "chase", "target", "follow me"]):
            return {"action": "mode", "value": "track", "raw": text}

        if any(k in text for k in ["explore", "wander", "patrol", "autopilot", "auto mode"]):
            return {"action": "mode", "value": "explore", "raw": text}

        # Explicit AI query triggers
        if any(k in text for k in ["ask ai", "hey car", "brain", "think about", "what do you see"]):
            return {"action": "llm_query", "query": text, "raw": text}

        # Unhandled phrase
        return {"action": "unknown", "raw": text}

    def start_listening(self):
        """Starts background microphone listening if SpeechRecognition is available."""
        if not SR_AVAILABLE:
            logger.info("SpeechRecognition module not found. Use interactive prompt or install speech_recognition.")
            return

        self.is_listening = True
        self._listen_thread = threading.Thread(target=self._mic_loop, daemon=True)
        self._listen_thread.start()
        logger.info("Voice recognition listener started in background.")

    def _mic_loop(self):
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                while self.is_listening:
                    try:
                        audio = self.recognizer.listen(source, timeout=5.0, phrase_time_limit=6.0)
                        spoken_text = self.recognizer.recognize_google(audio)
                        logger.info(f"[USER SPOKE] \"{spoken_text}\"")
                        intent = self.parse_intent(spoken_text)
                        if self.callback:
                            self.callback(intent)
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except Exception as e:
                        logger.debug(f"Audio recognition error: {e}")
                        time.sleep(0.5)
        except Exception as e:
            logger.error(f"Microphone access error: {e}")
            self.is_listening = False

    def stop_listening(self):
        self.is_listening = False
