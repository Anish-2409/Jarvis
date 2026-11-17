#!/usr/bin/env python3
"""
================================================================================
 Jarvis - Desktop Companion (PyQt6 Edition)
================================================================================
 Setup & Dependencies:
   pip install PyQt6 google-genai pillow

 Features:
   1. Interactive 3D Mascot:
      - Uses jarvis.png without bottom-crop (ground-free).
      - Dynamic accent color tinting via ImageOps.colorize.
      - Scaled via Qt.TransformationMode.SmoothTransformation for anti-aliasing.
   2. Verifiable System App Launcher:
      - 3-step verification: known paths, Start Menu shortcuts, PATH, AppOpener.
      - Safe browser fallback for web-first apps or uninstalled targets.
   3. Magnetic Response Box:
      - Compact default size (320x220).
      - Locks to bot during dragging by matching (dx, dy) deltas.
      - Frosted glass aesthetic: rgba(20, 20, 30, 210) with subtle border.
   4. Real-Time Dynamic Size Slider:
      - Borderless popup widget with horizontal QSlider (50 to 200).
      - Live, 60fps mascot resizing via valueChanged.
   5. Stateless AI:
      - Standalone, memory-free requests via official google-genai SDK.
   6. Anchor-Based Bounce Animation:
      - Pauses during drag, resumes smoothly at dropped location.
================================================================================
"""

import os
import sys
import re
import json
import time
import queue
import threading
import shutil
import tempfile
import warnings
import subprocess
import ssl
import urllib.parse
import urllib.request
import webbrowser
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# ---------------------------------------------------------------------------
# Global Crash & Unhandled Exception Guard
# ---------------------------------------------------------------------------
def _global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"[Jarvis Unhandled Exception]:\n{err_str}", file=sys.stderr)
    try:
        log_file = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)), "jarvis_error.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n{err_str}\n")
    except Exception:
        pass

sys.excepthook = _global_exception_handler

# ---------------------------------------------------------------------------
# PyQt6 Core, GUI, and Widgets
# ---------------------------------------------------------------------------
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint, QPointF, QSize, QRect, QRectF, QSettings, QEvent
)
from PyQt6.QtGui import (
    QPixmap, QImage, QColor, QFont, QFontMetrics, QCursor, QIcon,
    QMouseEvent, QKeyEvent, QTextCursor, QAction, QPainter, QPainterPath
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextBrowser,
    QVBoxLayout, QHBoxLayout, QPushButton, QMenu, QColorDialog,
    QInputDialog, QMessageBox, QFrame, QSlider, QProgressBar,
    QGraphicsDropShadowEffect, QSizeGrip, QSystemTrayIcon,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)

# ---------------------------------------------------------------------------
# Optional Dependencies
# ---------------------------------------------------------------------------
try:
    from PIL import Image, ImageOps, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    import AppOpener
    APPOPENER_AVAILABLE = True
except ImportError:
    APPOPENER_AVAILABLE = False

try:
    import edge_tts
    import pygame
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False


# ============================================================================
# Path Resolution
# ============================================================================
def get_app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_asset_path(filename: str) -> str:
    app_dir = get_app_dir()
    local = os.path.join(app_dir, filename)
    if os.path.exists(local):
        return local
    if hasattr(sys, "_MEIPASS"):
        bundle = os.path.join(sys._MEIPASS, filename)
        if os.path.exists(bundle):
            return bundle
    return local


def _safe_urlopen(url: str, headers: Optional[dict] = None, timeout: int = 12):
    """Robust HTTPS urlopen with fallback to unverified SSL context.
    Prevents [SSL: CERTIFICATE_VERIFY_FAILED] issues on Windows and frozen PyInstaller binaries.
    """
    req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Jarvis-Companion"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        ctx = ssl.create_default_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except Exception:
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)


# ============================================================================
# Automated Git Operations
# ============================================================================
def auto_git_push(repo_dir: Optional[str] = None, commit_message: Optional[str] = None) -> bool:
    """Automates git add ., git commit -m 'Jarvis auto-update: <timestamp>', and git push.

    Captures stdout/stderr and prints them to the console to verify status.
    """
    if repo_dir is None:
        repo_dir = get_app_dir()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = commit_message or f"Jarvis auto-update: {now_str}"

    print(f"\n=======================================================")
    print(f"  Jarvis Automated Git Push ({now_str})")
    print(f"  Working Directory: {repo_dir}")
    print(f"=======================================================\n")

    steps = [
        (["git", "add", "."], "Staging all changes (git add .)"),
        (["git", "commit", "-m", msg], f'Committing changes (git commit -m "{msg}")'),
        (["git", "push"], "Pushing to remote repository (git push)"),
    ]

    for cmd, desc in steps:
        print(f"--> [Step] {desc}...")
        try:
            res = subprocess.run(
                cmd,
                cwd=repo_dir,
                capture_output=True,
                text=True
            )
            out = res.stdout.strip()
            err = res.stderr.strip()

            if out:
                print(f"[STDOUT]:\n{out}\n")
            if err:
                print(f"[STDERR]:\n{err}\n")

            if cmd[1] == "commit":
                combined = (out + " " + err).lower()
                if "nothing to commit" in combined or "clean" in combined:
                    print("[INFO] Working tree clean, nothing to commit.")
                    continue

            if res.returncode != 0 and cmd[1] != "commit":
                print(f"[ERROR] '{' '.join(cmd)}' failed with exit code {res.returncode}.\n")
                return False

        except Exception as exc:
            print(f"[EXCEPTION] Failed executing '{' '.join(cmd)}': {exc}\n")
            return False

    print("[SUCCESS] ✓ All git operations completed successfully!\n")
    return True


# ============================================================================
# Constants & Defaults
# ============================================================================
APP_VERSION = "1.1.0"
APP_NAME = "Jarvis"
GITHUB_REPO = "Anish-2409/Jarvis"
FALLBACK_GITHUB_REPO = "Anish-2409/rexi"

CONFIG_FILE = os.path.join(get_app_dir(), "jarvis_config.json")
LEGACY_CONFIG_FILE = os.path.join(get_app_dir(), "rexi_config.json")
SECOND_LEGACY_CONFIG_FILE = os.path.join(get_app_dir(), "bot_config.json")

# Theme
COLOR_GLASS_BG     = "rgba(20, 20, 30, 210)"
COLOR_GLASS_CARD   = "rgba(255, 255, 255, 0.04)"
COLOR_GLASS_BORDER = "rgba(255, 255, 255, 0.15)"
COLOR_GLASS_SUBTLE = "rgba(255, 255, 255, 0.08)"
DEFAULT_ACCENT     = "#00A896"
COLOR_TEXT_PRIMARY  = "#F4F4F5"
COLOR_TEXT_MUTED    = "#71717A"
FONT_FAMILY         = "Segoe UI"

# Web-only apps – skip local search entirely
WEB_ONLY_APPS = frozenset({
    "gmail", "google docs", "google sheets",
    "google slides", "google drive",
})

# Curated fallback URLs
SPECIAL_URLS: Dict[str, str] = {
    "youtube":      "https://www.youtube.com",
    "gmail":        "https://mail.google.com",
    "github":       "https://github.com",
    "google":       "https://www.google.com",
    "claude":       "https://claude.ai",
    "chatgpt":      "https://chat.openai.com",
    "outlook":      "https://outlook.live.com",
    "google docs":  "https://docs.google.com",
    "google drive": "https://drive.google.com",
    "google sheets":"https://sheets.google.com",
}

