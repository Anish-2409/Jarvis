#!/usr/bin/env python3
"""
================================================================================
 Rexi - Persistent Desktop AI Companion (PyQt6 Edition)
================================================================================
 Setup & Dependencies:
   pip install PyQt6 google-genai pillow

 Features:
   1. Interactive 3D Mascot:
      - Uses rex.png without bottom-crop (ground-free).
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
import json
import time
import shutil
import tempfile
import warnings
import subprocess
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
    print(f"[Rexi Unhandled Exception]:\n{err_str}", file=sys.stderr)
    try:
        log_file = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)), "rexi_error.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n{err_str}\n")
    except Exception:
        pass

sys.excepthook = _global_exception_handler

# ---------------------------------------------------------------------------
# PyQt6 Core, GUI, and Widgets
# ---------------------------------------------------------------------------
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint, QPointF, QSize, QRectF, QSettings, QEvent
)
from PyQt6.QtGui import (
    QPixmap, QImage, QColor, QFont, QFontMetrics, QCursor, QIcon,
    QMouseEvent, QKeyEvent, QTextCursor, QAction
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextBrowser,
    QVBoxLayout, QHBoxLayout, QPushButton, QMenu, QColorDialog,
    QInputDialog, QMessageBox, QFrame, QSlider, QProgressBar,
    QGraphicsDropShadowEffect, QSizeGrip, QSystemTrayIcon
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


# ============================================================================
# Automated Git Operations
# ============================================================================
def auto_git_push(repo_dir: Optional[str] = None, commit_message: Optional[str] = None) -> bool:
    """Automates git add ., git commit -m 'Rexi auto-update: <timestamp>', and git push.

    Captures stdout/stderr and prints them to the console to verify status.
    """
    if repo_dir is None:
        repo_dir = get_app_dir()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = commit_message or f"Rexi auto-update: {now_str}"

    print(f"\n=======================================================")
    print(f"  Rexi Automated Git Push ({now_str})")
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
GITHUB_REPO = "Anish-2409/rexi"

CONFIG_FILE = os.path.join(get_app_dir(), "bot_config.json")

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
# Config (stateless – no history)
# ============================================================================
def load_config() -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "bot_x": None, "bot_y": None,
        "icon_size": 70,
        "accent_color": DEFAULT_ACCENT,
        "answer_window_width": 320,
        "answer_window_height": 220,
        "gemini_api_key": "",
        "preferred_model": "gemini-3.1-flash-lite",
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
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
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass


# ============================================================================
# Image Processing & Dynamic Tinting
# ============================================================================
_BASE_PIL_IMAGE: Optional[Image.Image] = None
_BASE_PIL_ALPHA: Optional[Image.Image] = None


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qi = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qi)


def get_base_rex_image() -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Loads and caches the clean foreground-isolated rex.png character (ground-free).
    Returns (base_rgba_image, clean_alpha_mask).
    """
    global _BASE_PIL_IMAGE, _BASE_PIL_ALPHA
    if _BASE_PIL_IMAGE is not None and _BASE_PIL_ALPHA is not None:
        return _BASE_PIL_IMAGE, _BASE_PIL_ALPHA

    if not PIL_AVAILABLE:
        return None, None

    for name in ("rex.png", "rex_icon.png", "trex_icon.png"):
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
        print(f"[Rexi] Image load error: {exc}")
        return None, None


def load_master_rex_pixmap(accent_color: str = DEFAULT_ACCENT) -> Optional[QPixmap]:
    """
    Loads rex.png ground-free and programmatically tints the character with accent_color.
    ImageOps.colorize maps midtones to the chosen color while preserving specular
    highlights and 3D shadows.
    """
    base_img, alpha = get_base_rex_image()
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
        print(f"[Rexi] Error tinting rex.png: {exc}")
        return pil_to_qpixmap(base_img)


