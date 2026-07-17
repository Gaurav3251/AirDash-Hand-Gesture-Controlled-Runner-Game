# AirDash — Hand Gesture Runner with React & WebAssembly Dashboard

A webcam-based hand-gesture-controlled runner game built with a **dual engine** (HTML5 Canvas in-browser + native Pygame on desktop) and a local **Python WebAssembly (Pyodide)** gesture classification pipeline. 

It includes real-time session metric tracking, local SQLite persistence, and an analytics dashboard with interactive charts.

---

## Project Structure

```text
AirDash/
├── backend/
│   └── api.py                  # FastAPI REST API exposing database session logs
├── frontend/                   # React + Vite dashboard & in-browser Canvas game
│   ├── index.html
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx             # Main React SPA
│   │   ├── index.css           # Cyberpunk dark style definitions
│   │   ├── api.js              # Fetch wrappers for backend REST API
│   │   ├── gameCanvas.js       # HTML5 Canvas 60 FPS Game Engine
│   │   └── gesture_classifier.py # Python script compiled by Pyodide (Wasm)
│   └── public/                 # Hand gesture illustrations & static assets
│       ├── peace_sign.jpg
│       ├── pinch_gesture.jpg
│       ├── thumbs_up.jpg
│       ├── pointing_up.jpg
│       └── closed_fist.jpg
├── scripts/
│   └── db_admin.py             # CLI Database administrator for terminal DB management
├── src/                        # Core backend database & logger package
│   ├── __init__.py
│   ├── config.py               # Tunable database and dev settings
│   ├── session_logger.py       # SQLite logger for sessions and frame events
│   └── evaluation_service.py   # Performance analytics compiler
├── tests/                      # Automated pytest folder for gesture classifier
│   └── test_classifier.py
├── requirements.txt            # Python backend dependencies
└── .gitignore                  # Configured git ignore file
```

---

## 1. Prerequisites

Make sure you have the following installed on your VS Code system:
- **Python 3.10 or 3.11** (recommended for MediaPipe compatibility on desktop)
- **Node.js** (v18 or higher recommended for the Vite frontend)

---

## 2. VS Code Setup & Run Guide

Follow these steps to set up the project on your machine:

### Step 1: Install Python Dependencies
Open your VS Code terminal and install the required Python packages:
```bash
# 1. Create a virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate      # On Windows (Command Prompt)
# OR: .\venv\Scripts\Activate.ps1 (On Windows PowerShell)

# 2. Install packages
pip install -r requirements.txt
```

### Step 2: Install Frontend NodeJS Dependencies
Open a second terminal window or `cd` into the frontend directory:
```bash
cd frontend
npm install
```

---

## 3. Running the Project

To run the complete system, you need to launch the **FastAPI Backend** and the **Vite React Frontend** concurrently. 

### A. Run Backend API Server
In your first terminal (in the root directory):
```bash
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```
This boots up the API on `http://127.0.0.1:8000` to handle game session logging and evaluations.

### B. Run React Web Application
In your second terminal (inside the `frontend` folder):
```bash
npm run dev
```
Open **[http://localhost:5173/](http://localhost:5173/)** in your web browser.

---

## 4. In-Browser Python WebAssembly Gesture Pipeline

When you load the Web Application on your browser:
1. **Pyodide Initialization**: The browser loads **Pyodide** (Python compiled to WebAssembly) and compiles [gesture_classifier.py](frontend/public/gesture_classifier.py) locally on your CPU.
2. **MediaPipe Tracking**: The browser webcam captures frames, extracts 21 coordinates via MediaPipe JS CDN, and feeds them directly into the compiled Python classifier in **under 1ms**.
3. **Zero Network Latency**: No video frames or coordinate arrays are uploaded over the internet during gameplay. The gesture checking is 100% local, responsive, and works offline.

---

## 5. Hand Gestures Vocabulary & Gameplay controls

| Hand Gesture | Control action | Gameplay resolution | Visual Guide |
| :--- | :--- | :--- | :--- |
| **Move Hand Left/Right** | Shift lanes | Avoid obstacles | (Position based) |
| **Peace Sign** (V-shape) | Jump | Clears ground potholes & cones | `peace_sign.jpg` |
| **Pinch** (OK Sign) | Duck | Passes under suspended construction gates | `pinch_gesture.jpg` |
| **Thumbs Up** | Pause / Resume | Freezes the run state | `thumbs_up.jpg` |
| **Pointing Up** (Index) | Lifeline (+1 Life) | Revives runner at Game Over (Max 3/session) | `pointing_up.jpg` |
| **Closed Fist** | Stop Run | Exits run immediately | `closed_fist.jpg` |

*Note: The warning text tags have been removed from the game obstacles. Look for the hanging yellow/black construction archway gate to know when to duck.*

---

## 6. Admin Terminal Database Management

To manage session records directly from your VS Code terminal, use the provided `db_admin.py` utility by enterning `scripts/` folder:

* **List all logged sessions**:
  ```bash
  python db_admin.py --list
  ```
* **Delete a specific session by ID** (e.g. ID #12):
  ```bash
  python db_admin.py --delete 12
  ```
* **Delete all session history logs**:
  ```bash
  python db_admin.py --clear
  ```
