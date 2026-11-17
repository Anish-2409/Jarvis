# Jarvis — Desktop AI Companion (PyQt6 Edition) ✦

[![Download for Windows](https://img.shields.io/badge/Download_for_Windows-Jarvis.exe-00A896?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Anish-2409/Jarvis/releases/download/v1.1.0/Jarvis.exe)
[![Download for macOS](https://img.shields.io/badge/Download_for_macOS-Jarvis--macOS.zip-00F0FF?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/Anish-2409/Jarvis/releases/download/v1.1.0/Jarvis-macOS.zip)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Gemini 3.1 Flash Lite](https://img.shields.io/badge/Model-Gemini_3.1_Flash_Lite-orange?style=for-the-badge)](https://ai.google.dev/)
[![Groq Whisper](https://img.shields.io/badge/STT-Groq_Whisper_v3-red?style=for-the-badge)](https://groq.com/)
[![Edge TTS](https://img.shields.io/badge/Voice-British_Jarvis-purple?style=for-the-badge)](https://github.com/rany2/edge-tts)

**Jarvis** is a lightweight, ultra-minimal, floating desktop AI companion and assistant built with **Python 3.12**, **PyQt6**, **Edge-TTS**, **Groq Whisper**, and Google's official **`google-genai`** SDK.

---

## 📥 Download Standalone (No Python Needed!)

If you want to run Jarvis without installing Python or running terminal commands:

- 🪟 **Windows Users**: Download [**`Jarvis.exe`**](https://github.com/Anish-2409/Jarvis/releases/download/v1.1.0/Jarvis.exe) ➔ Double-click to run!
- 🍎 **macOS Users**: Download [**`Jarvis-macOS.zip`**](https://github.com/Anish-2409/Jarvis/releases/download/v1.1.0/Jarvis-macOS.zip) ➔ Unzip and double-click `Jarvis.app`!

*After launching, right-click the mascot ➔ **🔑 API & Provider Settings** ➔ **Set Gemini Key** (free key available from [Google AI Studio](https://aistudio.google.com/)).*

---

## 🚀 Run from Source (Python)

```bash
# 1. Clone the repository
git clone https://github.com/Anish-2409/Jarvis.git
cd Jarvis

# 2. Install dependencies
pip install PyQt6 google-genai pillow edge-tts pygame sounddevice pvporcupine speechrecognition

# 3. Launch Jarvis
python jarvis.pyw
```

- **Quick Launch:** Double-click [`run_jarvis.bat`](run_jarvis.bat)
- **Build Portable Executable:** Run [`build_exe.bat`](build_exe.bat) ➔ `dist\Jarvis.exe`

---

## ✨ Features & Capabilities

### 1. 🎙️ Continuous "Jarvis" Wake Word & Voice Ears
- **Snappy Activation**: Powered by Picovoice Porcupine configured with the built-in keyword `'jarvis'` at `0.65` sensitivity.
- **Microphone Integration**: Queries and detects default input devices using `sounddevice` with automatic 16kHz audio resampling for headsets and AirPods.
- **Wake-Word State Loop**: If you say *"Jarvis"* alone with no follow-up command, Jarvis immediately responds with *"Listening, Sir."* and stays ready—preventing empty queries.
- **Multilingual Transcription**: Follow-up speech is transcribed using Groq Whisper API (`whisper-large-v3`), seamlessly supporting English, Tamil, and Tanglish.

### 2. 🗣️ Pipelined Gapless British Speech (Edge-TTS)
- Uses authentic British AI voice (`en-GB-ThomasNeural`).
- **Asynchronous Producer-Consumer Pipeline**: An internal synthesis worker eagerly pre-fetches and generates upcoming sentence audio bytes while current audio is playing via `pygame.mixer`, eliminating dead-air pauses between streamed sentences.

### 3. 🧠 The Brain & Stateful Memory Core
- Powered by Google Gemini (`gemini-3.1-flash-lite`).
- **Loyal Persona**: Jarvis strictly addresses the user as *"Sir"* with formal efficiency.
- **Long-Term Memory Core**: Stores facts, user details, and preferences locally in `jarvis_config.json`.
- Right-click mascot ➔ **🧠 Memories (View / Delete)...** to manage stored memories.

### 4. 🪟 Ultra-Minimal Compact HUD & Starburst Listening Indicator
- **No Dead Space**: Tight layout margins hug conversation dialogue directly, with an integrated hover-active close button.
- **Smart Toggle**: Clicking the mascot toggles between Spotlight Search, Answer HUD, or hides them cleanly.
- **Sleek Listening HUD**: A glowing floating pill featuring the starburst avatar and `"Listening, Sir..."` typography appears whenever ears are active.

### 5. 🎨 Real-Time Mascot Dynamic Tinting & Slider
- **Dynamic Accent Color**: Right-click ➔ **Change Colour...** recolors Jarvis in real time while preserving 3D specular highlights.
- **Real-Time Size Slider**: Adjust mascot size from 50px to 200px at 60fps.
- **Anti-Vanish Screen Watchdog**: Periodically verifies desktop coordinates to prevent the assistant from drifting off-screen.

---

## ⚙️ Configuration & Secrets

Settings and API keys are stored locally in `jarvis_config.json`:

```json
{
  "bot_x": 1200,
  "bot_y": 700,
  "icon_size": 70,
  "accent_color": "#00A896",
  "gemini_api_key": "YOUR_GEMINI_KEY",
  "groq_api_key": "YOUR_GROQ_KEY",
  "picovoice_access_key": "YOUR_PICOVOICE_KEY",
  "elevenlabs_api_key": "",
  "voice_enabled": true,
  "tts_enabled": true,
  "preferred_model": "gemini-3.1-flash-lite"
}
```

---

## 📜 License
Distributed under the MIT License.