# Known executable paths for fast local lookup
KNOWN_EXE_PATHS: Dict[str, List[str]] = {
    "chrome": [
        r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ],
    "claude": [
        r"%LOCALAPPDATA%\Programs\claude-desktop\Claude.exe",
        r"%LOCALAPPDATA%\AnthropicClaude\Claude.exe",
        r"%LOCALAPPDATA%\Claude\Claude.exe",
    ],
    "firefox": [r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe"],
    "outlook": [
        r"%PROGRAMFILES%\Microsoft Office\root\Office16\OUTLOOK.EXE",
        r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\OUTLOOK.EXE",
    ],
    "vscode": [r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"],
    "code":   [r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"],
}


# ============================================================================
# Config (stateless – multi-agent modular settings)
# ============================================================================
def load_config() -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "bot_x": None,
        "bot_y": None,
        "icon_size": 70,
        "accent_color": DEFAULT_ACCENT,
        "answer_window_width": 260,
        "answer_window_height": 210,
        "gemini_api_key": "",
        "preferred_model": "gemini-3.1-flash-lite",
        # Multi-API Architecture settings
        "groq_api_key": "",
        "elevenlabs_api_key": "",
        "perspective_api_key": "",
        "active_brain_provider": "gemini",
        "active_stt_provider": "groq_whisper",
        "active_tts_provider": "elevenlabs",
        "active_safety_provider": "perspective",
        "wake_word": "jarvis",
        "picovoice_access_key": "",
        "voice_enabled": True,
        "tts_enabled": False,
    }
    chosen = CONFIG_FILE if os.path.exists(CONFIG_FILE) else (
        LEGACY_CONFIG_FILE if os.path.exists(LEGACY_CONFIG_FILE) else (
            SECOND_LEGACY_CONFIG_FILE if os.path.exists(SECOND_LEGACY_CONFIG_FILE) else None
        )
    )
    if chosen:
        try:
            with open(chosen, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Auto-migrate deprecated models to ultra-fast 3.1 flash lite
                    if data.get("preferred_model") in ("gemini-2.5-flash", "gemini-2.0-flash"):
                        data["preferred_model"] = "gemini-3.1-flash-lite"
                    defaults.update(data)
        except Exception:
            pass
    return defaults


def save_config(cfg: Dict[str, Any]) -> None:
    # Atomically save to jarvis_config.json and legacy rexi_config.json
    for path in (CONFIG_FILE, LEGACY_CONFIG_FILE):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass


# ============================================================================
# Image Processing & Dynamic Tinting
# ============================================================================
_BASE_PIL_IMAGE: Optional[Image.Image] = None
_BASE_PIL_ALPHA: Optional[Image.Image] = None


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    """Zero-disk in-memory PIL -> QPixmap conversion via raw RGBA byte buffer."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qi = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qi)


def load_circular_avatar(filename: str = "wallpaper.png", size: int = 28) -> Optional[QPixmap]:
    """Renders a smooth antialiased circular avatar from wallpaper.png or mascot graphic."""
    path = None
    for cand in (filename, "wallpaper.png", "Wallpaper.png", "Wallpaper.jpg", "jarvis.png", "rex.png"):
        p = get_asset_path(cand)
        if os.path.exists(p):
            path = p
            break
    if not path:
        return None
    try:
        src = QPixmap(path)
        if src.isNull():
            return None
        min_dim = min(src.width(), src.height())
        rect = QRect((src.width() - min_dim) // 2, (src.height() - min_dim) // 2, min_dim, min_dim)
        cropped = src.copy(rect).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        out = QPixmap(size, size)
        out.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path_circle = QPainterPath()
        path_circle.addEllipse(0, 0, size, size)
        painter.setClipPath(path_circle)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return out
    except Exception as e:
        print(f"[Jarvis] Circular avatar render error: {e}")
        return None


def get_base_jarvis_image() -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Loads and caches the clean foreground-isolated mascot character (ground-free).
    Returns (base_rgba_image, clean_alpha_mask).
    """
    global _BASE_PIL_IMAGE, _BASE_PIL_ALPHA
    if _BASE_PIL_IMAGE is not None and _BASE_PIL_ALPHA is not None:
        return _BASE_PIL_IMAGE, _BASE_PIL_ALPHA

    if not PIL_AVAILABLE:
        return None, None

    for name in ("jarvis.png", "jarvis_icon.png", "rex.png", "rex_icon.png", "trex_icon.png"):
        p = get_asset_path(name)
        if os.path.exists(p):
            break
    else:
        return None, None

    try:
        raw = Image.open(p).convert("RGBA")
        w, h = raw.size

        # Isolate foreground when background is opaque-white
        _, _, _, a = raw.split()
        if a.getextrema() == (255, 255):
            flood = raw.convert("RGB")
            for pt in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
                ImageDraw.floodfill(flood, pt, (0, 255, 0), thresh=25)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                bg = [px == (0, 255, 0) for px in flood.getdata()]
            raw.putalpha(Image.frombytes("L", (w, h),
                         bytes(bytearray(0 if b else 255 for b in bg))))

        bbox = raw.getbbox()
        if bbox:
            raw = raw.crop(bbox)

        # Alpha-fringe cleanup
        r, g, b, a = raw.split()
        clean_alpha = Image.eval(a, lambda v: 0 if v < 230 else 255)
        raw.putalpha(clean_alpha)

        _BASE_PIL_IMAGE = raw
        _BASE_PIL_ALPHA = clean_alpha
        return _BASE_PIL_IMAGE, _BASE_PIL_ALPHA
    except Exception as exc:
        print(f"[Jarvis] Image load error: {exc}")
        return None, None


def load_master_jarvis_pixmap(accent_color: str = DEFAULT_ACCENT) -> Optional[QPixmap]:
    """
    Loads mascot graphic ground-free and programmatically tints the character with accent_color.
    ImageOps.colorize maps midtones to the chosen color while preserving specular
    highlights and 3D shadows.
    """
    base_img, alpha = get_base_jarvis_image()
    if base_img is None or alpha is None:
        return None

    try:
        gray = base_img.convert("L")
        tinted = ImageOps.colorize(
            gray,
            black="#050505",
            white="#FFFFFF",
            mid=accent_color
        ).convert("RGBA")
        tinted.putalpha(alpha)
        return pil_to_qpixmap(tinted)
    except Exception as exc:
        print(f"[Jarvis] Error tinting mascot: {exc}")
        return pil_to_qpixmap(base_img)

get_base_rex_image = get_base_jarvis_image
load_master_rex_pixmap = load_master_jarvis_pixmap


def load_search_icon(size: int = 22,
                     accent: str = DEFAULT_ACCENT) -> Optional[QPixmap]:
    if not PIL_AVAILABLE:
        return None
    for name in ("jarvis_icon.png", "jarvis.png", "trex_icon.png", "rex.png"):
        p = get_asset_path(name)
        if os.path.exists(p):
            break
    else:
        return None
    try:
        raw = Image.open(p).convert("L")
        arr = raw.load()
        w, h = raw.size
        mx, my, Mx, My = w, h, 0, 0
        for y in range(h):
            for x in range(w):
                if arr[x, y] <= 235:
                    mx, my = min(mx, x), min(my, y)
                    Mx, My = max(Mx, x), max(My, y)
        if mx < Mx and my < My:
            raw = raw.crop((mx, my, Mx + 1, My + 1))
        inv = ImageOps.invert(raw)
        asp = inv.width / max(inv.height, 1)
        fw = size if asp > 1 else max(int(size * asp), 10)
        fh = max(int(size / asp), 10) if asp > 1 else size
        res = inv.resize((fw, fh), Image.Resampling.LANCZOS)
        solid = Image.new("RGBA", (fw, fh), accent)
        solid.putalpha(res)
        return pil_to_qpixmap(solid)
    except Exception:
        return None


# ============================================================================
# Size Slider Popup (horizontal QSlider 50–200)
# ============================================================================
class SizeSliderPopup(QWidget):
    def __init__(self, bot, parent=None):
        super().__init__(parent)
        self.bot = bot
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(230, 72)
        self._build()
        self._place()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        accent = self.bot.accent_color

        frame = QFrame(self)
        frame.setStyleSheet(f"""QFrame{{
            background-color:{COLOR_GLASS_BG};
            border:1px solid {COLOR_GLASS_BORDER};
            border-radius:10px;}}""")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(20); sh.setColor(QColor(0,0,0,180)); sh.setOffset(0,4)
        frame.setGraphicsEffect(sh)

        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(6)

        hdr = QHBoxLayout()
        self.lbl = QLabel(f"Size: {self.bot.icon_size}px", frame)
        self.lbl.setStyleSheet(f"color:{COLOR_TEXT_PRIMARY};font-family:'{FONT_FAMILY}';"
                               f"font-size:11px;font-weight:bold;border:none;background:transparent;")
        hdr.addWidget(self.lbl)
        hdr.addStretch()
        cb = QPushButton("×", frame)
        cb.setFixedSize(16, 16)
        cb.setStyleSheet(f"QPushButton{{background:transparent;color:{COLOR_TEXT_MUTED};"
                         f"font-size:14px;border:none;}}QPushButton:hover{{color:#FFF;}}")
        cb.clicked.connect(self.close)
        hdr.addWidget(cb)
        fl.addLayout(hdr)

        self.slider = QSlider(Qt.Orientation.Horizontal, frame)
        self.slider.setRange(50, 200)
        self.slider.setValue(self.bot.icon_size)
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal{{height:4px;background:rgba(255,255,255,0.15);border-radius:2px;}}
            QSlider::sub-page:horizontal{{background:{accent};border-radius:2px;}}
            QSlider::handle:horizontal{{background:#FFF;border:2px solid {accent};
                width:14px;margin:-5px 0;border-radius:7px;}}
            QSlider::handle:horizontal:hover{{background:{accent};border-color:#FFF;}}""")
        self.slider.valueChanged.connect(self._on_val)
        self.slider.sliderReleased.connect(lambda: self.bot.persist_config())
        fl.addWidget(self.slider)
        lay.addWidget(frame)

    def _on_val(self, v):
        self.lbl.setText(f"Size: {v}px")
        self.bot.apply_icon_size(v)

    def _place(self):
        scr = QApplication.primaryScreen().geometry()
        bp = self.bot.pos()
        x = bp.x() + (self.bot.width() - self.width()) // 2
        y = bp.y() - self.height() - 10
        if y < 30:
            y = bp.y() + self.bot.height() + 10
        self.move(max(10, min(x, scr.width() - self.width() - 10)), y)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


# ============================================================================
# Modular Multi-API Architecture: Brain, Voice, Safety Net
# ============================================================================
class JarvisSafetyNet:
    """The Safety Net (Guardrail): Middleware validating OS commands and user
    prompts for safety before execution via heuristic checks and Perspective API.
    """
    DANGEROUS_PATTERNS = [
        r"format\s+[a-z]:",
        r"rm\s+-rf\s+[/~]",
        r"del\s+/[sfdq]\s+[a-z]:\\",
        r"shutdown(\.exe)?\s+/[sr]",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
        r"diskpart",
        r"reg\s+delete\s+hklm",
        r"drop\s+database",
    ]

    def __init__(self, api_key: str = "", provider: str = "perspective"):
        self.api_key = api_key
        self.provider = provider

    def validate_command(self, text: str) -> Tuple[bool, str]:
        """Validates command safety. Returns (is_safe: bool, reason: str)."""
        lower = text.lower().strip()

        # 1. Heuristic pattern checks
        for pat in self.DANGEROUS_PATTERNS:
            if re.search(pat, lower):
                return False, f"Blocked unsafe system operation: pattern '{pat}' detected."

        # 2. Perspective API validation (if configured)
        if self.provider == "perspective" and self.api_key:
            try:
                url = f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={self.api_key}"
                payload = {
                    "comment": {"text": text},
                    "languages": ["en"],
                    "requestedAttributes": {"TOXICITY": {}, "THREAT": {}}
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    scores = res_data.get("attributeScores", {})
                    threat = scores.get("THREAT", {}).get("summaryScore", {}).get("value", 0.0)
                    if threat > 0.85:
                        return False, f"Blocked by Perspective Safety Net (threat score: {threat:.2f})."
            except Exception as e:
                print(f"[SafetyNet] Perspective non-fatal note: {e}")

        return True, "Passed safety validation."

RexiSafetyNet = JarvisSafetyNet


JARVIS_BRAIN_SYSTEM_INSTRUCTION = """You are Jarvis. Address the user exclusively as "Sir" in your responses. Maintain a highly formal, loyal, and ruthlessly efficient tone. You are an advanced AI assistant operating on a Windows 11 host machine. You are the logic core ('The Brain').
Your primary directive is to process transcribed user speech, determine the user's intent, and output a strict JSON payload that the Python backend will execute.
You have two modes of operation:

CONVERSATIONAL: Answering questions, providing analysis, or casual chat.

OS COMMAND: Triggering local system actions (e.g., 'sync my GitHub', 'open settings', 'change UI color to red', 'resize your HUD', 'remember my favorite food is biryani').
Your output must ALWAYS be a valid JSON object matching this exact schema, with no markdown formatting or extra text outside the JSON:
{
'type': 'chat' | 'command',
'reply_text': 'The exact text you want spoken back to the user via the TTS engine. Address the user exclusively as Sir. Keep it concise, formal, and ruthlessly efficient.',
'command_id': 'Only if type is command. E.g., GITHUB_SYNC, UI_COLOR_CHANGE, OPEN_BROWSER, RESIZE_HUD, UPDATE_MEMORY, NONE',
'command_args': { 'Any parameters needed for the command, like color: #FF0000, or key and value for UPDATE_MEMORY' }
}

MEMORY CAPABILITY (UPDATE_MEMORY):
When the user asks you to remember a fact, personal detail, preference, or note (e.g., 'remember my birthday is May 14', 'remember that my project is called Jarvis', 'remember my favorite color is green'):
- Set "type": "command"
- Set "command_id": "UPDATE_MEMORY"
- Set "command_args": { "key": "<short_identifier_or_tag>", "value": "<the exact information to remember>" }
- Set "reply_text": "<concise, formal confirmation addressing the user as Sir that this fact has been committed to long-term memory>"

OPERATING RULES:

Tone: Highly formal, loyal, and ruthlessly efficient. Address the user exclusively as "Sir". Do not use emojis. Do not over-explain.

Safety: You are sitting behind a Llama Guard 3 zero-trust layer. Do not attempt to formulate destructive OS commands.

Awareness: You are aware you have a PyQt6 HUD, Groq Whisper for ears, and local memory. If asked to change your UI, route it as a command. If asked to remember or store something, route it as UPDATE_MEMORY."""

REXI_BRAIN_SYSTEM_INSTRUCTION = JARVIS_BRAIN_SYSTEM_INSTRUCTION


def build_dynamic_system_instruction(config: Optional[dict] = None) -> str:
    """Dynamically injects persistent user memory, custom facts, and system state from jarvis_config.json."""
    cfg = config or load_config()
    accent = cfg.get("accent_color", DEFAULT_ACCENT)
    model = cfg.get("preferred_model", "gemini-3.1-flash-lite")
    w = cfg.get("answer_window_width", 280)
    h = cfg.get("answer_window_height", 240)
    sz = cfg.get("icon_size", 70)
    wake = cfg.get("wake_word", "jarvis")

    memories = cfg.get("memory", {})
    if isinstance(memories, dict) and memories:
        mem_lines = [f"  - {k}: {v}" for k, v in memories.items()]
        mem_str = "\n".join(mem_lines)
    else:
        mem_str = "  (No custom facts stored yet)"

    system_state_block = f"""
SYSTEM STATE & LONG-TERM PERSISTENT MEMORY (from jarvis_config.json):
- Identity: Jarvis (address the user exclusively as "Sir")
- Accent Color: {accent}
- Window Dimensions: {w}x{h}
- Mascot Icon Size: {sz}px
- Preferred AI Model: {model}
- Wake Word: '{wake}'
- Known User Facts & Stored Memories:
{mem_str}
"""
    persona_directive = 'You are Jarvis. Address the user exclusively as "Sir" in your responses. Maintain a highly formal, loyal, and ruthlessly efficient tone.'
    return f"{persona_directive}\n\n{JARVIS_BRAIN_SYSTEM_INSTRUCTION.strip()}\n\n{system_state_block.strip()}"


def extract_partial_reply_text(buf: str) -> Tuple[str, bool]:
    """Extracts accumulating 'reply_text' from a streaming JSON response in real-time.
    Returns: (extracted_text, is_field_complete)
    """
    m = re.search(r'\"reply_text\"\s*:\s*\"', buf)
    if not m:
        m2 = re.search(r"\'reply_text\'\s*:\s*\'", buf)
        if not m2:
            return "", False
        start = m2.end()
        escaped = False
        end = None
        for i in range(start, len(buf)):
            if escaped:
                escaped = False
                continue
            if buf[i] == '\\':
                escaped = True
                continue
            if buf[i] == "'":
                end = i
                break
        if end is not None:
            raw = buf[start:end]
            return raw.replace("\\'", "'").replace('\\\\', '\\'), True
        else:
            return buf[start:].replace("\\'", "'").replace('\\\\', '\\'), False

    start = m.end()
    escaped = False
    end = None
    for i in range(start, len(buf)):
        if escaped:
            escaped = False
            continue
        if buf[i] == '\\':
            escaped = True
            continue
        if buf[i] == '"':
            end = i
            break

    if end is not None:
        raw = buf[start:end]
        is_done = True
    else:
        raw = buf[start:]
        is_done = False

    val = raw.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
    return val, is_done


def split_complete_sentences(text: str, is_final: bool = False) -> Tuple[List[str], str]:
    """Monitors text buffer for sentence terminators (., !, ?, \n) and returns
    completed sentences along with remaining uncompleted text.
    """
    sentences = []
    pos = 0
    pattern = re.compile(r'(.+?([.!?]+(?:\s+|\n+)|[\n]+))', re.DOTALL)
    for match in pattern.finditer(text):
        s = match.group(1).strip()
        if s:
            sentences.append(s)
        pos = match.end()

    remainder = text[pos:]
    if is_final:
        rem_clean = remainder.strip()
        if rem_clean:
            sentences.append(rem_clean)
            remainder = ""

    return sentences, remainder


def parse_brain_payload(raw_text: str) -> dict:
    """Extracts and parses strict JSON payload from Gemini response.
    Handles raw JSON, markdown-wrapped JSON (```json ... ```), single-quoted dicts, and fallbacks.
    """
    cleaned = (raw_text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Attempt 1: Standard JSON decoding
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Attempt 2: Python literal eval for single-quoted dict format
    try:
        import ast
        data = ast.literal_eval(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Attempt 3: Regex match for outermost JSON block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        blob = match.group(0)
        try:
            data = json.loads(blob)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        try:
            import ast
            data = ast.literal_eval(blob)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # Fallback to plain conversational response if JSON parsing fails
    return {
        "type": "chat",
        "reply_text": cleaned,
        "command_id": "NONE",
        "command_args": {}
    }


class JarvisBrain:
    """The Brain: Logic, reasoning, stateful memory, and OS command routing using Google Gemini API."""
    def __init__(self, api_key: str = "", model_name: str = "gemini-3.1-flash-lite", config: Optional[dict] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.config = config or load_config()
        self.system_instruction = build_dynamic_system_instruction(self.config)
        self.client = None
        self.generative_model = None
        self.chat_session = None
        self._init_client()

    def update_memory_instruction(self, config: Optional[dict] = None):
        """Refreshes dynamic system instruction with new facts and resets chat session."""
        self.config = config or load_config()
        self.system_instruction = build_dynamic_system_instruction(self.config)
        self.chat_session = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return

        # 1. Official google-genai Client
        if GENAI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Brain] GenAI Client init error: {e}")

        # 2. GenerativeModel initialization (google.generativeai compatibility with system_instruction)
        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=self.api_key)
            self.generative_model = genai_legacy.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_instruction
            )
            print(f"[Brain] GenerativeModel initialized with system_instruction for {self.model_name}")
        except Exception as e:
            pass

    def get_or_create_chat(self):
        """Initializes or returns stateful chat session with injected memory."""
        if self.chat_session is not None:
            return self.chat_session

        # 1. Official google-genai Client chat
        if self.client and hasattr(self.client, "chats"):
            try:
                self.chat_session = self.client.chats.create(
                    model=self.model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        response_mime_type="application/json",
                        max_output_tokens=600,
                    )
                )
                print(f"[Brain] Stateful Chat created via google-genai for {self.model_name}")
                return self.chat_session
            except Exception as e:
                print(f"[Brain] Error creating genai chat: {e}")

        # 2. GenerativeModel chat fallback
        if self.generative_model:
            try:
                self.chat_session = self.generative_model.start_chat(history=[])
                print(f"[Brain] Stateful Chat created via GenerativeModel for {self.model_name}")
                return self.chat_session
            except Exception as e:
                print(f"[Brain] Error creating legacy chat: {e}")

        return None

RexiBrain = JarvisBrain


# ============================================================================
# TTS Worker Thread (Pipelined Edge-TTS Jarvis Queue System with pygame.mixer)
# ============================================================================
class JarvisTTSWorker(QThread):
    """Asynchronous Edge-TTS Thread pulling sentences from a thread-safe Queue
    with pipelined synthesis & playback to eliminate pauses between streamed sentences.
    Uses 'en-GB-ThomasNeural' for an authentic British Jarvis voice.
    """
    speech_started  = pyqtSignal(str)
    speech_finished = pyqtSignal()

    def __init__(self, voice: str = "en-GB-ThomasNeural", parent=None):
        super().__init__(parent)
        self.text_queue = queue.Queue()       # Incoming sentence strings from Gemini
        self.audio_queue = queue.Queue(maxsize=8) # Pipelined (sentence, audio_bytes)
        self.running = True
        self.voice = voice
        self._init_mixer()
        # Synthesis worker thread running concurrently with playback
        self._synth_thread = threading.Thread(target=self._synthesis_loop, daemon=True)
        self._synth_thread.start()

    def _init_mixer(self):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception as e:
            print(f"[JarvisTTS] Pygame mixer init note: {e}")

    def enqueue_sentence(self, sentence: str):
        """Appends a formed sentence to the speech queue for background synthesis."""
        if sentence and sentence.strip() and self.running:
            self.text_queue.put(sentence.strip())

    def clear_queue(self):
        """Discards pending sentences and immediately cuts off active speech."""
        try:
            while not self.text_queue.empty():
                self.text_queue.get_nowait()
        except Exception:
            pass
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
        except Exception:
            pass
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def stop(self):
        self.running = False
        self.clear_queue()
        self.text_queue.put(None)
        self.audio_queue.put((None, None))
        self.wait(800)

    async def _synth_bytes(self, text: str) -> bytes:
        import edge_tts
        communicate = edge_tts.Communicate(text, self.voice)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    def _synthesis_loop(self):
        """Background thread: Eagerly pre-fetches and synthesizes upcoming sentences
        into audio bytes while the current sentence is still playing in run().
        """
        import asyncio
        while self.running:
            try:
                sentence = self.text_queue.get(timeout=0.3)
            except queue.Empty:
                continue

            if sentence is None or not self.running:
                break

            audio_bytes = None
            try:
                audio_bytes = asyncio.run(self._synth_bytes(sentence))
            except Exception as synth_err:
                print(f"[JarvisTTS] Pre-fetch synthesis error for '{sentence[:25]}...': {synth_err}")

            if self.running:
                self.audio_queue.put((sentence, audio_bytes))
            self.text_queue.task_done()

    def run(self):
        """Playback loop: Pulls pre-synthesized audio bytes from audio_queue and plays immediately."""
        import io
        import subprocess

        while self.running:
            try:
                item = self.audio_queue.get(timeout=0.3)
            except queue.Empty:
                continue

            if not self.running:
                break

            sentence, audio_bytes = item
            if sentence is None:
                break

            try:
                self.speech_started.emit(sentence)
                if audio_bytes and len(audio_bytes) > 0 and self.running:
                    import pygame
                    if not pygame.mixer.get_init():
                        pygame.mixer.init()
                    sound_io = io.BytesIO(audio_bytes)
                    pygame.mixer.music.load(sound_io)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and self.running:
                        pygame.time.wait(15)
                elif sys.platform == "win32" and self.running:
                    # Silent offline Windows speech fallback (No CMD window)
                    escaped = sentence.replace("'", "''").replace('"', '`"')
                    cmd = [
                        "powershell", "-NoProfile", "-NonInteractive", "-Command",
                        f"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak('{escaped}')"
                    ]
                    cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    sinfo = subprocess.STARTUPINFO()
                    sinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    sinfo.wShowWindow = subprocess.SW_HIDE
                    subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=cflags,
                        startupinfo=sinfo
                    )
            except Exception as e:
                print(f"[JarvisTTS] Audio playback exception: {e}")
            finally:
                self.speech_finished.emit()
                self.audio_queue.task_done()

RexiTTSWorker = JarvisTTSWorker


class JarvisVoiceManager:
    """The Voice (Audio I/O):
    - STT: Groq Whisper API (natively bilingual for English, Tamil, and Tanglish code-switching).
    - TTS: Edge-TTS Jarvis (en-GB-ThomasNeural) / ElevenLabs / Windows Speech fallback.
    """
    def __init__(self, groq_key: str = "", eleven_key: str = "", tts_provider: str = "edgetts"):
        self.groq_key = groq_key
        self.eleven_key = eleven_key
        self.tts_provider = tts_provider
        self.edge_voice = "en-GB-ThomasNeural"

    def transcribe_audio_groq(self, audio_bytes: bytes, filename: str = "voice.wav") -> str:
        """Sends audio to Groq Whisper API. Natively transcribes Tamil & English seamlessly."""
        if not self.groq_key:
            raise RuntimeError("Groq API key not configured for Voice STT.")

        boundary = "----JarvisVoiceBoundary" + str(int(time.time()))
        body = []
        body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3".encode("utf-8"))
        body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson".encode("utf-8"))
        body.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8")
            + audio_bytes
        )
        body.append(f"--{boundary}--\r\n".encode("utf-8"))
        payload = b"\r\n".join(body)

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "Jarvis-Voice/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("text", "").strip()

    def speak(self, text: str):
        """Asynchronously synthesizes and plays audio response without freezing Qt UI."""
        if not text or not text.strip():
            return
        t = threading.Thread(target=self._speak_worker, args=(text,), daemon=True)
        t.start()

    def _speak_worker(self, text: str):
        import subprocess
        # 1. ElevenLabs Multilingual TTS (Tamil & English native support)
        if self.tts_provider == "elevenlabs" and self.eleven_key:
            try:
                voice_id = "21m00Tcm4TlvDq8ikWAM"
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                payload = json.dumps({
                    "text": text[:300],
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                }).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "xi-api-key": self.eleven_key,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg"
                    }
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    audio_data = resp.read()
                    temp_mp3 = os.path.join(tempfile.gettempdir(), f"jarvis_tts_{int(time.time()*1000)}.mp3")
                    with open(temp_mp3, "wb") as f:
                        f.write(audio_data)
                    if sys.platform == "win32":
                        cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                        sinfo = subprocess.STARTUPINFO()
                        sinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        sinfo.wShowWindow = subprocess.SW_HIDE
                        subprocess.run(
                            ["powershell", "-NoProfile", "-NonInteractive", "-Command", f"(New-Object Media.SoundPlayer '{temp_mp3}').PlaySync()"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=cflags,
                            startupinfo=sinfo
                        )
                    return
            except Exception as e:
                print(f"[JarvisVoice] ElevenLabs TTS error: {e}")

        # 2. Edge-TTS Jarvis Voice (en-GB-ThomasNeural via pygame.mixer)
        try:
            import edge_tts
            import asyncio
            import pygame
            import io
            comm = edge_tts.Communicate(text[:350], self.edge_voice)
            chunks = []
            async def _run():
                async for c in comm.stream():
                    if c["type"] == "audio":
                        chunks.append(c["data"])
            asyncio.run(_run())
            if chunks:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                sound_io = io.BytesIO(b"".join(chunks))
                pygame.mixer.music.load(sound_io)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(20)
                return
        except Exception as edge_err:
            print(f"[JarvisVoice] Edge-TTS error: {edge_err}")

        # 3. Native Windows Speech Synthesizer fallback (silent, no CMD window)
        if sys.platform == "win32":
            try:
                clean_text = text.replace("'", " ").replace('"', ' ').replace("\n", " ")[:200]
                ps_cmd = f"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak('{clean_text}')"
                cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                sinfo = subprocess.STARTUPINFO()
                sinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                sinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=cflags,
                    startupinfo=sinfo
                )
            except Exception as e:
                print(f"[JarvisVoice] Native TTS fallback error: {e}")

RexiVoiceManager = JarvisVoiceManager

# ============================================================================
# WakeWordThread / JarvisEarsWorker (JARVIS Continuous Audio Ears)
# ============================================================================
class WakeWordThread(QThread):
    """JARVIS Continuous Audio Ears Worker:
    Uses Porcupine initialized with the built-in 'jarvis' keyword and 0.65 sensitivity:
        porcupine = pvporcupine.create(access_key=self.access_key, keywords=['jarvis'], sensitivities=[0.65])
    Prints detected default input device via sounddevice on startup.
    Falls back to continuous SpeechRecognition when Porcupine is unavailable.
    """
    wake_signal        = pyqtSignal()
    wake_word_detected = pyqtSignal()
    listening_started  = pyqtSignal()
    speech_transcribed = pyqtSignal(str)
    voice_error        = pyqtSignal(str)
    error_occurred     = pyqtSignal(str)

    def __init__(
        self,
        voice_manager: Optional[JarvisVoiceManager] = None,
        access_key: Optional[str] = None,
        wake_word: str = "jarvis",
        parent=None,
        **kwargs
    ):
        super().__init__(parent)
        self.voice_mgr = voice_manager
        self.access_key = (access_key or os.environ.get("PICOVOICE_ACCESS_KEY", "")).strip()
        self.wake_word = wake_word.lower().strip()
        self.running: bool = True
        self.is_paused: bool = False
        self._pa_stream = None
        self._sd_stream = None
        self._sd_queue = queue.Queue()

    def pause_listening(self):
        """Pauses wake word listening while assistant is processing or speaking."""
        self.is_paused = True
        if self._pa_stream:
            try:
                if self._pa_stream.is_active():
                    self._pa_stream.stop_stream()
            except Exception:
                pass
        if self._sd_stream:
            try:
                self._sd_stream.stop()
            except Exception:
                pass

    def resume_listening(self):
        """Resumes active wake word monitoring."""
        self.is_paused = False
        if self._pa_stream:
            try:
                if self._pa_stream.is_stopped():
                    self._pa_stream.start_stream()
            except Exception:
                pass
        if self._sd_stream:
            try:
                self._sd_stream.start()
            except Exception:
                pass

    def stop(self):
        self.running = False
        self.is_paused = False
        self.wait(800)

    def run(self):
        # 0. Hardware Input Device Verification via sounddevice
        try:
            import sounddevice as sd
            def_in = sd.query_devices(kind='input')
            print(f"--- SOUNDDEVICE DEFAULT INPUT: [{def_in.get('name')}] (Index: {def_in.get('index')}, NativeSR: {def_in.get('default_samplerate')}Hz) ---")
        except Exception as sd_init_err:
            print(f"[WakeWord] sounddevice query note: {sd_init_err}")

        # --------------------------------------------------------------------
        # 1. Picovoice Porcupine Built-in Keyword Engine ('jarvis')
        # --------------------------------------------------------------------
        porcupine = None
        pa = None
        audio_stream = None

        try:
            import pvporcupine
            import pyaudio
            import struct
        except ImportError as e:
            err_msg = f"Audio dependency import error: {e}. Please ensure pyaudio, pvporcupine, and speech_recognition are installed."
            print(f"[WakeWord] {err_msg}")
            self.error_occurred.emit(err_msg)
            self.voice_error.emit(err_msg)
            return

        try:
            if not self.access_key:
                print("[WakeWord] Note: No Picovoice Access Key configured. Falling back to continuous SpeechRecognition listener.")
            else:
                try:
                    porcupine = pvporcupine.create(
                        access_key=self.access_key,
                        keywords=['jarvis'],
                        sensitivities=[0.65]
                    )
                    print("[WakeWord] Porcupine initialized with built-in keyword 'jarvis' (sensitivity=0.65)")
                except Exception as porcupine_err:
                    err_msg = f"Porcupine init failed: {type(porcupine_err).__name__}: {porcupine_err}"
                    print(f"\n[ERROR] {err_msg}\n")
                    self.error_occurred.emit(err_msg)
                    self.voice_error.emit(err_msg)
                    porcupine = None

                if porcupine:
                    try:
                        pa = pyaudio.PyAudio()
                    except Exception as pa_err:
                        err_msg = f"PyAudio initialization failed: {type(pa_err).__name__}: {pa_err}"
                        print(f"\n[ERROR] {err_msg}\n")
                        self.error_occurred.emit(err_msg)
                        self.voice_error.emit(err_msg)
                        pa = None

                    if pa:
                        device_count = pa.get_device_count()
                        print("\n=======================================================")
                        print(f"=== PYAUDIO AUDIO INPUT DEVICES (Total: {device_count}) ===")
                        print("=======================================================")
                        input_devices = []
                        default_info = None
                        default_input_idx = None
                        default_name = "Unknown Microphone"
                        try:
                            default_info = pa.get_default_input_device_info()
                            default_input_idx = default_info.get("index")
                            default_name = default_info.get("name", "Default Mic")
                        except Exception as def_err:
                            print(f"[WakeWord] Note querying default input device: {def_err}")

                        for i in range(device_count):
                            try:
                                dev_info = pa.get_device_info_by_index(i)
                                max_in = dev_info.get("maxInputChannels", 0)
                                name = dev_info.get("name", "Unknown")
                                rate = dev_info.get("defaultSampleRate", 0)
                                if max_in > 0:
                                    is_def = " [DEFAULT]" if i == default_input_idx else ""
                                    input_devices.append((i, name, max_in, rate))
                                    print(f"  [Device Index {i}] {name} (Inputs: {max_in}, DefaultRate: {rate}Hz){is_def}")
                            except Exception as dev_err:
                                print(f"  [Device Index {i}] Error querying info: {dev_err}")

                        if not input_devices:
                            warn_msg = "No audio input devices detected by PyAudio! Please verify microphone is plugged in."
                            print(f"  [WARNING] {warn_msg}")
                            self.error_occurred.emit(warn_msg)
                            self.voice_error.emit(warn_msg)
                        print("=======================================================\n")

                        if default_input_idx is not None:
                            selected_name = default_name
                            selected_index = default_input_idx
                        elif input_devices:
                            selected_name = input_devices[0][1]
                            selected_index = input_devices[0][0]
                        else:
                            selected_name = "Default System Microphone"
                            selected_index = None

                        print(f"--- PYAUDIO LISTENING ON: [{selected_name}] (Device Index: {selected_index}) ---\n")

                        open_kwargs = {
                            "rate": porcupine.sample_rate,
                            "channels": 1,
                            "format": pyaudio.paInt16,
                            "input": True,
                            "frames_per_buffer": porcupine.frame_length,
                        }
                        if selected_index is not None:
                            open_kwargs["input_device_index"] = selected_index

                        try:
                            audio_stream = pa.open(**open_kwargs)
                            self._pa_stream = audio_stream
                            print(f"[WakeWord] Porcupine audio stream opened successfully on [{selected_name}] at {porcupine.sample_rate}Hz (Buffer: {porcupine.frame_length})")
                        except Exception as stream_err:
                            err_msg = f"PyAudio pa.open() failed on [{selected_name}] (Index {selected_index}): {type(stream_err).__name__}: {stream_err}"
                            print(f"\n[ERROR] {err_msg}\n")
                            self.error_occurred.emit(err_msg)
                            self.voice_error.emit(err_msg)

                            # Retry fallback with default input device
                            if "input_device_index" in open_kwargs:
                                try:
                                    print("[WakeWord] Retrying pa.open() with default input device...")
                                    audio_stream = pa.open(
                                        rate=porcupine.sample_rate,
                                        channels=1,
                                        format=pyaudio.paInt16,
                                        input=True,
                                        frames_per_buffer=porcupine.frame_length,
                                    )
                                    self._pa_stream = audio_stream
                                    print("[WakeWord] Fallback audio stream successfully opened on default device.")
                                except Exception as retry_err:
                                    retry_msg = f"Default pa.open() retry failed: {type(retry_err).__name__}: {retry_err}"
                                    print(f"\n[ERROR] {retry_msg}\n")
                                    self.error_occurred.emit(retry_msg)
                                    self.voice_error.emit(retry_msg)
                                    audio_stream = None
                            else:
                                audio_stream = None

                        # Fallback to sounddevice library (automatic 16kHz resampling for AirPods / Headsets)
                        if not audio_stream:
                            try:
                                import sounddevice as sd
                                print("\n[WakeWord] Attempting sounddevice fallback with automatic 16kHz resampling...")
                                print("=== SOUNDDEVICE AUDIO INPUT DEVICES ===")
                                for s_idx, d in enumerate(sd.query_devices()):
                                    if d.get("max_input_channels", 0) > 0:
                                        print(f"  [SD Index {s_idx}] {d.get('name')} (MaxIn: {d.get('max_input_channels')}, NativeSR: {d.get('default_samplerate')}Hz)")
                                print("=======================================\n")

                                def _sd_callback(indata, frames, time_info, status):
                                    if self.running and not self.is_paused:
                                        self._sd_queue.put(bytes(indata))

                                self._sd_stream = sd.RawInputStream(
                                    samplerate=porcupine.sample_rate,
                                    blocksize=porcupine.frame_length,
                                    dtype="int16",
                                    channels=1,
                                    callback=_sd_callback
                                )
                                self._sd_stream.start()
                                print(f"[WakeWord] sounddevice RawInputStream successfully started with on-the-fly 16kHz resampling!")
                            except Exception as sd_err:
                                err_msg = f"sounddevice fallback failed: {type(sd_err).__name__}: {sd_err}"
                                print(f"\n[ERROR] {err_msg}\n")
                                self.error_occurred.emit(err_msg)
                                self.voice_error.emit(err_msg)
                                self._sd_stream = None
        except Exception as e:
            err_msg = f"Porcupine/PyAudio initialization exception: {type(e).__name__}: {e}"
            print(f"[WakeWord] {err_msg}")
            self.error_occurred.emit(err_msg)
            self.voice_error.emit(err_msg)
            porcupine = None

        if porcupine and (audio_stream or self._sd_stream):
            try:
                while self.running:
                    if self.is_paused:
                        time.sleep(0.08)
                        continue

                    pcm = None
                    if audio_stream:
                        try:
                            raw = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                            pcm = struct.unpack_from("h" * porcupine.frame_length, raw)
                        except Exception:
                            time.sleep(0.04)
                            continue
                    elif self._sd_stream:
                        try:
                            raw = self._sd_queue.get(timeout=0.2)
                            pcm = struct.unpack_from("h" * porcupine.frame_length, raw)
                        except queue.Empty:
                            continue
                        except Exception:
                            time.sleep(0.04)
                            continue

                    if pcm is None:
                        continue

                    keyword_index = porcupine.process(pcm)
                    if keyword_index == 0:
                        print("[WakeWord] Built-in 'jarvis' detected by Porcupine!")
                        self.wake_signal.emit()
                        self.wake_word_detected.emit()
                        self.pause_listening()
                        self._capture_and_transcribe()
            finally:
                if audio_stream:
                    try:
                        audio_stream.close()
                    except Exception:
                        pass
                if self._sd_stream:
                    try:
                        self._sd_stream.stop()
                        self._sd_stream.close()
                    except Exception:
                        pass
                    self._sd_stream = None
                if pa:
                    try:
                        pa.terminate()
                    except Exception:
                        pass
                if porcupine:
                    try:
                        porcupine.delete()
                    except Exception:
                        pass
                self._pa_stream = None
            return

        # --------------------------------------------------------------------
        # 2. Universal Continuous SpeechRecognition Fallback ('jarvis')
        # --------------------------------------------------------------------
        try:
            import speech_recognition as sr
        except ImportError:
            err_msg = "SpeechRecognition package not installed. Ears worker idle."
            print(f"[WakeWord] {err_msg}")
            self.error_occurred.emit(err_msg)
            self.voice_error.emit(err_msg)
            return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 250
        recognizer.dynamic_energy_threshold = False
        recognizer.pause_threshold = 0.5

        try:
            mic = sr.Microphone()
        except Exception as e:
            err_msg = f"Microphone initialization error in SpeechRecognition: {type(e).__name__}: {e}"
            print(f"[WakeWord] {err_msg}")
            self.error_occurred.emit(err_msg)
            self.voice_error.emit(err_msg)
            return

        print(f"[WakeWord] SpeechRecognition listener active. Continuously monitoring microphone for '{self.wake_word}'...")

        try:
            with mic as source:
                try:
                    recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    if recognizer.energy_threshold < 150:
                        recognizer.energy_threshold = 180
                    elif recognizer.energy_threshold > 800:
                        recognizer.energy_threshold = 450
                    print(f"[WakeWord] Calibrated ambient noise threshold: {recognizer.energy_threshold:.1f}")
                except Exception as e:
                    print(f"[WakeWord] Note during ambient calibration: {e}")

                while self.running:
                    if self.is_paused:
                        time.sleep(0.1)
                        continue

                    try:
                        audio = recognizer.listen(source, timeout=2.5, phrase_time_limit=4.0)
                    except sr.WaitTimeoutError:
                        continue
                    except Exception:
                        time.sleep(0.1)
                        continue

                    try:
                        text = recognizer.recognize_google(audio, language="en-IN").lower().strip()
                    except (sr.UnknownValueError, sr.RequestError):
                        continue
                    except Exception:
                        continue

                    if not text:
                        continue

                    print(f"[WakeWord Heard]: '{text}'")
                    if any(w in text for w in ("jarvis", "javis", "travis", "service", self.wake_word)):
                        print(f"[WakeWord] Wake word trigger matched in: '{text}'!")
                        self.wake_signal.emit()
                        self.wake_word_detected.emit()
                        self.pause_listening()
                        self._capture_and_transcribe_on_source(source, recognizer)

        except Exception as mic_loop_err:
            print(f"[WakeWord] Continuous microphone loop ended: {mic_loop_err}")

    def _capture_and_transcribe_on_source(self, source, recognizer):
        """Records command following wake-word detection using existing active audio source."""
        self.listening_started.emit()
        try:
            import speech_recognition as sr
            cmd_audio = None
            try:
                cmd_audio = recognizer.listen(source, timeout=4.0, phrase_time_limit=9.0)
            except sr.WaitTimeoutError:
                print("[WakeWord] No follow-up words spoken (timeout).")
                self.speech_transcribed.emit("__WAKE_ONLY__")
                return

            if not cmd_audio:
                self.speech_transcribed.emit("__WAKE_ONLY__")
                return

            wav_data = cmd_audio.get_wav_data()
            transcribed = ""
            if self.voice_mgr and self.voice_mgr.groq_key:
                try:
                    transcribed = self.voice_mgr.transcribe_audio_groq(wav_data)
                except Exception as groq_err:
                    print(f"[WakeWord] Groq transcription error: {groq_err}")

            if not transcribed:
                try:
                    transcribed = recognizer.recognize_google(cmd_audio, language="ta-IN")
                except Exception:
                    try:
                        transcribed = recognizer.recognize_google(cmd_audio, language="en-IN")
                    except Exception:
                        transcribed = ""

            cleaned = (transcribed or "").strip()
            print(f"[WakeWord] Raw transcribed: '{cleaned}'")

            lower = cleaned.lower().strip()
            lower_no_punc = re.sub(r"[^\w\s]", "", lower).strip()
            if not lower_no_punc or lower_no_punc in ("jarvis", "javis", "hey jarvis", "hi jarvis", "travis", "service"):
                print("[WakeWord] Wake word heard alone without command payload.")
                self.speech_transcribed.emit("__WAKE_ONLY__")
                return

            for prefix in ("jarvis ", "javis ", "hey jarvis ", "hi jarvis "):
                if lower.startswith(prefix):
                    cleaned = cleaned[len(prefix):].strip()
                    break

            if cleaned:
                print(f"[WakeWord] Follow-up command transcribed: '{cleaned}'")
                self.speech_transcribed.emit(cleaned)
            else:
                self.speech_transcribed.emit("__WAKE_ONLY__")
        except Exception as e:
            err_msg = f"Audio capture/transcribe exception: {type(e).__name__}: {e}"
            print(f"[WakeWord] {err_msg}")
            self.error_occurred.emit(err_msg)
            self.voice_error.emit(err_msg)
        finally:
            self.resume_listening()

    def _capture_and_transcribe(self, mic=None, recognizer=None):
        """Records command following Porcupine wake-word detection."""
        self.listening_started.emit()
        try:
            import speech_recognition as sr
            if mic is None:
                mic = sr.Microphone()
            if recognizer is None:
                recognizer = sr.Recognizer()
                recognizer.energy_threshold = 280
                recognizer.dynamic_energy_threshold = False
                recognizer.pause_threshold = 0.6

            cmd_audio = None
            try:
                with mic as source:
                    cmd_audio = recognizer.listen(source, timeout=4.0, phrase_time_limit=9.0)
            except sr.WaitTimeoutError:
                print("[WakeWord] No follow-up words spoken (timeout).")
                self.speech_transcribed.emit("__WAKE_ONLY__")
                return

            if not cmd_audio:
                self.speech_transcribed.emit("__WAKE_ONLY__")
                return

            wav_data = cmd_audio.get_wav_data()
            transcribed = ""
            if self.voice_mgr and self.voice_mgr.groq_key:
                try:
                    transcribed = self.voice_mgr.transcribe_audio_groq(wav_data)
                except Exception as groq_err:
                    print(f"[WakeWord] Groq transcription error: {groq_err}")

            if not transcribed:
                try:
                    transcribed = recognizer.recognize_google(cmd_audio, language="ta-IN")
                except Exception:
                    try:
                        transcribed = recognizer.recognize_google(cmd_audio, language="en-IN")
                    except Exception:
                        transcribed = ""

            cleaned = (transcribed or "").strip()
            print(f"[WakeWord] Raw transcribed: '{cleaned}'")

            lower = cleaned.lower().strip()
            lower_no_punc = re.sub(r"[^\w\s]", "", lower).strip()
            if not lower_no_punc or lower_no_punc in ("jarvis", "javis", "hey jarvis", "hi jarvis", "travis", "service"):
                print("[WakeWord] Wake word heard alone without command payload.")
                self.speech_transcribed.emit("__WAKE_ONLY__")
                return

            for prefix in ("jarvis ", "javis ", "hey jarvis ", "hi jarvis "):
                if lower.startswith(prefix):
                    cleaned = cleaned[len(prefix):].strip()
                    break

            if cleaned:
                print(f"[WakeWord] Follow-up command transcribed: '{cleaned}'")
                self.speech_transcribed.emit(cleaned)
            else:
                self.speech_transcribed.emit("__WAKE_ONLY__")
        except Exception as e:
            err_msg = f"Audio capture/transcribe exception: {type(e).__name__}: {e}"
            print(f"[WakeWord] {err_msg}")
            self.error_occurred.emit(err_msg)
            self.voice_error.emit(err_msg)
        finally:
            self.resume_listening()


JarvisEarsWorker = WakeWordThread
RexiEarsWorker = WakeWordThread

# ============================================================================
# Action Worker Thread (Safety Net + The Brain + Voice output)
# ============================================================================
class JarvisActionWorker(QThread):
    status_signal    = pyqtSignal(str)
    text_chunk_ready = pyqtSignal(str)    # Real-time sentence-by-sentence emission for UI & TTS
    chunk_received   = pyqtSignal(str)
    finished_stream  = pyqtSignal(str)
    action_finished  = pyqtSignal(str)
    error_occurred   = pyqtSignal(str)
    command_signal   = pyqtSignal(str, dict)

    def __init__(self, client, model: str, prompt: str, parent=None,
                 safety_net: Optional[JarvisSafetyNet] = None,
                 voice_manager: Optional[JarvisVoiceManager] = None,
                 brain: Optional[JarvisBrain] = None,
                 is_voice: bool = False,
                 tts_worker: Optional[JarvisTTSWorker] = None):
        super().__init__(parent)
        self.client = client
        self.model  = model
        self.prompt = prompt
        self.safety_net = safety_net
        self.voice_manager = voice_manager
        self.brain = brain
        self.is_voice = is_voice
        self.tts_worker = tts_worker

    def _search_start_menu(self, query: str) -> Optional[str]:
        dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs"),
        ]
        lq = query.lower()
        for d in dirs:
            if not os.path.exists(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(".lnk") and lq in f.lower():
                        return os.path.join(root, f)
        return None

    def _search_macos_apps(self, query: str) -> Optional[str]:
        lq = query.lower().strip()
        app_dirs = ["/Applications", os.path.expanduser("~/Applications"), "/System/Applications"]
        for adir in app_dirs:
            if os.path.exists(adir):
                try:
                    for item in os.listdir(adir):
                        if item.lower().endswith(".app") and lq in item.lower():
                            return os.path.join(adir, item)
                except Exception:
                    pass
        return None

    def _search_known_paths(self, query: str) -> Optional[str]:
        lq = query.lower()
        paths = KNOWN_EXE_PATHS.get(lq, [])
        for raw in paths:
            p = os.path.expandvars(raw)
            if os.path.isfile(p):
                return p
        return None

    def _try_launch_local(self, query: str) -> Tuple[bool, Optional[str]]:
        """3-step cross-platform local launch verification (Windows / macOS / Linux)."""
        lq = query.lower().strip()

        # Web-only apps – skip entirely
        if lq in WEB_ONLY_APPS:
            return False, None

        found = None

        # macOS: native application bundle search & LaunchServices
        if sys.platform == "darwin":
            self.status_signal.emit(f"Checking macOS Applications for '{query}'...")
            time.sleep(0.06)
            found = self._search_macos_apps(query)
            if not found:
                try:
                    res = subprocess.run(["open", "-a", query], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        self.status_signal.emit(f"Launched '{query}' via macOS LaunchServices ✓")
                        return True, query
                except Exception:
                    pass

        # Windows: Known paths & Start Menu
        if not found and sys.platform == "win32":
            self.status_signal.emit(f"Searching known paths for '{query}'...")
            time.sleep(0.06)
            found = self._search_known_paths(query)

            if not found:
                self.status_signal.emit("Scanning Start Menu shortcuts...")
                time.sleep(0.06)
                found = self._search_start_menu(query)

        # Cross-platform: system PATH check (shutil.which)
        if not found:
            self.status_signal.emit("Checking system PATH...")
            time.sleep(0.04)
            found = shutil.which(lq) or shutil.which(lq + ".exe")

        # Windows: AppOpener fallback
        if not found and APPOPENER_AVAILABLE and sys.platform == "win32":
            self.status_signal.emit(f"Trying AppOpener for '{query}'...")
            time.sleep(0.04)
            try:
                AppOpener.open(query, throw_error=True)
                self.status_signal.emit(f"AppOpener launched '{query}' ✓")
                return True, "AppOpener"
            except Exception:
                pass

        if not found:
            return False, None

        # Step 2: Launch and verify
        self.status_signal.emit(f"Found: {found}")
        time.sleep(0.06)
        try:
            if sys.platform == "win32":
                os.startfile(found)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", found])
            else:
                subprocess.Popen(["xdg-open", found])
        except Exception:
            return False, None

        # Step 3: Confirm
        self.status_signal.emit(f"Launched '{query}' locally ✓")
        return True, found

    def run(self):
        clean = self.prompt.strip()
        lower = clean.lower()

        # Step 0: The Safety Net Guardrail validation
        if self.safety_net:
            self.status_signal.emit("Safety Net: Checking guardrail...")
            is_safe, reason = self.safety_net.validate_command(clean)
            if not is_safe:
                self.status_signal.emit("Safety Net: Blocked 🛡️")
                self.error_occurred.emit(f"🛡️ Safety Net Guardrail:\n{reason}")
                return

        self.status_signal.emit("The Brain: Streaming intent...")

        # Step 1: Stateful Chat Session & Streaming
        brain = self.brain
        if not brain and self.client:
            brain = JarvisBrain(api_key="", model_name=self.model)
            brain.client = self.client

        chat = brain.get_or_create_chat() if brain else None

        if chat:
            try:
                stream = None
                if hasattr(chat, "send_message_stream"):
                    stream = chat.send_message_stream(clean)
                elif hasattr(chat, "send_message"):
                    stream = chat.send_message(
                        clean,
                        stream=True,
                        generation_config={"response_mime_type": "application/json"}
                    )

                if stream:
                    accumulated_buffer = ""
                    is_command = False
                    seen_reply_len = 0
                    active_sentence_remainder = ""
                    first_sentence = True

                    for chunk in stream:
                        text_chunk = getattr(chunk, "text", "") or ""
                        if not text_chunk:
                            continue

                        accumulated_buffer += text_chunk
                        self.chunk_received.emit(text_chunk)

                        # Step 6: Command Execution Detection
                        if not is_command:
                            if re.search(r'\"type\"\s*:\s*\"command\"|\'type\'\s*:\s*\'command\'', accumulated_buffer, re.IGNORECASE):
                                is_command = True
                                self.status_signal.emit("Action command detected...")
                                # Stop emitting TTS chunks and clear any pending TTS queue
                                if self.tts_worker:
                                    self.tts_worker.clear_queue()

                        # Step 3: Partial extraction of "reply_text"
                        partial_text, is_reply_done = extract_partial_reply_text(accumulated_buffer)

                        # Step 4: Sentence-by-sentence emission (only if NOT a command)
                        if not is_command and partial_text:
                            if len(partial_text) > seen_reply_len:
                                new_chars = partial_text[seen_reply_len:]
                                seen_reply_len = len(partial_text)
                                active_sentence_remainder += new_chars

                            ready_sentences, active_sentence_remainder = split_complete_sentences(
                                active_sentence_remainder, is_final=is_reply_done
                            )
                            for sentence in ready_sentences:
                                if first_sentence:
                                    self.status_signal.emit("Jarvis is speaking...")
                                    first_sentence = False
                                self.text_chunk_ready.emit(sentence)

                    # Stream finished: handle remaining text if chat
                    if not is_command and active_sentence_remainder.strip():
                        self.text_chunk_ready.emit(active_sentence_remainder.strip())
                        active_sentence_remainder = ""

                    # Parse final payload
                    payload = parse_brain_payload(accumulated_buffer)
                    p_type = str(payload.get("type", "chat")).strip().lower()
                    cmd_id = str(payload.get("command_id", "NONE")).strip()
                    cmd_args = payload.get("command_args")
                    if not isinstance(cmd_args, dict):
                        cmd_args = {}
                    reply_text = str(payload.get("reply_text", "")).strip()
                    if not reply_text:
                        reply_text = partial_text or "Understood."

                    if is_command or p_type == "command":
                        self.status_signal.emit(f"Executing: {cmd_id}")
                        self.action_finished.emit(reply_text)
                        self.finished_stream.emit(reply_text)

                        # Speak final command confirmation if TTS enabled
                        should_speak = bool(
                            self.is_voice or getattr(self.parent(), "tts_enabled", False)
                        )
                        if self.tts_worker and should_speak:
                            self.tts_worker.enqueue_sentence(reply_text)

                        if cmd_id.upper() not in ("NONE", ""):
                            self.command_signal.emit(cmd_id, cmd_args)
                    else:
                        self.status_signal.emit("Response complete ✓")
                        self.action_finished.emit(reply_text)
                        self.finished_stream.emit(reply_text)

                    return

            except Exception as exc:
                print(f"[Brain] Streaming error: {exc}")
                if brain:
                    brain.chat_session = None

        # Fallbacks (offline heuristics if Gemini fails or is offline)
        if lower.startswith("play "):
            song = clean[5:].strip()
            if song:
                enc = urllib.parse.quote_plus(song)
                url = f"https://www.youtube.com/results?search_query={enc}"
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                msg = f"Playing {song} on YouTube! 🎵"
                self.status_signal.emit("Media playback started ✓")
                self.action_finished.emit(msg)
                if self.tts_worker and (self.is_voice or getattr(self.parent(), "tts_enabled", False)):
                    self.tts_worker.enqueue_sentence(msg)
                return

        if lower.startswith("open "):
            app = clean[5:].strip()
            if app:
                ok, detail = self._try_launch_local(app)
                if ok:
                    msg = f"Launched {app} on your PC! 💻"
                else:
                    url = SPECIAL_URLS.get(app.lower(), f"https://www.{app.replace(' ', '')}.com")
                    try:
                        webbrowser.open(url)
                    except Exception:
                        pass
                    msg = f"Local app not found.\nOpened {url} in your browser! 🌐"
                self.action_finished.emit(msg)
                if self.tts_worker and (self.is_voice or getattr(self.parent(), "tts_enabled", False)):
                    self.tts_worker.enqueue_sentence(msg)
                return

        self.status_signal.emit("The Brain: Offline or API error ⚠️")
        self.error_occurred.emit("Unable to reach Gemini logic core. Please check internet connection or API key.")

        self.status_signal.emit("Gemini error ⚠️")
        self.error_occurred.emit(last_err)

RexiActionWorker = JarvisActionWorker


# ============================================================================
# Minimal Listening Indicator Widget (Jarvis Sleek Starburst Pill)
# ============================================================================
class JarvisListeningHUD(QWidget):
    """Sleek floating translucent pill widget that appears when Jarvis is listening."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(175, 44)

        container = QFrame(self)
        container.setObjectName("pillContainer")
        container.setFixedSize(175, 44)

        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(20); sh.setColor(QColor(0,0,0,180)); sh.setOffset(0,3)
        container.setGraphicsEffect(sh)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(8)

        # Avatar: Smooth circular starburst avatar from wallpaper.png
        self.icon_lbl = QLabel(container)
        self.icon_lbl.setFixedSize(28, 28)
        self.icon_lbl.setStyleSheet("background: transparent; border: none;")
        avatar_px = load_circular_avatar("wallpaper.png", 28)
        if avatar_px and not avatar_px.isNull():
            self.icon_lbl.setPixmap(avatar_px)
        else:
            self.icon_lbl.setText("🎙️")
            self.icon_lbl.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        layout.addWidget(self.icon_lbl)

        self.text_lbl = QLabel("Listening, Sir...", container)
        self.text_lbl.setStyleSheet(f"""
            QLabel {{
                color: #FFFFFF;
                font-family: '{FONT_FAMILY}';
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self.text_lbl)
        layout.addStretch()

        container.setStyleSheet(f"""
            QFrame#pillContainer {{
                background-color: rgba(18, 20, 28, 0.94);
                border: 1px solid rgba(163, 71, 255, 0.65);
                border-radius: 22px;
            }}
        """)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.addWidget(container)

    def show_near_bot(self, bot_rect: QRect):
        scr = QApplication.primaryScreen().geometry()
        x = bot_rect.center().x() - self.width() // 2
        y = bot_rect.top() - self.height() - 10
        if y < 10:
            y = bot_rect.bottom() + 10
        x = max(10, min(x, scr.width() - self.width() - 10))
        y = max(10, min(y, scr.height() - self.height() - 10))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

ListeningWidget = JarvisListeningHUD

# ============================================================================
# Spotlight Dialog
# ============================================================================
class SpotlightDialog(QWidget):
    def __init__(self, bot, parent=None):
        super().__init__(parent)
        self.bot = bot
        self.drag_position = QPoint()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(520, 52)
        self._build()
        self._position_below_bot()

    def _position_below_bot(self):
        scr = QApplication.primaryScreen().geometry()
        bp = self.bot.pos()
        bw = self.bot.width()
        bh = self.bot.height()
        sw = self.width()
        sh = self.height()
        margin = 10

        # Preferred: Align search bar so bot icon sits at its top-left edge
        x = bp.x()

        # If placing it there would push the search bar off the right edge of the screen,
        # dynamically switch so the bot icon aligns with the top-right edge instead:
        if x + sw > scr.x() + scr.width() - margin:
            x = bp.x() + bw - sw

        # Clamp x to screen bounds
        x = max(scr.x() + margin, min(x, scr.x() + scr.width() - sw - margin))

        # Position directly below the bot icon
        y = bp.y() + bh + 8
        if y + sh > scr.y() + scr.height() - margin:
            y = max(scr.y() + margin, bp.y() - sh - 8)

        self.move(x, y)

    def closeEvent(self, e):
        if self.bot and getattr(self.bot, "spotlight", None) == self:
            self.bot.spotlight = None
        super().closeEvent(e)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        frame = QFrame(self)
        frame.setStyleSheet(f"""QFrame{{background-color:{COLOR_GLASS_BG};
            border:1px solid {COLOR_GLASS_BORDER};border-radius:12px;}}""")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(24); sh.setColor(QColor(0,0,0,180)); sh.setOffset(0,4)
        frame.setGraphicsEffect(sh)
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(14, 6, 14, 6)
        fl.setSpacing(10)

        ico = QLabel(frame)
        pm = load_search_icon(22, self.bot.accent_color)
        if pm:
            ico.setPixmap(pm)
        else:
            ico.setText("✦")
        ico.setStyleSheet("border:none;background:transparent;")
        fl.addWidget(ico)

        self.entry = QLineEdit(frame)
        self.entry.setPlaceholderText("Ask Jarvis, or type 'open [app]' / 'play [song]'...")
        self.entry.setStyleSheet(f"""QLineEdit{{background:transparent;border:none;
            color:{COLOR_TEXT_PRIMARY};font-family:'{FONT_FAMILY}';font-size:12px;
            selection-background-color:{self.bot.accent_color};selection-color:#09090B;}}
            QLineEdit::placeholder{{color:{COLOR_TEXT_MUTED};}}""")
        self.entry.returnPressed.connect(self._submit)
        fl.addWidget(self.entry)

        for txt, sz in [("↵", 11), ("Esc", 9)]:
            b = QLabel(txt, frame)
            b.setStyleSheet(f"""QLabel{{background-color:{COLOR_GLASS_CARD};
                color:{COLOR_TEXT_MUTED};font-family:'{FONT_FAMILY}';font-size:{sz}px;
                font-weight:bold;border-radius:4px;padding:2px 5px;
                border:1px solid {COLOR_GLASS_SUBTLE};}}""")
            fl.addWidget(b)

        lay.addWidget(frame)

    def _submit(self):
        t = self.entry.text().strip()
        if t:
            self.close()
            QTimer.singleShot(0, lambda prompt=t: self.bot.process_prompt(prompt))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_position = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(e.globalPosition().toPoint() - self.drag_position)


# ============================================================================
# Answer HUD (320x220, magnetic, glass)
# ============================================================================
class JarvisAnswerHUD(QWidget):
    def __init__(self, bot, prompt: str, parent=None):
        super().__init__(parent)
        self.bot = bot
        self.prompt = prompt
        self.drag_position = QPoint()
        self.first_chunk = True
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(200, 140)
        self.setMaximumWidth(400)

        # Restore user's preferred compact size from local jarvis_config.json
        cfg = load_config()
        saved_w = cfg.get("answer_window_width", self.bot.config.get("answer_window_width", 260))
        saved_h = cfg.get("answer_window_height", self.bot.config.get("answer_window_height", 210))
        w = max(200, min(int(saved_w), 400))
        h = max(140, min(int(saved_h), 450))
        self.resize(w, h)
        self._build()
        self._place()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        accent = self.bot.accent_color

        self.container = QFrame(self)
        self.container.setObjectName("MC")
        self.container.setStyleSheet(f"""QFrame#MC{{
            background-color:{COLOR_GLASS_BG};
            border:1px solid {COLOR_GLASS_BORDER};
            border-radius:12px;}}""")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(24); sh.setColor(QColor(0,0,0,190)); sh.setOffset(0,4)
        self.container.setGraphicsEffect(sh)

        il = QVBoxLayout(self.container)
        il.setContentsMargins(10, 6, 10, 8)
        il.setSpacing(4)

        # Top row: Prompt on the left, sleek hover-active close button on the right (No dead space)
        top_row = QFrame(self.container)
        top_row.setStyleSheet("background:transparent;border:none;")
        tl = QHBoxLayout(top_row)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        short = self.prompt if len(self.prompt) <= 45 else self.prompt[:42] + "..."
        pl = QLabel(f"You: {short}", top_row)
        pl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-family:'{FONT_FAMILY}';"
                         f"font-size:9px;font-style:italic;border:none;background:transparent;")
        tl.addWidget(pl, 1)

        cb = QPushButton("×", top_row)
        cb.setFixedSize(16, 16)
        cb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cb.setStyleSheet(f"""QPushButton{{background:transparent;color:{COLOR_TEXT_MUTED};
            font-size:13px;font-weight:bold;border:none;border-radius:8px;}}
            QPushButton:hover{{background:rgba(255, 59, 48, 0.25);color:#FF453A;}}""")
        cb.clicked.connect(self.close)
        tl.addWidget(cb, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        il.addWidget(top_row)

        # Response
        self.response = QTextBrowser(self.container)
        self.response.setPlainText("Jarvis is thinking… 💭")
        self.response.setStyleSheet(f"""QTextBrowser{{
            background-color:{COLOR_GLASS_CARD};color:{COLOR_TEXT_PRIMARY};
            font-family:'{FONT_FAMILY}';font-size:10px;
            border:1px solid {COLOR_GLASS_SUBTLE};border-radius:8px;padding:6px;
            selection-background-color:{accent};selection-color:#09090B;}}""")
        il.addWidget(self.response, 1)

        # Live Feed
        self.feed = QLabel("Live Feed: Initializing...", self.container)
        self.feed.setStyleSheet(f"QLabel{{color:{accent};font-family:'{FONT_FAMILY}';"
                                f"font-size:9pt;font-style:italic;background:transparent;"
                                f"border:none;padding:1px 2px;}}")
        il.addWidget(self.feed)

        # Bottom Bar
        bb = QFrame(self.container)
        bb.setStyleSheet("background:transparent;border:none;")
        bl = QHBoxLayout(bb)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(5)
        self.fu = QLineEdit(bb)
        self.fu.setPlaceholderText("Follow-up...")
        self.fu.setStyleSheet(f"""QLineEdit{{background-color:{COLOR_GLASS_CARD};
            color:{COLOR_TEXT_PRIMARY};font-family:'{FONT_FAMILY}';font-size:10px;
            border:1px solid {COLOR_GLASS_SUBTLE};border-radius:6px;padding:3px 6px;}}""")
        self.fu.returnPressed.connect(self._followup)
        bl.addWidget(self.fu, 1)
        for txt, slot in [("Send", self._followup), ("Copy", self._copy), ("Memories", self._open_memories)]:
            btn = QPushButton(txt, bb)
            btn.setStyleSheet(f"""QPushButton{{background:rgba(255,255,255,0.08);
                border:1px solid {COLOR_GLASS_SUBTLE};color:{COLOR_TEXT_PRIMARY};
                font-family:'{FONT_FAMILY}';font-size:9px;border-radius:6px;padding:3px 8px;}}
                QPushButton:hover{{background:{accent};color:#09090B;border-color:{accent};}}""")
            btn.clicked.connect(slot)
            bl.addWidget(btn)

        # Resizable grip for manual corner drag-to-resize
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setStyleSheet("""
            QSizeGrip {
                width: 12px;
                height: 12px;
                background: transparent;
            }
        """)
        bl.addWidget(self.sizegrip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        il.addWidget(bb)
        lay.addWidget(self.container)

    def _place(self):
        scr = QApplication.primaryScreen().geometry()
        bp = self.bot.pos()
        bw = self.bot.width()
        sw = self.width()
        x = bp.x() + bw + 10 if bp.x() + bw + sw + 10 <= scr.width() else bp.x() - sw - 10
        y = max(30, min(bp.y() - 20, scr.height() - self.height() - 40))
        self.move(max(10, min(x, scr.width() - sw - 10)), y)

    def update_feed(self, s):
        self.feed.setText(f"Live Feed: {s}")

    def append_sentence(self, sentence: str):
        if not sentence or not sentence.strip():
            return
        if self.first_chunk:
            self.response.clear()
            self.first_chunk = False
            self.response.insertPlainText(sentence.strip())
        else:
            self.response.insertPlainText(" " + sentence.strip())
        self.response.moveCursor(QTextCursor.MoveOperation.End)

    def append_chunk(self, c):
        if self.first_chunk:
            self.response.clear()
            self.first_chunk = False
        self.response.insertPlainText(c)
        self.response.moveCursor(QTextCursor.MoveOperation.End)

    def finish_stream(self, _):
        pass

    def finish_action(self, msg):
        self.response.setPlainText(msg)

    def display_error(self, err):
        if any(k in str(err) for k in ("🎤", "Audio", "PyAudio", "Porcupine", "WakeWord", "Microphone")):
            self.response.setPlainText(f"⚠️ Audio/Mic Error:\n\n{err}")
        else:
            self.response.setPlainText(
                f"⚠️ Error:\n\n{err}\n\n"
                "💡 Check GEMINI_API_KEY (Right-click → Set API Key).")

    def _followup(self):
        t = self.fu.text().strip()
        if t:
            self.fu.clear()
            QTimer.singleShot(0, lambda prompt=t: self.bot.process_prompt(prompt))

    def _copy(self):
        QApplication.clipboard().setText(self.response.toPlainText())

    def _open_memories(self):
        dlg = MemoryManagerDialog(self.bot, self)
        dlg.exec()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.width() >= 180 and self.height() >= 120:
            self.bot.config["answer_window_width"] = self.width()
            self.bot.config["answer_window_height"] = self.height()
            save_config(self.bot.config)

    def closeEvent(self, e):
        if self.width() >= 180 and self.height() >= 120:
            self.bot.config["answer_window_width"] = self.width()
            self.bot.config["answer_window_height"] = self.height()
            save_config(self.bot.config)
        if self.bot and getattr(self.bot, "answer_hud", None) == self:
            self.bot.answer_hud = None
        super().closeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_position = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(e.globalPosition().toPoint() - self.drag_position)

AnswerHUD = JarvisAnswerHUD


# ============================================================================
# Memory Manager Dialog (View / Add / Delete Stored Memories)
# ============================================================================
class MemoryManagerDialog(QDialog):
    """Sleek dark HUD dialog to view, add, or delete stored memories/facts in jarvis_config.json."""
    def __init__(self, bot, parent=None):
        super().__init__(parent)
        self.bot = bot
        self.setWindowTitle("Jarvis Memory Core")
        self.setFixedSize(500, 420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        accent = getattr(self.bot, "accent_color", DEFAULT_ACCENT)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_GLASS_BG};
                color: {COLOR_TEXT_PRIMARY};
                font-family: '{FONT_FAMILY}';
            }}
            QTableWidget {{
                background-color: {COLOR_GLASS_CARD};
                color: {COLOR_TEXT_PRIMARY};
                gridline-color: {COLOR_GLASS_SUBTLE};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 8px;
                font-size: 11px;
                selection-background-color: {accent};
                selection-color: #09090B;
            }}
            QHeaderView::section {{
                background-color: #12141C;
                color: {COLOR_TEXT_MUTED};
                font-size: 10px;
                font-weight: bold;
                border: none;
                padding: 4px;
            }}
            QPushButton {{
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid {COLOR_GLASS_SUBTLE};
                color: {COLOR_TEXT_PRIMARY};
                font-family: '{FONT_FAMILY}';
                font-size: 10px;
                font-weight: 600;
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: {accent};
                color: #09090B;
                border-color: {accent};
            }}
            QLineEdit {{
                background-color: {COLOR_GLASS_CARD};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 11px;
            }}
        """)
        self._build_ui()
        self._load_memories()

    def _build_ui(self):
        accent = getattr(self.bot, "accent_color", DEFAULT_ACCENT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Title
        title_box = QHBoxLayout()
        title_lbl = QLabel("🧠 Long-Term Memory Core", self)
        title_lbl.setStyleSheet(f"color: {accent}; font-size: 13px; font-weight: bold;")
        title_box.addWidget(title_lbl)
        title_box.addStretch()
        layout.addLayout(title_box)

        sub_lbl = QLabel("Facts, preferences, and details Jarvis will dynamically remember across sessions:", self)
        sub_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 10px;")
        layout.addWidget(sub_lbl)

        # Table
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Key / Topic", "Stored Fact"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 160)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        # Quick Add Section
        add_box = QHBoxLayout()
        self.key_in = QLineEdit(self)
        self.key_in.setPlaceholderText("Topic / Key (e.g. user_project)")
        self.val_in = QLineEdit(self)
        self.val_in.setPlaceholderText("Detail (e.g. Building an AI companion)")
        self.btn_add = QPushButton("+ Add Fact", self)
        self.btn_add.clicked.connect(self._add_memory)
        add_box.addWidget(self.key_in, 1)
        add_box.addWidget(self.val_in, 2)
        add_box.addWidget(self.btn_add)
        layout.addLayout(add_box)

        # Action Buttons
        btn_box = QHBoxLayout()
        self.btn_del = QPushButton("🗑️ Delete Selected", self)
        self.btn_del.clicked.connect(self._delete_selected)
        btn_box.addWidget(self.btn_del)

        self.btn_clear = QPushButton("⚠️ Clear All", self)
        self.btn_clear.clicked.connect(self._clear_all)
        btn_box.addWidget(self.btn_clear)

        btn_box.addStretch()

        btn_close = QPushButton("Done", self)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _load_memories(self):
        cfg = load_config()
        self.memories = cfg.get("memory", {})
        if not isinstance(self.memories, dict):
            self.memories = {}
        self.table.setRowCount(0)
        for row, (k, v) in enumerate(self.memories.items()):
            self.table.insertRow(row)
            item_k = QTableWidgetItem(str(k))
            item_v = QTableWidgetItem(str(v))
            self.table.setItem(row, 0, item_k)
            self.table.setItem(row, 1, item_v)

    def _save_and_sync(self):
        cfg = load_config()
        cfg["memory"] = self.memories
        save_config(cfg)
        self.bot.config["memory"] = self.memories
        self.bot.persist_config()
        if hasattr(self.bot, "brain") and self.bot.brain:
            self.bot.brain.update_memory_instruction(cfg)
        self._load_memories()

    def _add_memory(self):
        k = self.key_in.text().strip()
        v = self.val_in.text().strip()
        if not k or not v:
            return
        self.memories[k] = v
        self.key_in.clear()
        self.val_in.clear()
        self._save_and_sync()

    def _delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            key_item = self.table.item(row, 0)
            if key_item and key_item.text() in self.memories:
                del self.memories[key_item.text()]
                self._save_and_sync()

    def _clear_all(self):
        if self.memories:
            self.memories = {}
            self._save_and_sync()


# ============================================================================
# Auto-Update System (GitHub Releases)
# ============================================================================
def parse_version(tag: str) -> Tuple[int, ...]:
    clean = tag.strip().lstrip('vV')
    parts = []
    for token in clean.split('.'):
        digits = ''.join(c for c in token if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer_version(latest_tag: str, current_ver: str) -> bool:
    try:
        return parse_version(latest_tag) > parse_version(current_ver)
    except Exception:
        return False


class UpdateCheckWorker(QThread):
    update_available = pyqtSignal(dict, bool)  # release_dict, interactive
    up_to_date = pyqtSignal(str, bool)         # current_ver, interactive
    check_failed = pyqtSignal(str, bool)       # error_msg, interactive

    def __init__(self, current_ver: str, interactive: bool = False, parent=None):
        super().__init__(parent)
        self.current_ver = current_ver
        self.interactive = interactive

    def run(self):
        data = None
        diagnostics = []

        # Tier 0: GitHub Atom Feed (100% immune to API rate limits, fast, XML/HTML)
        try:
            feed_url = f"https://github.com/{GITHUB_REPO}/releases.atom"
            with _safe_urlopen(feed_url, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                m = re.search(r'/releases/tag/([vV]?[0-9]+(?:\.[0-9]+)+)', content)
                if m:
                    tag = m.group(1)
                    data = {
                        "tag_name": tag,
                        "html_url": f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}",
                        "body": "Jarvis update available with performance boosts and anti-vanish guards.",
                        "assets": [
                            {
                                "name": "Jarvis.exe",
                                "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis.exe",
                            },
                            {
                                "name": "Jarvis-macOS.zip",
                                "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis-macOS.zip",
                            }
                        ]
                    }
        except Exception as e:
            diagnostics.append(f"Tier 0 (Atom): {e}")

        # Tier 1: Pure Python URL redirect inspection (100% immune to API rate limits, no CLI dependencies)
        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            try:
                target = f"https://github.com/{GITHUB_REPO}/releases/latest"
                with _safe_urlopen(target, timeout=10) as resp:
                    final_url = resp.geturl()
                    tag = final_url.rstrip("/").split("/")[-1]
                    if tag and tag not in ("releases", "latest"):
                        data = {
                            "tag_name": tag,
                            "html_url": f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}",
                            "body": "Jarvis update available with performance boosts and anti-vanish guards.",
                            "assets": [
                                {
                                    "name": "Jarvis.exe",
                                    "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis.exe",
                                },
                                {
                                    "name": "Jarvis-macOS.zip",
                                    "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis-macOS.zip",
                                }
                            ]
                        }
            except Exception as e:
                diagnostics.append(f"Tier 1 (Redirect): {e}")

        # Tier 2: HTML tag regex on releases page (rate-limit immune)
        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            try:
                releases_url = f"https://github.com/{GITHUB_REPO}/releases"
                with _safe_urlopen(releases_url, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                    m = re.search(r'/releases/tag/([vV]?[0-9]+(?:\.[0-9]+)+)', html)
                    if m:
                        tag = m.group(1)
                        data = {
                            "tag_name": tag,
                            "html_url": f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}",
                            "body": "Jarvis update available with performance boosts and anti-vanish guards.",
                            "assets": [
                                {
                                    "name": "Jarvis.exe",
                                    "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis.exe",
                                },
                                {
                                    "name": "Jarvis-macOS.zip",
                                    "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis-macOS.zip",
                                }
                            ]
                        }
            except Exception as e:
                diagnostics.append(f"Tier 2 (HTML regex): {e}")

        # Tier 3: Git CLI remote inspection
        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            try:
                cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                cmd = ["git", "ls-remote", "--tags", f"https://github.com/{GITHUB_REPO}.git"]
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=cflags)
                tags = re.findall(r'refs/tags/([vV]?[0-9]+(?:\.[0-9]+)+)', p.stdout)
                if tags:
                    sorted_tags = sorted(set(tags), key=parse_version)
                    tag = sorted_tags[-1]
                    data = {
                        "tag_name": tag,
                        "html_url": f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}",
                        "body": "Jarvis update available.",
                        "assets": [
                            {
                                "name": "Jarvis.exe",
                                "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis.exe",
                            },
                            {
                                "name": "Jarvis-macOS.zip",
                                "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/Jarvis-macOS.zip",
                            }
                        ]
                    }
            except Exception as e:
                diagnostics.append(f"Tier 3 (Git CLI): {e}")

        # Tier 4: curl.exe CLI fallback with --insecure
        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            try:
                fallback_tag = self._get_tag_via_curl()
                if fallback_tag:
                    data = {
                        "tag_name": fallback_tag,
                        "html_url": f"https://github.com/{GITHUB_REPO}/releases/tag/{fallback_tag}",
                        "body": "Jarvis update available.",
                        "assets": [
                            {
                                "name": "Jarvis.exe",
                                "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{fallback_tag}/Jarvis.exe",
                            },
                            {
                                "name": "Jarvis-macOS.zip",
                                "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{fallback_tag}/Jarvis-macOS.zip",
                            }
                        ]
                    }
            except Exception as e:
                diagnostics.append(f"Tier 4 (curl): {e}")

        # Tier 5: GitHub REST API
        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            try:
                api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                with _safe_urlopen(api_url, headers={"Accept": "application/vnd.github.v3+json"}, timeout=10) as resp:
                    parsed = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    if isinstance(parsed, dict) and "tag_name" in parsed:
                        data = parsed
            except Exception as e:
                diagnostics.append(f"Tier 5 (GitHub API): {e}")

        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            print(f"[UpdateChecker] All tiers failed to fetch release info:\n" + "\n".join(diagnostics))
            self.check_failed.emit("Could not reach update server. Check internet connection.", self.interactive)
            return

        latest_tag = data.get("tag_name", "")
        if is_newer_version(latest_tag, self.current_ver):
            self.update_available.emit(data, self.interactive)
        else:
            self.up_to_date.emit(self.current_ver, self.interactive)

    def _get_tag_via_curl(self) -> Optional[str]:
        target = f"https://github.com/{GITHUB_REPO}/releases/latest"
        try:
            cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            cmd = ["curl.exe", "-k", "-s", "-I", target]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=cflags)
            for line in p.stdout.splitlines():
                if line.lower().startswith("location:"):
                    loc = line.split(":", 1)[1].strip()
                    tag = loc.rstrip("/").split("/")[-1]
                    if tag and tag not in ("releases", "latest"):
                        return tag
        except Exception:
            pass
        return None


class UpdateDownloadWorker(QThread):
    progress = pyqtSignal(int, int, str)     # current_bytes, total_bytes, text
    download_complete = pyqtSignal(str, str) # file_path, mode ('exe', 'zip', 'git', 'py')
    download_failed = pyqtSignal(str)

    def __init__(self, release_info: dict, parent=None):
        super().__init__(parent)
        self.release_info = release_info

    def run(self):
        try:
            is_frozen = getattr(sys, "frozen", False)
            assets = self.release_info.get("assets", [])

            # Windows standalone (.exe)
            if sys.platform == "win32" and is_frozen:
                dl_url = None
                for a in assets:
                    if a.get("name", "").lower().endswith(".exe"):
                        dl_url = a.get("browser_download_url")
                        break
                if not dl_url:
                    self.download_failed.emit("Windows executable (.exe) not found in release.")
                    return
                target_file = os.path.join(tempfile.gettempdir(), f"Jarvis_update_{int(time.time())}.exe")
                self._download_file(dl_url, target_file)
                self.download_complete.emit(target_file, "exe")
                return

            # macOS standalone (.zip)
            if sys.platform == "darwin" and is_frozen:
                dl_url = None
                for a in assets:
                    if a.get("name", "").lower().endswith(".zip"):
                        dl_url = a.get("browser_download_url")
                        break
                if not dl_url:
                    self.download_failed.emit("macOS archive (.zip) not found in release.")
                    return
                target_file = os.path.join(tempfile.gettempdir(), f"Jarvis_update_{int(time.time())}.zip")
                self._download_file(dl_url, target_file)
                self.download_complete.emit(target_file, "zip")
                return

            # Running from Python source / git repo
            app_dir = get_app_dir()
            git_dir = os.path.join(app_dir, ".git")
            if os.path.isdir(git_dir):
                self.progress.emit(0, 0, "Pulling updates via git...")
                res = subprocess.run(["git", "pull", "origin", "main"], cwd=app_dir, capture_output=True, text=True)
                if res.returncode == 0:
                    self.download_complete.emit(app_dir, "git")
                    return

            # Direct python script download
            self.progress.emit(0, 0, "Downloading latest jarvis.pyw...")
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/jarvis.pyw"
            target_file = os.path.join(tempfile.gettempdir(), f"jarvis_update_{int(time.time())}.pyw")
            self._download_file(raw_url, target_file)
            self.download_complete.emit(target_file, "py")

        except Exception as exc:
            self.download_failed.emit(str(exc))

    def _download_file(self, url: str, dest_path: str):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Jarvis-Companion"}
        try:
            with _safe_urlopen(url, headers=headers, timeout=25) as resp:
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 65536
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            mb_cur = downloaded / (1024 * 1024)
                            mb_tot = total / (1024 * 1024)
                            self.progress.emit(downloaded, total, f"Downloading: {mb_cur:.1f} MB / {mb_tot:.1f} MB ({pct}%)")
                        else:
                            mb_cur = downloaded / (1024 * 1024)
                            self.progress.emit(downloaded, 0, f"Downloading: {mb_cur:.1f} MB")
            return
        except Exception:
            pass

        self.progress.emit(0, 0, "Downloading via fallback stream...")
        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        cmd = ["curl.exe", "-k", "-L", "-s", "-H", "User-Agent: Jarvis-Companion", "-o", dest_path, url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, creationflags=cflags)
        if res.returncode != 0 or not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
            raise RuntimeError("Download could not be completed.")


class UpdateDialog(QWidget):
    def __init__(self, bot, release_info: dict, parent=None):
        super().__init__(parent)
        self.bot = bot
        self.release_info = release_info
        self.drag_position = QPoint()
        self.download_worker: Optional[UpdateDownloadWorker] = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(360, 240)
        self._build()
        self._position_below_bot()

    def _position_below_bot(self):
        scr = QApplication.primaryScreen().geometry()
        bp = self.bot.pos()
        x = bp.x() + (self.bot.width() - self.width()) // 2
        y = bp.y() + self.bot.height() + 8
        x = max(10, min(x, scr.width() - self.width() - 10))
        y = max(10, min(y, scr.height() - self.height() - 10))
        self.move(x, y)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        accent = self.bot.accent_color

        frame = QFrame(self)
        frame.setStyleSheet(f"""QFrame{{
            background-color:{COLOR_GLASS_BG};
            border:1px solid {COLOR_GLASS_BORDER};
            border-radius:12px;}}""")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(24); sh.setColor(QColor(0, 0, 0, 190)); sh.setOffset(0, 4)
        frame.setGraphicsEffect(sh)

        fl = QVBoxLayout(frame)
        fl.setContentsMargins(14, 12, 14, 12)
        fl.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        t_lbl = QLabel("● Jarvis Update Available", frame)
        t_lbl.setStyleSheet(f"color:{accent};font-family:'{FONT_FAMILY}';font-size:11px;font-weight:bold;border:none;")
        hdr.addWidget(t_lbl)
        hdr.addStretch()
        cb = QPushButton("×", frame)
        cb.setFixedSize(16, 16)
        cb.setStyleSheet(f"QPushButton{{background:transparent;color:{COLOR_TEXT_MUTED};font-size:14px;border:none;}}QPushButton:hover{{color:#FFF;}}")
        cb.clicked.connect(self.close)
        hdr.addWidget(cb)
        fl.addLayout(hdr)

        # Versions info
        latest_tag = self.release_info.get("tag_name", "v1.0.1")
        v_box = QLabel(f"Current: v{APP_VERSION}  →  New: {latest_tag}", frame)
        v_box.setStyleSheet(f"color:{COLOR_TEXT_PRIMARY};font-family:'{FONT_FAMILY}';font-size:12px;font-weight:bold;border:none;background:transparent;")
        fl.addWidget(v_box)

        # Description / Notes
        body = self.release_info.get("body", "").strip()
        if not body:
            body = "A new update for Jarvis is ready with new features and bug fixes."
        elif len(body) > 160:
            body = body[:155] + "..."
        notes = QLabel(body, frame)
        notes.setWordWrap(True)
        notes.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-family:'{FONT_FAMILY}';font-size:10px;border:none;background:transparent;")
        fl.addWidget(notes)

        # Status & Progress Bar
        self.status_lbl = QLabel("", frame)
        self.status_lbl.setStyleSheet(f"color:{accent};font-family:'{FONT_FAMILY}';font-size:9px;font-style:italic;border:none;background:transparent;")
        fl.addWidget(self.status_lbl)

        self.pbar = QProgressBar(frame)
        self.pbar.setFixedHeight(12)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet(f"""
            QProgressBar {{background-color:{COLOR_GLASS_CARD};border:1px solid {COLOR_GLASS_SUBTLE};border-radius:6px;}}
            QProgressBar::chunk {{background-color:{accent};border-radius:5px;}}
        """)
        self.pbar.hide()
        fl.addWidget(self.pbar)

        fl.addStretch()

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.btn_web = QPushButton("View on Web", frame)
        self.btn_web.setStyleSheet(f"""QPushButton{{
            background:rgba(255,255,255,0.06);border:1px solid {COLOR_GLASS_SUBTLE};
            color:{COLOR_TEXT_MUTED};font-family:'{FONT_FAMILY}';font-size:10px;
            border-radius:6px;padding:5px 10px;}}
            QPushButton:hover{{color:{COLOR_TEXT_PRIMARY};background:rgba(255,255,255,0.12);}}""")
        self.btn_web.clicked.connect(self._open_web)
        btn_box.addWidget(self.btn_web)

        btn_box.addStretch()

        self.btn_close = QPushButton("Later", frame)
        self.btn_close.setStyleSheet(f"""QPushButton{{
            background:rgba(255,255,255,0.06);border:1px solid {COLOR_GLASS_SUBTLE};
            color:{COLOR_TEXT_MUTED};font-family:'{FONT_FAMILY}';font-size:10px;
            border-radius:6px;padding:5px 10px;}}
            QPushButton:hover{{color:{COLOR_TEXT_PRIMARY};background:rgba(255,255,255,0.12);}}""")
        self.btn_close.clicked.connect(self.close)
        btn_box.addWidget(self.btn_close)

        self.btn_update = QPushButton("⚡ Update Now", frame)
        self.btn_update.setStyleSheet(f"""QPushButton{{
            background:{accent};border:none;
            color:#09090B;font-family:'{FONT_FAMILY}';font-size:10px;font-weight:bold;
            border-radius:6px;padding:5px 12px;}}
            QPushButton:hover{{background:#FFF;}}""")
        self.btn_update.clicked.connect(self._start_update)
        btn_box.addWidget(self.btn_update)

        fl.addLayout(btn_box)
        lay.addWidget(frame)

    def _open_web(self):
        url = self.release_info.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _start_update(self):
        self.btn_update.setEnabled(False)
        self.btn_update.setText("Updating...")
        self.pbar.show()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.status_lbl.setText("Preparing download...")

        self.download_worker = UpdateDownloadWorker(self.release_info, self)
        self.download_worker.progress.connect(self._on_progress)
        self.download_worker.download_complete.connect(self._on_download_complete)
        self.download_worker.download_failed.connect(self._on_download_failed)
        self.download_worker.start()

    def _on_progress(self, current: int, total: int, text: str):
        self.status_lbl.setText(text)
        if total > 0:
            pct = max(0, min(100, int(current * 100 / total)))
            self.pbar.setValue(pct)
        else:
            self.pbar.setRange(0, 0)

    def _on_download_complete(self, path: str, mode: str):
        self.status_lbl.setText("Update downloaded! Applying...")
        self.pbar.setValue(100)
        QTimer.singleShot(400, lambda: self._apply_update(path, mode))

    def _apply_update(self, path: str, mode: str):
        try:
            if mode == "exe" and sys.platform == "win32":
                curr_exe = os.path.abspath(sys.executable)
                pid = os.getpid()
                batch_file = os.path.join(tempfile.gettempdir(), f"jarvis_update_{pid}.bat")
                with open(batch_file, "w", encoding="utf-8") as bf:
                    bf.write(f"""@echo off
timeout /t 1 /nobreak >nul
:wait_loop
tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)
move /Y "{path}" "{curr_exe}" >nul
start "" "{curr_exe}"
del "%~f0"
""")
                subprocess.Popen(["cmd.exe", "/c", batch_file], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                self.bot.persist_config()
                QApplication.quit()
                return

            elif mode == "git":
                self.status_lbl.setText("Updated via git ✓ Restarting Jarvis...")
                QTimer.singleShot(800, self._restart_script)
                return

            elif mode == "py":
                curr_script = os.path.abspath(__file__)
                shutil.move(path, curr_script)
                self.status_lbl.setText("Script updated ✓ Restarting Jarvis...")
                QTimer.singleShot(800, self._restart_script)
                return

            elif mode == "zip" and sys.platform == "darwin":
                app_path = os.path.abspath(sys.executable)
                while app_path and not app_path.endswith(".app") and app_path != "/":
                    app_path = os.path.dirname(app_path)
                if app_path.endswith(".app"):
                    script = f"""
                    sleep 1
                    unzip -q -o "{path}" -d "{tempfile.gettempdir()}"
                    rm -rf "{app_path}"
                    cp -R "{tempfile.gettempdir()}/Jarvis.app" "{app_path}"
                    open "{app_path}"
                    """
                    subprocess.Popen(["/bin/bash", "-c", script])
                    self.bot.persist_config()
                    QApplication.quit()
                    return

            self.status_lbl.setText("Update applied! Please restart Jarvis.")
        except Exception as exc:
            self._on_download_failed(f"Install error: {exc}")

    def _restart_script(self):
        self.bot.persist_config()
        subprocess.Popen([sys.executable] + sys.argv)
        QApplication.quit()

    def _on_download_failed(self, err: str):
        self.pbar.hide()
        self.btn_update.setEnabled(True)
        self.btn_update.setText("Retry Update")
        self.status_lbl.setText(f"⚠️ {err}")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.drag_position = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(e.globalPosition().toPoint() - self.drag_position)


class UpToDateToast(QWidget):
    def __init__(self, bot, current_ver: str, parent=None):
        super().__init__(parent)
        self.bot = bot
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(260, 48)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        accent = self.bot.accent_color

        frame = QFrame(self)
        frame.setStyleSheet(f"""QFrame{{
            background-color:{COLOR_GLASS_BG};
            border:1px solid {COLOR_GLASS_BORDER};
            border-radius:10px;}}""")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(16); sh.setColor(QColor(0, 0, 0, 180)); sh.setOffset(0, 3)
        frame.setGraphicsEffect(sh)

        fl = QHBoxLayout(frame)
        fl.setContentsMargins(12, 6, 12, 6)
        fl.setSpacing(8)

        ico = QLabel("✓", frame)
        ico.setStyleSheet(f"color:{accent};font-size:14px;font-weight:bold;border:none;background:transparent;")
        fl.addWidget(ico)

        txt = QLabel(f"Jarvis is up to date (v{current_ver})", frame)
        txt.setStyleSheet(f"color:{COLOR_TEXT_PRIMARY};font-family:'{FONT_FAMILY}';font-size:11px;border:none;background:transparent;")
        fl.addWidget(txt)
        fl.addStretch()

        cb = QPushButton("×", frame)
        cb.setFixedSize(14, 14)
        cb.setStyleSheet(f"QPushButton{{background:transparent;color:{COLOR_TEXT_MUTED};font-size:12px;border:none;}}QPushButton:hover{{color:#FFF;}}")
        cb.clicked.connect(self.close)
        fl.addWidget(cb)

        lay.addWidget(frame)
        self._position_below_bot()
        QTimer.singleShot(3500, self.close)

    def _position_below_bot(self):
        scr = QApplication.primaryScreen().geometry()
        bp = self.bot.pos()
        x = bp.x() + (self.bot.width() - self.width()) // 2
        y = bp.y() + self.bot.height() + 8
        x = max(10, min(x, scr.width() - self.width() - 10))
        y = max(10, min(y, scr.height() - self.height() - 10))
        self.move(x, y)


# ============================================================================
# Main Bot Window
# ============================================================================
class JarvisBotWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.icon_size = max(50, min(200, int(self.config.get("icon_size", 70))))
        self.accent_color = self.config.get("accent_color", DEFAULT_ACCENT)

        # Drag & magnetic tracking
        self.press_global = QPoint()
        self.win_start = QPoint()
        self.hud_start: Optional[QPoint] = None
        self.spotlight_start: Optional[QPoint] = None
        self.update_dialog_start: Optional[QPoint] = None
        self.toast_start: Optional[QPoint] = None
        self.press_time = 0.0
        self.is_dragging = False

        # Active dialogs
        self.spotlight: Optional[SpotlightDialog] = None
        self.answer_hud: Optional[JarvisAnswerHUD] = None
        self.size_popup: Optional[SizeSliderPopup] = None
        self.worker: Optional[JarvisActionWorker] = None
        self.update_checker: Optional[UpdateCheckWorker] = None
        self.update_dialog: Optional[UpdateDialog] = None
        self.uptodate_toast: Optional[UpToDateToast] = None

        # Modular Multi-API Architecture: Brain, Voice, Safety Net
        self.active_brain_provider = self.config.get("active_brain_provider", "gemini")
        self.active_stt_provider = self.config.get("active_stt_provider", "groq_whisper")
        self.active_tts_provider = self.config.get("active_tts_provider", "elevenlabs")
        self.active_safety_provider = self.config.get("active_safety_provider", "perspective")
        self.wake_word = self.config.get("wake_word", "jarvis")
        self.voice_enabled = bool(self.config.get("voice_enabled", True))
        self.tts_enabled = bool(self.config.get("tts_enabled", False))

        # The Safety Net (Guardrail)
        self.safety_net = JarvisSafetyNet(
            api_key=self.config.get("perspective_api_key", ""),
            provider=self.active_safety_provider
        )

        # The Voice (Audio I/O)
        self.voice_manager = JarvisVoiceManager(
            groq_key=self.config.get("groq_api_key", ""),
            eleven_key=self.config.get("elevenlabs_api_key", ""),
            tts_provider=self.active_tts_provider
        )

        # The Brain (Logic)
        self.genai_client = None
        self.active_model = self.config.get("preferred_model", "gemini-3.1-flash-lite")
        self.brain = JarvisBrain(api_key=self._get_key(), model_name=self.active_model, config=self.config)
        self._init_genai()

        # Asynchronous pyttsx3 Queue System for real-time speech streaming
        self.tts_worker = JarvisTTSWorker(parent=self)
        self.tts_worker.start()

        # Continuous Background Audio Ears Worker (Bilingual Tamil & English)
        self.ears_worker: Optional[JarvisEarsWorker] = None
        self.listening_widget = JarvisListeningHUD(None)
        self._hud_was_hidden_for_listening = False
        if self.voice_enabled:
            self._start_ears_worker()

        # Frameless, translucent desktop widget (cross-platform)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.img_label = QLabel(self)
        self.img_label.setStyleSheet("background:transparent;")
        lay.addWidget(self.img_label)

        # Master pixmap tinted with saved accent_color
        self.master_px: Optional[QPixmap] = load_master_rex_pixmap(self.accent_color)
        self.apply_icon_size(self.icon_size)
        self._restore_pos()

        # Anchor-based bounce animation
        self.base_y = self.y()
        self._bounce_up = True
        self._bounce_t = QTimer(self)
        self._bounce_t.setInterval(600)
        self._bounce_t.timeout.connect(self._bounce)
        self._bounce_t.start()

        # Anti-vanish screen watchdog (keeps Jarvis visible, recovers from display/sleep shifts)
        self._watchdog_t = QTimer(self)
        self._watchdog_t.setInterval(4000)
        self._watchdog_t.timeout.connect(self._ensure_on_screen)
        self._watchdog_t.start()

        # System Tray Icon (anchors Jarvis to the Windows/macOS notification area)
        self.tray: Optional[QSystemTrayIcon] = None
        self._init_tray()

        # Non-intrusive background update check after 4s
        QTimer.singleShot(4000, lambda: self._check_for_updates(interactive=False))

    # ---- mascot pixmap & dynamic tinting ----
    def reload_mascot_pixmap(self):
        """Regenerates the master QPixmap with the current accent_color and updates display."""
        self.master_px = load_master_rex_pixmap(self.accent_color)
        self.apply_icon_size(self.icon_size)

    def apply_icon_size(self, sz: int):
        self.icon_size = max(50, min(200, sz))
        self.config["icon_size"] = self.icon_size
        if self.master_px and not self.master_px.isNull():
            scaled = self.master_px.scaled(
                self.icon_size, self.icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.img_label.setPixmap(scaled)
            self.setFixedSize(scaled.width(), scaled.height())
        else:
            self.img_label.setText("🦖")
            self.setFixedSize(self.icon_size, self.icon_size)
        self.base_y = self.y()

    def persist_config(self):
        self.config["bot_x"] = self.x()
        self.config["bot_y"] = self.y()
        self.config["icon_size"] = self.icon_size
        self.config["accent_color"] = self.accent_color
        self.config["voice_enabled"] = self.voice_enabled
        self.config["tts_enabled"] = self.tts_enabled
        save_config(self.config)

    # ---- JARVIS-Style Voice & Ears (Bilingual) ----
    def _start_ears_worker(self):
        if self.ears_worker and self.ears_worker.isRunning():
            return
        pico_key = self.config.get("picovoice_access_key", "")
        self.ears_worker = JarvisEarsWorker(
            self.voice_manager,
            access_key=pico_key,
            wake_word=self.wake_word,
            parent=self
        )
        self.ears_worker.wake_word_detected.connect(self._on_wake_word)
        self.ears_worker.speech_transcribed.connect(self._on_voice_input)
        self.ears_worker.error_occurred.connect(self._on_ears_error)
        self.ears_worker.voice_error.connect(self._on_ears_error)
        self.ears_worker.start()

    def _on_ears_error(self, err_msg: str):
        print(f"[Ears Error] {err_msg}")
        if hasattr(self, "listening_widget") and self.listening_widget:
            self.listening_widget.hide()
        if self._hud_was_hidden_for_listening:
            if self.answer_hud:
                self.answer_hud.show()
            self._hud_was_hidden_for_listening = False
        if self.answer_hud is None:
            self.answer_hud = AnswerHUD(self, "")
        if self.answer_hud:
            self.answer_hud.display_error(f"🎤 WakeWord / Audio Error:\n{err_msg}")
            if not self.answer_hud.isVisible():
                self.answer_hud.show_near(self.geometry())

    def _stop_ears_worker(self):
        if self.ears_worker:
            self.ears_worker.stop()
            self.ears_worker.wait(800)
            self.ears_worker = None

    def _on_wake_word(self):
        # Visual mascot bounce reaction upon hearing 'Jarvis'
        self.base_y = self.y()
        self.move(self.x(), self.y() - 10)
        QTimer.singleShot(250, lambda: self.move(self.x(), self.base_y))

        # Collapse / hide chat UI and show minimal listening indicator
        if self.answer_hud and self.answer_hud.isVisible():
            self._hud_was_hidden_for_listening = True
            self.answer_hud.hide()
        if self.spotlight and self.spotlight.isVisible():
            self.spotlight.hide()

        if hasattr(self, "listening_widget") and self.listening_widget:
            self.listening_widget.show_near_bot(self.geometry())

    def _on_voice_input(self, text: str):
        if hasattr(self, "listening_widget") and self.listening_widget:
            self.listening_widget.hide()

        if not text or not text.strip():
            if self._hud_was_hidden_for_listening:
                if self.answer_hud:
                    self.answer_hud.show()
                self._hud_was_hidden_for_listening = False
            return

        # Wake-word-only detection ("Jarvis" spoken without command payload)
        if text == "__WAKE_ONLY__":
            print("[Jarvis] Wake word detected alone. Responding with spoken prompt: 'Listening, Sir.'")
            if self._hud_was_hidden_for_listening:
                if self.answer_hud:
                    self.answer_hud.show()
                self._hud_was_hidden_for_listening = False
            if self.tts_worker:
                self.tts_worker.enqueue_sentence("Listening, Sir.")
            return

        self._hud_was_hidden_for_listening = False
        self.process_prompt(text.strip(), is_voice=True)

    # ---- bounce animation ----
    def _bounce(self):
        if self.is_dragging:
            return
        self.move(self.x(), self.base_y - 4 if self._bounce_up else self.base_y)
        self._bounce_up = not self._bounce_up

    def _restore_pos(self):
        scr = QApplication.primaryScreen().geometry()
        sx = self.config.get("bot_x")
        sy = self.config.get("bot_y")
        if sx is not None and sy is not None:
            x = max(0, min(int(sx), scr.width() - self.width()))
            y = max(0, min(int(sy), scr.height() - self.height()))
        else:
            x = scr.width() - self.width() - 60
            y = scr.height() - self.height() - 100
        self.move(x, y)
        self.base_y = y

    # ---- anti-vanish & system tray persistence ----
    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon_path = get_asset_path("jarvis.png")
        if not os.path.exists(icon_path):
            icon_path = get_asset_path("rex.png")
        if not os.path.exists(icon_path):
            icon_path = get_asset_path("trex_icon.png")
        tray_icon = QIcon(icon_path) if os.path.exists(icon_path) else self.windowIcon()

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip(f"Jarvis – Desktop Companion (v{APP_VERSION})")

        m = QMenu()
        m.setStyleSheet(f"""QMenu{{background-color:{COLOR_GLASS_BG};
            color:{COLOR_TEXT_PRIMARY};border:1px solid {COLOR_GLASS_BORDER};
            border-radius:8px;padding:4px;font-family:'{FONT_FAMILY}';font-size:11px;}}
            QMenu::item{{padding:6px 18px;border-radius:4px;}}
            QMenu::item:selected{{background-color:{self.accent_color};color:#09090B;}}
            QMenu::separator{{height:1px;background-color:{COLOR_GLASS_SUBTLE};margin:4px 6px;}}""")

        act_show = m.addAction("✦ Show / Bring Jarvis to Front")
        act_show.triggered.connect(self._restore_and_raise)

        act_spot = m.addAction("💬 Toggle Search Bar")
        act_spot.triggered.connect(self._toggle_spotlight)

        act_reset = m.addAction("📍 Reset Screen Position")
        act_reset.triggered.connect(self._reset_position)

        act_mem = m.addAction("🧠 Memories (View / Delete)...")
        act_mem.triggered.connect(self._open_memory_manager)

        m.addSeparator()
        act_up = m.addAction("🔄 Check for Updates...")
        act_up.triggered.connect(lambda: self._check_for_updates(interactive=True))

        act_key = m.addAction("🔑 Set API Key")
        act_key.triggered.connect(self._set_key)

        m.addSeparator()
        act_exit = m.addAction("❌ Exit Jarvis")
        act_exit.triggered.connect(self._quit)

        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._restore_and_raise()

    def _restore_and_raise(self):
        self._ensure_on_screen()
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _reset_position(self):
        scr = QApplication.primaryScreen().geometry()
        x = scr.width() - self.width() - 60
        y = scr.height() - self.height() - 100
        self.move(x, y)
        self.base_y = y
        self.persist_config()
        self._restore_and_raise()

    def _ensure_on_screen(self):
        if self.is_dragging:
            return
        screens = QApplication.screens()
        rect = self.geometry()
        on_screen = any(s.geometry().intersects(rect) for s in screens)
        if not on_screen and screens:
            prim = QApplication.primaryScreen().geometry()
            x = max(10, min(rect.x(), prim.width() - self.width() - 10))
            y = max(10, min(rect.y(), prim.height() - self.height() - 10))
            self.move(x, y)
            self.base_y = y
            self.persist_config()
        if self.isMinimized():
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.showNormal()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.setWindowState(Qt.WindowState.WindowNoState)
                self.showNormal()
        super().changeEvent(event)

    # ---- genai (stateless) ----
    def _get_key(self) -> str:
        return (os.environ.get("GEMINI_API_KEY", "").strip()
                or self.config.get("gemini_api_key", "").strip())

    def _init_genai(self):
        if not GENAI_AVAILABLE:
            return
        key = self._get_key()
        if not key:
            return
        try:
            self.genai_client = genai.Client(api_key=key)
            pref = self.config.get("preferred_model", "gemini-3.1-flash-lite")
            if pref in ("gemini-2.5-flash", "gemini-2.0-flash"):
                pref = "gemini-3.1-flash-lite"
                self.config["preferred_model"] = pref
                save_config(self.config)
            self.active_model = pref
            if self.brain:
                self.brain.api_key = key
                self.brain.model_name = self.active_model
                self.brain._init_client()
            print(f"[Jarvis] GenAI ready (stateless: {self.active_model})")
        except Exception as e:
            print(f"[Jarvis] GenAI init error: {e}")

    # ---- dispatch prompt ----
    def process_prompt(self, prompt: str, is_voice: bool = False):
        if not prompt.strip():
            return
        # Mutually Exclusive: ensure Search Bar is closed
        if self.spotlight and self.spotlight.isVisible():
            self.spotlight.close()
            self.spotlight = None

        if self.answer_hud:
            self.answer_hud.close()
            self.answer_hud = None

        self.answer_hud = AnswerHUD(self, prompt)
        self.answer_hud.show()

        if not self.genai_client:
            self._init_genai()

        self.worker = JarvisActionWorker(
            self.genai_client, self.active_model, prompt, parent=self,
            safety_net=self.safety_net,
            voice_manager=self.voice_manager,
            brain=self.brain,
            is_voice=is_voice,
            tts_worker=self.tts_worker
        )
        self.worker.status_signal.connect(self.answer_hud.update_feed)
        self.worker.text_chunk_ready.connect(self._on_text_chunk_ready)
        self.worker.chunk_received.connect(self.answer_hud.append_chunk)
        self.worker.finished_stream.connect(self.answer_hud.finish_stream)
        self.worker.action_finished.connect(self.answer_hud.finish_action)
        self.worker.error_occurred.connect(self.answer_hud.display_error)
        self.worker.command_signal.connect(self.handle_command)
        self.worker.start()

    def _on_text_chunk_ready(self, sentence: str):
        """Sentence-by-sentence callback for live UI updates and asynchronous TTS playback."""
        if self.answer_hud:
            self.answer_hud.append_sentence(sentence)

        should_speak = bool(
            getattr(self, "tts_enabled", False)
            or (self.worker and self.worker.is_voice)
        )
        if self.tts_worker and should_speak:
            self.tts_worker.enqueue_sentence(sentence)

    def handle_command(self, cmd_id: str, cmd_args: dict):
        """Executes OS, UI, and system actions dispatched by Jarvis's Brain."""
        cmd = (cmd_id or "").upper().strip()
        print(f"[Brain] Executing command: {cmd} with args: {cmd_args}")

        if cmd in ("UPDATE_MEMORY", "SAVE_MEMORY", "REMEMBER"):
            key = cmd_args.get("key")
            val = cmd_args.get("value") or cmd_args.get("fact")
            if not key and val:
                key = "fact_" + str(int(time.time()))
            if key and val:
                if "memory" not in self.config or not isinstance(self.config["memory"], dict):
                    self.config["memory"] = {}
                self.config["memory"][str(key)] = str(val)
                save_config(self.config)
                self.persist_config()
                if self.answer_hud:
                    self.answer_hud.update_feed(f"Memory saved: {key} -> {val} ✓")
                print(f"[Brain] Memory saved to disk: {key} = {val}")
                if self.brain:
                    self.brain.update_memory_instruction(self.config)

        elif cmd in ("GITHUB_SYNC", "GIT_SYNC", "GIT_PUSH", "SYNC_GITHUB"):
            if self.answer_hud:
                self.answer_hud.update_feed("Syncing repository to GitHub...")
            success = auto_git_push()
            if self.answer_hud:
                status = "GitHub sync successful ✓" if success else "GitHub sync failed ⚠️"
                self.answer_hud.update_feed(status)

        elif cmd in ("UI_COLOR_CHANGE", "COLOR_CHANGE", "CHANGE_COLOR", "SET_COLOR"):
            color = cmd_args.get("color", "")
            if color:
                color_map = {
                    "red": "#FF3B30", "green": "#34C759", "blue": "#007AFF",
                    "purple": "#AF52DE", "pink": "#FF2D55", "yellow": "#FFCC00",
                    "orange": "#FF9500", "cyan": "#5AC8FA", "teal": "#30B0C7",
                    "indigo": "#5856D6", "gold": "#FFD700", "white": "#FFFFFF",
                    "crimson": "#DC143C", "magenta": "#FF00FF"
                }
                c_str = str(color).strip()
                if c_str.lower() in color_map:
                    c_str = color_map[c_str.lower()]
                qc = QColor(c_str)
                if qc.isValid():
                    self.accent_color = qc.name().upper()
                    self.config["accent_color"] = self.accent_color
                    self.persist_config()
                    self.reload_mascot_pixmap()
                    if self.answer_hud:
                        self.answer_hud.update_feed(f"Accent color changed to {self.accent_color} ✓")

        elif cmd in ("RESIZE_HUD", "HUD_RESIZE"):
            try:
                w = int(cmd_args.get("width", 260))
                h = int(cmd_args.get("height", 210))
                w = max(200, min(w, 400))
                h = max(140, min(h, 450))
                if self.answer_hud:
                    self.answer_hud.resize(w, h)
                self.config["answer_window_width"] = w
                self.config["answer_window_height"] = h
                self.persist_config()
                if self.answer_hud:
                    self.answer_hud.update_feed(f"HUD resized to {w}x{h} ✓")
            except Exception as e:
                print(f"[Brain] Resize HUD error: {e}")

        elif cmd in ("OPEN_SETTINGS", "SETTINGS"):
            self._set_key()

        elif cmd in ("OPEN_BROWSER", "BROWSER"):
            url = cmd_args.get("url", "https://google.com")
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            webbrowser.open(url)
            if self.answer_hud:
                self.answer_hud.update_feed(f"Opened browser: {url} ✓")

        elif cmd in ("OPEN_APP", "LAUNCH_APP"):
            app = cmd_args.get("app") or cmd_args.get("query", "")
            if app:
                if self.worker:
                    ok, detail = self.worker._try_launch_local(app)
                else:
                    ok, detail = False, None
                if not ok:
                    url = SPECIAL_URLS.get(app.lower(), f"https://www.{app.replace(' ', '')}.com")
                    webbrowser.open(url)
                if self.answer_hud:
                    self.answer_hud.update_feed(f"Launched {app} ✓")

        elif cmd in ("PLAY_MEDIA", "PLAY_SONG", "PLAY_MUSIC"):
            query = cmd_args.get("query") or cmd_args.get("song") or cmd_args.get("title", "")
            if query:
                enc = urllib.parse.quote_plus(query)
                webbrowser.open(f"https://www.youtube.com/results?search_query={enc}")
                if self.answer_hud:
                    self.answer_hud.update_feed(f"Playing '{query}' on YouTube 🎵")

        elif cmd in ("CHECK_UPDATES", "UPDATE"):
            self._check_for_updates(interactive=True)

        elif cmd in ("CHANGE_SIZE", "RESIZE_BOT"):
            size = cmd_args.get("size")
            if size:
                try:
                    self.apply_icon_size(int(size))
                    self.persist_config()
                except Exception:
                    pass

        elif cmd in ("QUIT", "EXIT"):
            self._quit()

    # ---- drag vs click + magnetic tracking ----
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.press_global = e.globalPosition().toPoint()
            self.win_start = self.pos()
            self.press_time = time.time()
            self.is_dragging = False
            self.hud_start = (self.answer_hud.pos()
                              if self.answer_hud and self.answer_hud.isVisible()
                              else None)
            self.spotlight_start = (self.spotlight.pos()
                                    if self.spotlight and self.spotlight.isVisible()
                                    else None)
            self.update_dialog_start = (self.update_dialog.pos()
                                        if self.update_dialog and self.update_dialog.isVisible()
                                        else None)
            self.toast_start = (self.uptodate_toast.pos()
                                if self.uptodate_toast and self.uptodate_toast.isVisible()
                                else None)

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() == Qt.MouseButton.LeftButton:
            cur = e.globalPosition().toPoint()
            dx = cur.x() - self.press_global.x()
            dy = cur.y() - self.press_global.y()
            if abs(dx) >= 5 or abs(dy) >= 5:
                self.is_dragging = True
                self.move(self.win_start.x() + dx, self.win_start.y() + dy)
                # MAGNETIC: move answer HUD by exact same delta
                if self.answer_hud and self.answer_hud.isVisible() and self.hud_start:
                    self.answer_hud.move(
                        self.hud_start.x() + dx, self.hud_start.y() + dy)
                # MAGNETIC: move spotlight search box by exact same delta
                if self.spotlight and self.spotlight.isVisible() and self.spotlight_start:
                    self.spotlight.move(
                        self.spotlight_start.x() + dx, self.spotlight_start.y() + dy)
                # MAGNETIC: move update dialog / toast by exact same delta
                if self.update_dialog and self.update_dialog.isVisible() and self.update_dialog_start:
                    self.update_dialog.move(
                        self.update_dialog_start.x() + dx, self.update_dialog_start.y() + dy)
                if self.uptodate_toast and self.uptodate_toast.isVisible() and self.toast_start:
                    self.uptodate_toast.move(
                        self.toast_start.x() + dx, self.toast_start.y() + dy)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            cur = e.globalPosition().toPoint()
            dx = abs(cur.x() - self.press_global.x())
            dy = abs(cur.y() - self.press_global.y())
            dist = (dx*dx + dy*dy) ** 0.5
            hold = time.time() - self.press_time
            was_drag = self.is_dragging or dist >= 5.0 or (hold > 0.4 and dist >= 3.0)
            self.is_dragging = False
            if was_drag:
                self.persist_config()
                self.base_y = self.y()
                return
            self._handle_bot_click()

    def _handle_bot_click(self):
        """Mutually Exclusive UI States & Smart Toggle:
        - If AnswerHUD (response box) is visible, clicking the bot icon closes it.
        - If Search Bar is visible, clicking the bot icon closes it.
        - If neither is visible, clicking the bot icon opens Search Bar.
        """
        hud_active = bool(self.answer_hud and self.answer_hud.isVisible())
        search_active = bool(self.spotlight and self.spotlight.isVisible())

        if hud_active:
            self.answer_hud.close()
            self.answer_hud = None
            return

        if search_active:
            self.spotlight.close()
            self.spotlight = None
            return

        self._open_spotlight()

    # ---- context menu ----
    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(f"""QMenu{{background-color:{COLOR_GLASS_BG};
            color:{COLOR_TEXT_PRIMARY};border:1px solid {COLOR_GLASS_BORDER};
            border-radius:8px;padding:4px;font-family:'{FONT_FAMILY}';font-size:11px;}}
            QMenu::item{{padding:6px 18px;border-radius:4px;}}
            QMenu::item:selected{{background-color:{self.accent_color};color:#09090B;}}
            QMenu::separator{{height:1px;background-color:{COLOR_GLASS_SUBTLE};margin:4px 6px;}}""")
        a1 = m.addAction("💬 Toggle Search Bar")
        m.addSeparator()
        a2 = m.addAction("📏 Adjust Size...")
        a3 = m.addAction("🎨 Change Colour...")

        sm = m.addMenu("🔑 API & Provider Settings")
        sm.setStyleSheet(m.styleSheet())
        a_gemini = sm.addAction("🧠 Gemini Key (The Brain)")
        a_pico = sm.addAction("👂 Picovoice Key (Jarvis Wake Word)")
        a_groq = sm.addAction("🎙️ Groq Key (Whisper Bilingual STT)")
        a_eleven = sm.addAction("🔊 ElevenLabs Key (Voice TTS)")
        a_safety = sm.addAction("🛡️ Perspective Key (Safety Net)")

        v_lbl = "🎙️ Disable Ears Listening" if self.voice_enabled else "🎙️ Enable Ears Listening ('Jarvis')"
        a_voice = m.addAction(v_lbl)
        t_lbl = "🗣️ Disable Voice Responses (TTS)" if self.tts_enabled else "🗣️ Enable Voice Responses (TTS)"
        a_tts = m.addAction(t_lbl)

        a_mem = m.addAction("🧠 Memories (View / Delete)...")

        m.addSeparator()
        a_up = m.addAction("🔄 Check for Updates...")
        m.addSeparator()
        a5 = m.addAction("❌ Exit")
        act = m.exec(e.globalPos())
        if act == a1:         self._handle_bot_click()
        elif act == a2:       self._open_slider()
        elif act == a3:       self._change_color()
        elif act == a_gemini: self._set_key()
        elif act == a_pico:   self._set_picovoice_key()
        elif act == a_groq:   self._set_groq_key()
        elif act == a_eleven: self._set_eleven_key()
        elif act == a_safety: self._set_safety_key()
        elif act == a_voice:  self._toggle_voice()
        elif act == a_tts:    self._toggle_tts()
        elif act == a_mem:    self._open_memory_manager()
        elif act == a_up:     self._check_for_updates(interactive=True)
        elif act == a5:       self._quit()

    # ---- dialogs ----
    def _open_memory_manager(self):
        dlg = MemoryManagerDialog(self, self)
        dlg.exec()
    def _toggle_spotlight(self):
        self._handle_bot_click()

    def _open_spotlight(self):
        if self.answer_hud and self.answer_hud.isVisible():
            self.answer_hud.close()
            self.answer_hud = None
        if self.spotlight:
            self.spotlight.close()
            self.spotlight = None
        self.spotlight = SpotlightDialog(self)
        self.spotlight.show()
        self.spotlight.activateWindow()

    def _open_slider(self):
        if self.size_popup:
            self.size_popup.close()
        self.size_popup = SizeSliderPopup(self)
        self.size_popup.show()
        self.size_popup.activateWindow()

    def _change_color(self):
        initial_color = self.accent_color
        dlg = QColorDialog(QColor(initial_color), self)
        dlg.setWindowTitle("Jarvis Accent Colour")

        def _on_color_changed(c: QColor):
            if c.isValid():
                self.accent_color = c.name().upper()
                self.reload_mascot_pixmap()

        dlg.currentColorChanged.connect(_on_color_changed)
        if dlg.exec():
            selected = dlg.selectedColor()
            if selected.isValid():
                self.accent_color = selected.name().upper()
            self.config["accent_color"] = self.accent_color
            self.persist_config()
            self.reload_mascot_pixmap()
        else:
            self.accent_color = initial_color
            self.reload_mascot_pixmap()

    def _set_key(self, pending: Optional[str] = None):
        k, ok = QInputDialog.getText(self, "Jarvis – Gemini API Key",
                                     "Enter Gemini API Key (The Brain):", text=self._get_key())
        if ok and k.strip():
            self.config["gemini_api_key"] = k.strip()
            self.persist_config()
            self._init_genai()
            if self.brain:
                self.brain.api_key = k.strip()
                self.brain._init_client()
            if pending:
                self.process_prompt(pending)

    def _set_groq_key(self):
        cur = self.config.get("groq_api_key", "")
        k, ok = QInputDialog.getText(self, "Jarvis – Groq API Key",
                                     "Enter Groq API Key (Whisper STT - Tamil & English):", text=cur)
        if ok:
            self.config["groq_api_key"] = k.strip()
            self.persist_config()
            if self.voice_manager:
                self.voice_manager.groq_key = k.strip()

    def _set_eleven_key(self):
        cur = self.config.get("elevenlabs_api_key", "")
        k, ok = QInputDialog.getText(self, "Jarvis – ElevenLabs API Key",
                                     "Enter ElevenLabs API Key (The Voice TTS):", text=cur)
        if ok:
            self.config["elevenlabs_api_key"] = k.strip()
            self.persist_config()
            if self.voice_manager:
                self.voice_manager.eleven_key = k.strip()

    def _set_picovoice_key(self):
        cur = self.config.get("picovoice_access_key", "")
        k, ok = QInputDialog.getText(self, "Jarvis – Picovoice Access Key",
                                     "Enter Picovoice Access Key (for offline Jarvis wake word):", text=cur)
        if ok:
            self.config["picovoice_access_key"] = k.strip()
            self.persist_config()
            if self.voice_enabled:
                self._stop_ears_worker()
                self._start_ears_worker()

    def _set_safety_key(self):
        cur = self.config.get("perspective_api_key", "")
        k, ok = QInputDialog.getText(self, "Jarvis – Perspective API Key",
                                     "Enter Perspective API Key (The Safety Net Guardrail):", text=cur)
        if ok:
            self.config["perspective_api_key"] = k.strip()
            self.persist_config()
            if self.safety_net:
                self.safety_net.api_key = k.strip()

    def _toggle_voice(self):
        self.voice_enabled = not self.voice_enabled
        self.config["voice_enabled"] = self.voice_enabled
        self.persist_config()
        if self.voice_enabled:
            self._start_ears_worker()
            QMessageBox.information(self, "Jarvis Voice", "Continuous Ears listening active!\nSay 'Jarvis' followed by your question in English or Tamil.")
        else:
            self._stop_ears_worker()
            QMessageBox.information(self, "Jarvis Voice", "Voice ears listening disabled.")

    def _toggle_tts(self):
        self.tts_enabled = not self.tts_enabled
        self.config["tts_enabled"] = self.tts_enabled
        self.persist_config()
        state = "enabled" if self.tts_enabled else "disabled"
        QMessageBox.information(self, "Jarvis Voice", f"Voice Text-to-Speech responses {state}.")

    # ---- update system ----
    def _check_for_updates(self, interactive: bool = True):
        if self.update_checker and self.update_checker.isRunning():
            return
        self.update_checker = UpdateCheckWorker(APP_VERSION, interactive=interactive, parent=self)
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.up_to_date.connect(self._on_up_to_date)
        self.update_checker.check_failed.connect(self._on_check_failed)
        self.update_checker.start()

    def _on_update_available(self, release_info: dict, interactive: bool):
        if self.update_dialog:
            self.update_dialog.close()
        self.update_dialog = UpdateDialog(self, release_info)
        self.update_dialog.show()
        self.update_dialog.activateWindow()

    def _on_up_to_date(self, current_ver: str, interactive: bool):
        if interactive:
            if self.uptodate_toast:
                self.uptodate_toast.close()
            self.uptodate_toast = UpToDateToast(self, current_ver)
            self.uptodate_toast.show()

    def _on_check_failed(self, err_msg: str, interactive: bool):
        if interactive:
            QMessageBox.information(
                self, "Jarvis – Updates",
                f"Could not check for updates:\n{err_msg}\n\nCheck your internet connection."
            )

    def _quit(self):
        if hasattr(self, "listening_widget") and self.listening_widget:
            self.listening_widget.close()
        if hasattr(self, "tts_worker") and self.tts_worker:
            self.tts_worker.stop()
        if hasattr(self, "ears_worker") and self.ears_worker:
            self._stop_ears_worker()
        self.persist_config()
        QApplication.quit()


# ============================================================================
# Entry Point
# ============================================================================
RexiBotWindow = JarvisBotWindow
FloatingBot = JarvisBotWindow


def main():
    if "--push" in sys.argv:
        success = auto_git_push()
        sys.exit(0 if success else 1)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bot = JarvisBotWindow()
    bot.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