def load_search_icon(size: int = 22,
                     accent: str = DEFAULT_ACCENT) -> Optional[QPixmap]:
    if not PIL_AVAILABLE:
        return None
    for name in ("trex_icon.png", "rex.png"):
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
# Action Worker Thread (3-step verification + stateless streaming)
# ============================================================================
class RexiActionWorker(QThread):
    status_signal    = pyqtSignal(str)
    chunk_received   = pyqtSignal(str)
    finished_stream  = pyqtSignal(str)
    action_finished  = pyqtSignal(str)
    error_occurred   = pyqtSignal(str)

    def __init__(self, client, model: str, prompt: str, parent=None):
        super().__init__(parent)
        self.client = client
        self.model  = model
        self.prompt = prompt

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
        self.status_signal.emit("Analyzing intent...")

        clean = self.prompt.strip()
        lower = clean.lower()

        # === ACTION A: play [song] ===
        if lower.startswith("play "):
            song = clean[5:].strip()
            if song:
                enc = urllib.parse.quote_plus(song)
                url = f"https://www.youtube.com/results?search_query={enc}"
                self.status_signal.emit(f"Opening YouTube for '{song}'...")
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                self.status_signal.emit("Media playback started ✓")
                self.action_finished.emit(f"Playing {song} on YouTube! 🎵")
                return

        # === ACTION B: open [app] — 3-step verified ===
        if lower.startswith("open "):
            app = clean[5:].strip()
            if app:
                self.status_signal.emit(f"Launching '{app}'...")
                ok, detail = self._try_launch_local(app)
                if ok:
                    self.status_signal.emit(f"Local launch verified: {detail}")
                    self.action_finished.emit(f"Launched {app} on your PC! 💻")
                else:
                    self.status_signal.emit("Local app not found – opening browser...")
                    url = SPECIAL_URLS.get(app.lower())
                    if not url:
                        url = f"https://www.{app.replace(' ', '')}.com"
                    try:
                        webbrowser.open(url)
                    except Exception:
                        pass
                    self.status_signal.emit(f"Opened {url} ✓")
                    self.action_finished.emit(
                        f"Local app not found.\nOpened {url} in your browser! 🌐")
                return

        # === ACTION C: stateless ultra-fast Gemini streaming ===
        if not self.client:
            self.error_occurred.emit("Gemini client not initialised. Set API key.")
            self.status_signal.emit("API error ⚠️")
            return

        candidate_models = [self.model, "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
        models_to_try = []
        for m in candidate_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        last_err = ""
        for m in models_to_try:
            try:
                self.status_signal.emit(f"Connecting to {m}...")
                stream = self.client.models.generate_content_stream(
                    model=m,
                    contents=clean,
                    config=types.GenerateContentConfig(
                        system_instruction=(
                            "You are Rexi, a friendly, concise, and smart desktop companion. "
                            "Keep your answers short, direct, and conversational."
                        ),
                        max_output_tokens=300,
                    ),
                )
                first = True
                chunks: List[str] = []
                for ch in stream:
                    if ch and ch.text:
                        if first:
                            self.status_signal.emit("Streaming response...")
                            first = False
                        chunks.append(ch.text)
                        self.chunk_received.emit(ch.text)
                self.status_signal.emit("Response complete ✓")
                self.finished_stream.emit("".join(chunks))
                return
            except Exception as exc:
                last_err = str(exc)
                continue

        self.status_signal.emit("Gemini error ⚠️")
        self.error_occurred.emit(last_err)


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
        self.entry.setPlaceholderText("Ask Rexi, or type 'open [app]' / 'play [song]'...")
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
class AnswerHUD(QWidget):
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
        self.setMinimumSize(220, 160)
        self.setMaximumWidth(350)

        # Restore user's preferred compact size from QSettings (or bot.config fallback)
        settings = QSettings("RexiBot", "Rexi")
        saved_w = settings.value(
            "hud_width",
            self.bot.config.get("answer_window_width", 280),
            type=int
        )
        saved_h = settings.value(
            "hud_height",
            self.bot.config.get("answer_window_height", 220),
            type=int
        )
        w = max(220, min(saved_w, 350))
        h = max(160, min(saved_h, 450))
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
        il.setContentsMargins(10, 8, 10, 8)
        il.setSpacing(5)

        # Header
        hdr = QFrame(self.container)
        hdr.setStyleSheet("background:transparent;border:none;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(2, 0, 2, 0)
        self.title_lbl = QLabel(f"● Rexi • {self.bot.active_model}", hdr)
        self.title_lbl.setStyleSheet(f"color:{accent};font-family:'{FONT_FAMILY}';"
                                     f"font-size:10px;font-weight:bold;border:none;")
        hl.addWidget(self.title_lbl); hl.addStretch()
        cb = QPushButton("×", hdr)
        cb.setFixedSize(16, 16)
        cb.setStyleSheet(f"QPushButton{{background:transparent;color:{COLOR_TEXT_MUTED};"
                         f"font-size:14px;border:none;}}QPushButton:hover{{color:#FFF;}}")
        cb.clicked.connect(self.close)
        hl.addWidget(cb)
        il.addWidget(hdr)

        # Prompt
        short = self.prompt if len(self.prompt) <= 55 else self.prompt[:52] + "..."
        pl = QLabel(f"You: {short}", self.container)
        pl.setStyleSheet(f"color:{COLOR_TEXT_MUTED};font-family:'{FONT_FAMILY}';"
                         f"font-size:9px;font-style:italic;border:none;background:transparent;")
        il.addWidget(pl)

        # Response
        self.response = QTextBrowser(self.container)
        self.response.setPlainText("Rexi is thinking… 💭")
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
        for txt, slot in [("Send", self._followup), ("Copy", self._copy)]:
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

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.width() >= 200 and self.height() >= 140:
            self.bot.config["answer_window_width"] = self.width()
            self.bot.config["answer_window_height"] = self.height()
            save_config(self.bot.config)
            settings = QSettings("RexiBot", "Rexi")
            settings.setValue("hud_width", self.width())
            settings.setValue("hud_height", self.height())

    def closeEvent(self, e):
        if self.width() >= 200 and self.height() >= 140:
            self.bot.config["answer_window_width"] = self.width()
            self.bot.config["answer_window_height"] = self.height()
            save_config(self.bot.config)
            settings = QSettings("RexiBot", "Rexi")
            settings.setValue("hud_width", self.width())
            settings.setValue("hud_height", self.height())
        e.accept()

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
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        headers = {
            "User-Agent": "Rexi-Desktop-Companion",
            "Accept": "application/vnd.github.v3+json",
        }
        data = None
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

        if not data or not isinstance(data, dict) or "tag_name" not in data:
            try:
                cmd = [
                    "curl.exe", "-s",
                    "-H", "User-Agent: Rexi-Desktop-Companion",
                    "-H", "Accept: application/vnd.github.v3+json",
                    url
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if proc.returncode == 0 and proc.stdout.strip():
                    parsed = json.loads(proc.stdout)
                    if isinstance(parsed, dict) and "tag_name" in parsed:
                        data = parsed
            except Exception:
                pass

        # Fallback to web redirect inspection (rate-limit immune)
        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            fallback_tag = self._get_tag_via_redirect()
            if fallback_tag:
                data = {
                    "tag_name": fallback_tag,
                    "html_url": f"https://github.com/{GITHUB_REPO}/releases/tag/{fallback_tag}",
                    "body": "A new version of Rexi is available.",
                    "assets": [
                        {
                            "name": "Rexi.exe",
                            "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{fallback_tag}/Rexi.exe",
                        },
                        {
                            "name": "Rexi-macOS.zip",
                            "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/{fallback_tag}/Rexi-macOS.zip",
                        }
                    ]
                }

        if not data or not isinstance(data, dict) or not data.get("tag_name"):
            self.check_failed.emit("Could not reach update server. Check internet connection.", self.interactive)
            return

        latest_tag = data.get("tag_name", "")
        if is_newer_version(latest_tag, self.current_ver):
            self.update_available.emit(data, self.interactive)
        else:
            self.up_to_date.emit(self.current_ver, self.interactive)

    def _get_tag_via_redirect(self) -> Optional[str]:
        target = f"https://github.com/{GITHUB_REPO}/releases/latest"
        try:
            cmd = ["curl.exe", "-s", "-I", target]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            for line in p.stdout.splitlines():
                if line.lower().startswith("location:"):
                    loc = line.split(":", 1)[1].strip()
                    tag = loc.rstrip("/").split("/")[-1]
                    if tag and tag != "releases":
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
                target_file = os.path.join(tempfile.gettempdir(), f"Rexi_update_{int(time.time())}.exe")
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
                target_file = os.path.join(tempfile.gettempdir(), f"Rexi_update_{int(time.time())}.zip")
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
            self.progress.emit(0, 0, "Downloading latest rexi.pyw...")
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/rexi.pyw"
            target_file = os.path.join(tempfile.gettempdir(), f"rexi_update_{int(time.time())}.pyw")
            self._download_file(raw_url, target_file)
            self.download_complete.emit(target_file, "py")

        except Exception as exc:
            self.download_failed.emit(str(exc))

    def _download_file(self, url: str, dest_path: str):
        headers = {"User-Agent": "Rexi-Desktop-Companion"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
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
        cmd = ["curl.exe", "-L", "-s", "-H", "User-Agent: Rexi-Desktop-Companion", "-o", dest_path, url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
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
        t_lbl = QLabel("● Rexi Update Available", frame)
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
            body = "A new update for Rexi is ready with new features and bug fixes."
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
                batch_file = os.path.join(tempfile.gettempdir(), f"rexi_update_{pid}.bat")
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
                self.status_lbl.setText("Updated via git ✓ Restarting Rexi...")
                QTimer.singleShot(800, self._restart_script)
                return

            elif mode == "py":
                curr_script = os.path.abspath(__file__)
                shutil.move(path, curr_script)
                self.status_lbl.setText("Script updated ✓ Restarting Rexi...")
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
                    cp -R "{tempfile.gettempdir()}/Rexi.app" "{app_path}"
                    open "{app_path}"
                    """
                    subprocess.Popen(["/bin/bash", "-c", script])
                    self.bot.persist_config()
                    QApplication.quit()
                    return

            self.status_lbl.setText("Update applied! Please restart Rexi.")
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

        txt = QLabel(f"Rexi is up to date (v{current_ver})", frame)
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
class RexiBotWindow(QWidget):
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
        self.answer_hud: Optional[AnswerHUD] = None
        self.size_popup: Optional[SizeSliderPopup] = None
        self.worker: Optional[RexiActionWorker] = None
        self.update_checker: Optional[UpdateCheckWorker] = None
        self.update_dialog: Optional[UpdateDialog] = None
        self.uptodate_toast: Optional[UpToDateToast] = None

        # Stateless GenAI
        self.genai_client = None
        self.active_model = "gemini-3.1-flash-lite"
        self._init_genai()

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

        # Anti-vanish screen watchdog (keeps Rexi visible, recovers from display/sleep shifts)
        self._watchdog_t = QTimer(self)
        self._watchdog_t.setInterval(4000)
        self._watchdog_t.timeout.connect(self._ensure_on_screen)
        self._watchdog_t.start()

        # System Tray Icon (anchors Rexi to the Windows/macOS notification area)
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
        save_config(self.config)

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
        icon_path = get_asset_path("rex.png")
        if not os.path.exists(icon_path):
            icon_path = get_asset_path("trex_icon.png")
        tray_icon = QIcon(icon_path) if os.path.exists(icon_path) else self.windowIcon()

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip(f"Rexi – Desktop Companion (v{APP_VERSION})")

        m = QMenu()
        m.setStyleSheet(f"""QMenu{{background-color:{COLOR_GLASS_BG};
            color:{COLOR_TEXT_PRIMARY};border:1px solid {COLOR_GLASS_BORDER};
            border-radius:8px;padding:4px;font-family:'{FONT_FAMILY}';font-size:11px;}}
            QMenu::item{{padding:6px 18px;border-radius:4px;}}
            QMenu::item:selected{{background-color:{self.accent_color};color:#09090B;}}
            QMenu::separator{{height:1px;background-color:{COLOR_GLASS_SUBTLE};margin:4px 6px;}}""")

        act_show = m.addAction("🦖 Show / Bring Rexi to Front")
        act_show.triggered.connect(self._restore_and_raise)

        act_spot = m.addAction("💬 Toggle Search Bar")
        act_spot.triggered.connect(self._toggle_spotlight)

        act_reset = m.addAction("📍 Reset Screen Position")
        act_reset.triggered.connect(self._reset_position)

        m.addSeparator()
        act_up = m.addAction("🔄 Check for Updates...")
        act_up.triggered.connect(lambda: self._check_for_updates(interactive=True))

        act_key = m.addAction("🔑 Set API Key")
        act_key.triggered.connect(self._set_key)

        m.addSeparator()
        act_exit = m.addAction("❌ Exit Rexi")
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
            print(f"[Rexi] GenAI ready (stateless: {self.active_model})")
        except Exception as e:
            print(f"[Rexi] GenAI init error: {e}")

    # ---- dispatch prompt ----
    def process_prompt(self, prompt: str):
        if not prompt.strip():
            return
        if self.answer_hud:
            self.answer_hud.close()
        self.answer_hud = AnswerHUD(self, prompt)
        self.answer_hud.show()

        if not self.genai_client:
            self._init_genai()

        self.worker = RexiActionWorker(
            self.genai_client, self.active_model, prompt, parent=self)
        self.worker.status_signal.connect(self.answer_hud.update_feed)
        self.worker.chunk_received.connect(self.answer_hud.append_chunk)
        self.worker.finished_stream.connect(self.answer_hud.finish_stream)
        self.worker.action_finished.connect(self.answer_hud.finish_action)
        self.worker.error_occurred.connect(self.answer_hud.display_error)
        self.worker.start()

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
            self._toggle_spotlight()

    # ---- context menu ----
    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(f"""QMenu{{background-color:{COLOR_GLASS_BG};
            color:{COLOR_TEXT_PRIMARY};border:1px solid {COLOR_GLASS_BORDER};
            border-radius:8px;padding:4px;font-family:'{FONT_FAMILY}';font-size:11px;}}
            QMenu::item{{padding:6px 18px;border-radius:4px;}}
            QMenu::item:selected{{background-color:{self.accent_color};color:#09090B;}}
            QMenu::separator{{height:1px;background-color:{COLOR_GLASS_SUBTLE};margin:4px 6px;}}""")
        a1 = m.addAction("💬 What's up? (Spotlight)")
        m.addSeparator()
        a2 = m.addAction("📏 Adjust Size...")
        a3 = m.addAction("🎨 Change Colour...")
        a4 = m.addAction("🔑 Set API Key")
        a_up = m.addAction("🔄 Check for Updates...")
        m.addSeparator()
        a5 = m.addAction("❌ Exit")
        act = m.exec(e.globalPos())
        if act == a1:   self._toggle_spotlight()
        elif act == a2: self._open_slider()
        elif act == a3: self._change_color()
        elif act == a4: self._set_key()
        elif act == a_up: self._check_for_updates(interactive=True)
        elif act == a5: self._quit()

    # ---- dialogs ----
    def _toggle_spotlight(self):
        if self.spotlight and self.spotlight.isVisible():
            self.spotlight.close()
            self.spotlight = None
        else:
            self._open_spotlight()

    def _open_spotlight(self):
        if self.spotlight:
            self.spotlight.close()
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
        dlg.setWindowTitle("Rexi Accent Colour")

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
        k, ok = QInputDialog.getText(self, "Rexi – API Key",
                                     "Enter Gemini API Key:", text=self._get_key())
        if ok and k.strip():
            self.config["gemini_api_key"] = k.strip()
            self.persist_config()
            self._init_genai()
            if pending:
                self.process_prompt(pending)

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
                self, "Rexi – Updates",
                f"Could not check for updates:\n{err_msg}\n\nCheck your internet connection."
            )

    def _quit(self):
        self.persist_config()
        QApplication.quit()


# ============================================================================
# Entry Point
# ============================================================================
def main():
    if "--push" in sys.argv:
        success = auto_git_push()
        sys.exit(0 if success else 1)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bot = RexiBotWindow()
    bot.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
