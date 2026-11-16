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
import warnings
import subprocess
import urllib.parse
import webbrowser
from typing import Optional, List, Dict, Any, Tuple

# ---------------------------------------------------------------------------
# PyQt6 Core, GUI, and Widgets
# ---------------------------------------------------------------------------
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint, QPointF, QSize, QRectF
)
from PyQt6.QtGui import (
    QPixmap, QImage, QColor, QFont, QFontMetrics, QCursor, QIcon,
    QMouseEvent, QKeyEvent, QTextCursor, QAction
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTextBrowser,
    QVBoxLayout, QHBoxLayout, QPushButton, QMenu, QColorDialog,
    QInputDialog, QMessageBox, QFrame, QSlider,
    QGraphicsDropShadowEffect
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
# Constants & Defaults
# ============================================================================
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
        "preferred_model": "gemini-2.5-flash",
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
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
        self.status_signal.emit("User input received...")
        time.sleep(0.06)
        self.status_signal.emit("Analyzing intent...")
        time.sleep(0.06)

        clean = self.prompt.strip()
        lower = clean.lower()

        # === ACTION A: play [song] ===
        if lower.startswith("play "):
            song = clean[5:].strip()
            if song:
                self.status_signal.emit(f"Routing media: '{song}'...")
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
                self.status_signal.emit(f"3-Step Verify: '{app}'...")
                time.sleep(0.06)

                ok, detail = self._try_launch_local(app)

                if ok:
                    self.status_signal.emit(f"Local launch verified: {detail}")
                    self.action_finished.emit(f"Launched {app} on your PC! 💻")
                else:
                    self.status_signal.emit(f"Local app not found – routing to browser...")
                    time.sleep(0.08)
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

        # === ACTION C: stateless Gemini 2.5 Flash streaming ===
        self.status_signal.emit("Querying Gemini 2.5 Flash...")
        time.sleep(0.06)

        if not self.client:
            self.error_occurred.emit("Gemini client not initialised. Set API key.")
            self.status_signal.emit("API error ⚠️")
            return

        chunks: List[str] = []
        try:
            self.status_signal.emit("Connecting...")
            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=clean,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are Rexi, a friendly, concise, and smart desktop companion."
                    )
                ),
            )
            first = True
            for ch in stream:
                if ch and ch.text:
                    if first:
                        self.status_signal.emit("Streaming response...")
                        first = False
                    chunks.append(ch.text)
                    self.chunk_received.emit(ch.text)
            self.status_signal.emit("Response complete ✓")
            self.finished_stream.emit("".join(chunks))

        except Exception as exc:
            err = str(exc)
            if ("404" in err or "NOT_FOUND" in err) and self.model != "gemini-3.5-flash":
                try:
                    self.status_signal.emit("Falling back to gemini-3.5-flash...")
                    fb = self.client.models.generate_content_stream(
                        model="gemini-3.5-flash", contents=clean,
                        config=types.GenerateContentConfig(
                            system_instruction="You are Rexi, a friendly, concise desktop companion."
                        ),
                    )
                    chunks = []
                    first = True
                    for ch in fb:
                        if ch and ch.text:
                            if first:
                                self.status_signal.emit("Streaming response...")
                                first = False
                            chunks.append(ch.text)
                            self.chunk_received.emit(ch.text)
                    self.status_signal.emit("Response complete ✓")
                    self.finished_stream.emit("".join(chunks))
                    return
                except Exception as fb_e:
                    err = str(fb_e)
            self.status_signal.emit("Gemini error ⚠️")
            self.error_occurred.emit(err)


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
        x = bp.x() + (self.bot.width() - self.width()) // 2
        y = bp.y() + self.bot.height() + 8
        x = max(10, min(x, scr.width() - self.width() - 10))
        y = max(10, min(y, scr.height() - self.height() - 10))
        self.move(x, y)

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
            self.bot.process_prompt(t)

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
        w = min(int(bot.config.get("answer_window_width", 320)), 380)
        h = min(int(bot.config.get("answer_window_height", 220)), 280)
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
        il.addWidget(bb)
        lay.addWidget(self.container)

    def _place(self):
        scr = QApplication.primaryScreen().geometry()
        bp = self.bot.pos()
        x = bp.x() + self.bot.width() + 10 if bp.x() + 340 <= scr.width() else bp.x() - self.width() - 10
        y = max(30, min(bp.y() - 20, scr.height() - self.height() - 40))
        self.move(max(10, min(x, scr.width() - self.width() - 10)), y)

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

    def closeEvent(self, e):
        if self.width() > 120 and self.height() > 100:
            self.bot.config["answer_window_width"] = self.width()
            self.bot.config["answer_window_height"] = self.height()
            save_config(self.bot.config)
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
        self.press_time = 0.0
        self.is_dragging = False

        # Active dialogs
        self.spotlight: Optional[SpotlightDialog] = None
        self.answer_hud: Optional[AnswerHUD] = None
        self.size_popup: Optional[SizeSliderPopup] = None
        self.worker: Optional[RexiActionWorker] = None

        # Stateless GenAI
        self.genai_client = None
        self.active_model = "gemini-2.5-flash"
        self._init_genai()

        # Frameless, translucent desktop widget (cross-platform)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        if sys.platform == "win32":
            flags |= Qt.WindowType.SubWindow
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
            self.active_model = self.config.get("preferred_model", "gemini-2.5-flash")
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
        a1 = m.addAction("💬 What's up? (Spotlight)")
        m.addSeparator()
        a2 = m.addAction("📏 Adjust Size...")
        a3 = m.addAction("🎨 Change Colour...")
        a4 = m.addAction("🔑 Set API Key")
        m.addSeparator()
        a5 = m.addAction("❌ Exit")
        act = m.exec(e.globalPos())
        if act == a1:   self._open_spotlight()
        elif act == a2: self._open_slider()
        elif act == a3: self._change_color()
        elif act == a4: self._set_key()
        elif act == a5: self._quit()

    # ---- dialogs ----
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

    def _quit(self):
        self.persist_config()
        QApplication.quit()


# ============================================================================
# Entry Point
# ============================================================================
def main():
    app = QApplication(sys.argv)
    bot = RexiBotWindow()
    bot.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
