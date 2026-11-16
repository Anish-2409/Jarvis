# Rexi — Persistent Desktop AI Companion (PyQt6 Edition) 🦖

Rexi is a lightweight, borderless, floating desktop AI companion built with **Python**, **PyQt6**, **Pillow**, and Google's **`google-genai`** SDK targeting **`gemini-2.5-flash`**.

---

## 🚀 Setup & Installation

```bash
pip install PyQt6 google-genai pillow
```

*(Python 3.12: `py -3.12 -m pip install PyQt6 google-genai pillow`)*

---

## ✨ Features

### 1. 🎨 Dynamic Mascot Color Tinting
- Ground-free 3D character loaded from `rex.png` with crisp alpha edge thresholding.
- Right-click ➔ **Change Colour...** immediately recolors the bot's icon in real time using `ImageOps.colorize` to shade midtones with the chosen accent color while preserving 3D specular highlights and shadows.
- Scaled via `Qt.TransformationMode.SmoothTransformation` for smooth, anti-aliased edges at any size.

### 2. 📏 Real-Time Dynamic Size Slider
- Right-click ➔ **Adjust Size...** opens a custom borderless popup widget with a horizontal `QSlider` (50px to 200px).
- Connected directly to `apply_icon_size` for smooth 60fps real-time scaling.

### 3. 🧲 Magnetic Response Box
- Compact default dimensions (**320 × 220**).
- Magnetic lock: when dragging Rexi across your desktop, the response box moves in lockstep by tracking the exact same `(dx, dy)` movement delta.
- Frosted glass aesthetic: `rgba(20, 20, 30, 210)` background with subtle glass border and 12px rounded corners.

### 4. 🔍 3-Step Verified App Launcher
- 3-step verification pipeline:
  1. **Search**: Known paths (`%LOCALAPPDATA%`, `%PROGRAMFILES%`), Start Menu `.lnk` shortcuts, system `PATH`, and `AppOpener`.
  2. **Launch & Verify**: `os.startfile()` or `AppOpener.open(throw_error=True)`.
  3. **Fallback**: If not found locally, declares `"Local app not found"` in the UI and opens the web application fallback in your default browser.

### 5. ⚡ Stateless AI
- Pure stateless requests to Google's official `google-genai` SDK (`gemini-2.5-flash`) without chat history overhead.

### 6. 📡 Live Status Feed
- Sleek italic label at the bottom of the HUD streaming backend states in real-time (`"User input received..."` ➔ `"Analyzing intent..."` ➔ `"Streaming response..."`).

### 7. 🎯 Core Interactions
- **Drag vs. Click**: Stationary clicks (< 5px) open Spotlight; drags move Rexi and save coordinates to `bot_config.json`.
- **Anchor-Based Bounce**: 4px vertical bounce every 600ms, paused during drag and re-anchored on release.
- **Context Menu**: Spotlight, Adjust Size, Change Colour, Set API Key, Exit.

---

## 🎮 How to Run

```powershell
py -3.12 rexi.pyw
```

- **Silent launch:** Double-click [`run_rex.bat`](run_rex.bat)
- **Standalone `.exe`:** Run [`build_exe.bat`](build_exe.bat) ➔ `dist\Rexi.exe`
