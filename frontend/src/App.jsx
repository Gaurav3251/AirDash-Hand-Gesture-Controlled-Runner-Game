import { useEffect, useState, useRef, useCallback } from "react";
import { fetchSessions, fetchSessionSummary, createSession, finalizeSession, deleteSession, clearAllSessions } from "./api.js";
import { Game } from "./gameCanvas.js";
import pyClassifierCode from "./gesture_classifier.py?raw";

// Local temporal majority voting filter to smooth predictions
class StabilityFilter {
  constructor() {
    this.window = [];
    this.lastFiredTime = 0.0;
    this.lastFiredGesture = "none";
  }

  update(gestureLabel, confidence) {
    const now = Date.now() / 1000;
    const val = confidence >= 0.65 ? gestureLabel : "none";
    this.window.push(val);

    if (this.window.length > 6) {
      this.window.shift();
    }

    if (this.window.length < 6) {
      return null;
    }

    const counts = {};
    for (const g of this.window) {
      counts[g] = (counts[g] || 0) + 1;
    }

    let winner = "none";
    let maxVotes = 0;
    for (const g in counts) {
      if (counts[g] > maxVotes) {
        maxVotes = counts[g];
        winner = g;
      }
    }

    if (maxVotes >= 4 && winner !== "none") {
      if (winner === this.lastFiredGesture && now - this.lastFiredTime < 0.6) {
        return null;
      }
      this.lastFiredTime = now;
      this.lastFiredGesture = winner;
      return winner;
    }

    return null;
  }

  reset() {
    this.window = [];
    this.lastFiredTime = 0.0;
    this.lastFiredGesture = "none";
  }
}


const GESTURE_MAP = [
  { gesture: "Move Hand Left", type: "Position", action: "Left Lane", desc: "Hold your hand on the left side of the camera screen to shift lanes.", image: null },
  { gesture: "Move Hand Right", type: "Position", action: "Right Lane", desc: "Hold your hand on the right side of the camera screen to shift lanes.", image: null },
  { gesture: "Peace Sign", type: "Static (Held)", action: "Jump", desc: "Extend index & middle fingers. Clears ground obstacles (cones/potholes).", image: "/peace_sign.jpg" },
  { gesture: "Pinch", type: "Static (Held)", action: "Duck", desc: "Touch thumb and index tips together. Clears overhead obstacles (barriers).", image: "/pinch_gesture.jpg" },
  { gesture: "Thumbs Up", type: "Static (Held)", action: "Pause / Resume", desc: "Extend thumb up, curl others. Toggles pause/resume.", image: "/thumbs_up.jpg" },
  { gesture: "Pointing Up", type: "Static (Held)", action: "Lifeline (+1 Life)", desc: "Point your index finger up, curl others. Adds 1 life (max 3 times per game).", image: "/pointing_up.jpg" },
  { gesture: "Fist", type: "Static (Held)", action: "Stop Run / Restart", desc: "Curl all fingers. Ends the current run immediately.", image: "/closed_fist.jpg" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("landing");
  const [inputMode, setInputMode] = useState("gesture"); // "gesture" or "keyboard"
  
  // Database Sessions State
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(false);

  // Pyodide (Python Wasm) State
  const [pyRuntime, setPyRuntime] = useState(null);
  const [loadingPyodide, setLoadingPyodide] = useState(false);

  // Calibration/Testing State
  const [testGesture, setTestGesture] = useState("none");
  const [testConfidence, setTestConfidence] = useState(0);
  const [testFeedback, setTestFeedback] = useState("Show a gesture in camera to test...");
  
  // Game Play State
  const [gameActive, setGameActive] = useState(false);
  const [gameScore, setGameScore] = useState(0);
  const [gameLives, setGameLives] = useState(3);
  const [gameLifelinesUsed, setGameLifelinesUsed] = useState(0);
  const [gameFps, setGameFps] = useState(0);
  const [gameLatency, setGameLatency] = useState(0);
  const [activeGesture, setActiveGesture] = useState("none");
  const [activeAction, setActiveAction] = useState("none");

  // Ref handles
  const gameCanvasRef = useRef(null);
  const testVideoRef = useRef(null);
  const gameVideoRef = useRef(null);
  
  // Instantiated Objects
  const gameRef = useRef(null);
  const handsRef = useRef(null);
  const cameraRef = useRef(null);

  // Load Pyodide Wasm Runtime on mount
  useEffect(() => {
    async function loadPython() {
      if (window.loadPyodide && !pyRuntime && !loadingPyodide) {
        setLoadingPyodide(true);
        try {
          const pyodide = await window.loadPyodide();
          await pyodide.runPythonAsync(pyClassifierCode);
          setPyRuntime(pyodide);
          console.log("Pyodide Wasm environment initialized locally!");
        } catch (e) {
          console.error("Pyodide initialization failed:", e);
          setError("Failed to initialize client-side Python Wasm environment.");
        } finally {
          setLoadingPyodide(false);
        }
      }
    }
    loadPython();
  }, [pyRuntime, loadingPyodide]);
  const stabilityFilterRef = useRef(new StabilityFilter());

  // Keep track of events during session
  const sessionEventsRef = useRef([]);
  const currentSessionIdRef = useRef(null);

  // Load Session History
  const loadSessionsData = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const data = await fetchSessions();
      setSessions(data);
      if (data.length > 0) {
        // Select latest by default
        const latestId = data[0].id;
        setSelectedId(latestId);
        const summ = await fetchSessionSummary(latestId);
        setSummary(summ);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  const loadSingleSummary = async (id) => {
    try {
      setSelectedId(id);
      const summ = await fetchSessionSummary(id);
      setSummary(summ);
    } catch (e) {
      setError(e.message);
    }
  };

  // Analytics will start empty. Sessions will accumulate as the user plays during the tab session.

  // Clean up MediaPipe
  const stopMediaPipe = () => {
    if (cameraRef.current) {
      cameraRef.current.stop();
      cameraRef.current = null;
    }
    if (handsRef.current) {
      handsRef.current.close();
      handsRef.current = null;
    }
  };

  // Start MediaPipe for Warmup/Test
  const startTestMediaPipe = async () => {
    stopMediaPipe();
    const video = testVideoRef.current;
    if (!video) return;

    if (!window.Hands) {
      setTestFeedback("MediaPipe library failed to load. Check internet connection.");
      return;
    }

    setTestFeedback("Initializing camera & hand tracker...");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      video.srcObject = stream;
      video.play();

      const hands = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
      });

      hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.6,
        minTrackingConfidence: 0.6,
      });

      hands.onResults((results) => {
        const landmarks = results.multiHandLandmarks?.[0];
        
        // Render landmarks on top
        const canvas = document.getElementById("test-overlay");
        if (canvas) {
          const ctx = canvas.getContext("2d");
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          
          if (landmarks) {
            drawHandLandmarks(ctx, landmarks);
            
            let pyLabel = "none";
            let pyConfidence = 0.0;
            let palmCenterX = 0.5;

            if (!pyRuntime) {
              setTestFeedback("Compiling local Python WebAssembly environment...");
              return;
            }

            try {
              const pyClassify = pyRuntime.globals.get("classify_frame");
              const jsonResult = pyClassify(JSON.stringify(landmarks));
              const res = JSON.parse(jsonResult);
              
              pyLabel = res.label;
              pyConfidence = res.confidence;
              palmCenterX = res.palmCenterX;
            } catch (pyErr) {
              console.error("Python frame classification error:", pyErr);
            }

            const mirroredX = 1.0 - palmCenterX;
            let lane = "Middle";
            if (mirroredX < 0.38) lane = "Left";
            else if (mirroredX > 0.62) lane = "Right";

            let actionText = "Running";
            if (pyLabel === "peace_sign") actionText = "Jump 🦘";
            else if (pyLabel === "pinch") actionText = "Duck 🦆";
            else if (pyLabel === "thumbs_up") actionText = "Pause ⏸️";
            else if (pyLabel === "fist") actionText = "Stop ⏹️";
            else if (pyLabel === "pointing_up") actionText = "Lifeline ❤️";

            let feedback = `Position: ${lane} Lane | Gesture Action: ${actionText}`;

            setTestGesture(`${lane} Lane + ${actionText}`);
            setTestConfidence(pyConfidence);
            setTestFeedback(feedback);
          }
        }
      });

      const camera = new window.Camera(video, {
        onFrame: async () => {
          await hands.send({ image: video });
        },
        width: 640,
        height: 480,
      });

      cameraRef.current = camera;
      handsRef.current = hands;
      camera.start();
      setTestFeedback("Webcam active! Try doing different gestures.");
    } catch (err) {
      console.error(err);
      setTestFeedback(`Camera access failed: ${err.message}`);
    }
  };

  // Start Play Session
  const startPlaySession = async () => {
    stopMediaPipe();
    setGameActive(true);
    
    // Create new SQLite session
    try {
      const res = await createSession(inputMode);
      currentSessionIdRef.current = res.session_id;
    } catch (e) {
      console.error("Failed to write session:", e);
      currentSessionIdRef.current = Date.now(); // local fallback
    }

    sessionEventsRef.current = [];
    
    // Instaniate Game
    const game = new Game();
    gameRef.current = game;

    // Connect Canvas
    const canvas = gameCanvasRef.current;
    const ctx = canvas.getContext("2d");
    
    let animationId;
    let lastTime = performance.now();
    let frameCount = 0;
    let fps = 60;
    let latencySamples = [];

    // Keyboard handlers
    const handleKeyDown = (e) => {
      if (inputMode === "keyboard" || !gameActive) {
        let action = "none";
        if (e.key === "ArrowLeft") action = "move_left";
        else if (e.key === "ArrowRight") action = "move_right";
        else if (e.key === "ArrowUp") action = "move_up"; // Map arrow up to jump
        else if (e.key === "ArrowDown") action = "move_down"; // Map arrow down to duck
        else if (e.key === "ArrowUp" || e.key === "w" || e.key === "W") action = "jump";
        else if (e.key === "ArrowDown" || e.key === "s" || e.key === "S") action = "duck";
        else if (e.key.toLowerCase() === "p" || e.key === " ") action = "pause";
        else if (e.key.toLowerCase() === "x" || e.key === "Escape") action = "stop";
        else if (e.key.toLowerCase() === "l") action = "extra_life";

        if (action !== "none") {
          game.applyAction(action);
          
          // Log keyboard event
          sessionEventsRef.current.push({
            timestamp: Date.now() / 1000,
            predicted_gesture: "keyboard",
            confidence: 1.0,
            action_fired: action,
            fps: fps,
            latency_ms: 1.0,
          });
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    // If gesture mode, initialize MediaPipe
    if (inputMode === "gesture") {
      const video = gameVideoRef.current;
      if (video) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } });
          video.srcObject = stream;
          video.play();

          const hands = new window.Hands({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
          });

          hands.setOptions({
            maxNumHands: 1,
            modelComplexity: 1,
            minDetectionConfidence: 0.6,
            minTrackingConfidence: 0.6,
          });

          hands.onResults((results) => {
            const startProcess = performance.now();
            const landmarks = results.multiHandLandmarks?.[0];
            
            // Draw overlay PiP
            const pipCanvas = document.getElementById("game-pip-overlay");
            if (pipCanvas) {
              const pipCtx = pipCanvas.getContext("2d");
              pipCtx.clearRect(0, 0, pipCanvas.width, pipCanvas.height);
              
              // Draw video frame to PiP canvas
              pipCtx.drawImage(video, 0, 0, pipCanvas.width, pipCanvas.height);
              if (landmarks) {
                drawHandLandmarks(pipCtx, landmarks);
              }
            }

            let gestureLabel = "none";
            let confidence = 0.0;
            let action = "none";

            if (landmarks) {
              let pyLabel = "none";
              let pyConfidence = 0.0;
              let palmCenterX = 0.5;

              if (!pyRuntime) {
                return;
              }

              try {
                const pyClassify = pyRuntime.globals.get("classify_frame");
                const jsonResult = pyClassify(JSON.stringify(landmarks));
                const res = JSON.parse(jsonResult);
                
                pyLabel = res.label;
                pyConfidence = res.confidence;
                palmCenterX = res.palmCenterX;
              } catch (pyErr) {
                console.error("Python frame classification error:", pyErr);
              }

              // 1. Mirror the X-coordinate to align visually with the mirrored CSS webcam feed
              const mirroredX = 1.0 - palmCenterX;

              // 2. Position-based Lane Selection
              let targetLane = 1; // Middle
              if (mirroredX < 0.38) {
                targetLane = 0; // Left
              } else if (mirroredX > 0.62) {
                targetLane = 2; // Right
              }
              game.player.lane = targetLane;

              // 3. Temporal Stability Filter on Python-returned label
              const stableStatic = stabilityFilterRef.current.update(pyLabel, pyConfidence);

              let activeActionLabel = "none";
              if (stableStatic === "peace_sign") {
                action = "jump";
                activeActionLabel = "jump";
              } else if (stableStatic === "pinch") {
                action = "duck";
                activeActionLabel = "duck";
              } else if (stableStatic === "thumbs_up") {
                action = "pause";
                activeActionLabel = "pause";
              } else if (stableStatic === "fist") {
                action = "stop";
                activeActionLabel = "stop";
              } else if (stableStatic === "pointing_up") {
                action = "extra_life";
                activeActionLabel = "extra_life";
              }

              if (action !== "none") {
                game.applyAction(action);
              }

              // Diagnostics formatting for overlay & logging
              const laneLabel = targetLane === 0 ? "LEFT" : targetLane === 2 ? "RIGHT" : "MIDDLE";
              const actionLabelStr = activeActionLabel !== "none" ? ` + ${activeActionLabel.toUpperCase()}` : "";
              
              gestureLabel = `${laneLabel}${actionLabelStr}`;
              confidence = pyConfidence;
            }

            const procLatency = performance.now() - startProcess;
            latencySamples.push(procLatency);
            if (latencySamples.length > 30) latencySamples.shift();
            
            const avgLat = latencySamples.reduce((a, b) => a + b, 0) / latencySamples.length;
            setGameLatency(avgLat);
            setActiveGesture(gestureLabel);
            setActiveAction(action);

            // Log event
            sessionEventsRef.current.push({
              timestamp: Date.now() / 1000,
              predicted_gesture: gestureLabel,
              confidence: confidence,
              action_fired: action,
              fps: fps,
              latency_ms: procLatency,
            });
          });

          const camera = new window.Camera(video, {
            onFrame: async () => {
              await hands.send({ image: video });
            },
            width: 320,
            height: 240,
          });

          cameraRef.current = camera;
          handsRef.current = hands;
          camera.start();
        } catch (e) {
          console.error("Camera fail for game:", e);
        }
      }
    }

    // Main Game Rendering Loop (60 FPS requestAnimationFrame)
    const loop = () => {
      if (!gameRef.current || game.gameOver) {
        // End of run
        cancelAnimationFrame(animationId);
        window.removeEventListener("keydown", handleKeyDown);
        stopMediaPipe();
        setGameActive(false);
        finalizeGameSession(game.score, true);
        return;
      }

      const now = performance.now();
      frameCount++;
      if (now - lastTime >= 1000) {
        fps = Math.round((frameCount * 1000) / (now - lastTime));
        setGameFps(fps);
        frameCount = 0;
        lastTime = now;
      }

      game.update();
      game.draw(ctx);

      // Update state for hooks
      setGameScore(game.score);
      setGameLives(game.lives);
      setGameLifelinesUsed(game.lifelinesUsed);

      animationId = requestAnimationFrame(loop);
    };

    loop();
  };

  // Submit Final Metrics to SQLite & Update Local React State
  const finalizeGameSession = async (finalScore, completed) => {
    const sessionId = currentSessionIdRef.current;
    if (!sessionId) return;

    try {
      // 1. Log to SQLite database
      await finalizeSession(sessionId, completed, finalScore, sessionEventsRef.current);
      
      // 2. Fetch the compiled summary for this specific session
      const newSummary = await fetchSessionSummary(sessionId);

      // 3. Update the local sessions list in React state
      const newSessionRecord = {
        id: sessionId,
        input_mode: inputMode,
        final_score: finalScore,
        completed: completed,
      };

      setSessions((prev) => [newSessionRecord, ...prev]);
      setSummary(newSummary);
      setSelectedId(sessionId);

      setActiveTab("analytics");
    } catch (e) {
      console.error("Error writing final session:", e);
      setError("Failed to export game session details to backend.");
    }
  };



  // Render hand helper
  const drawHandLandmarks = (ctx, landmarks) => {
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4],
      [0, 5], [5, 6], [6, 7], [7, 8],
      [5, 9], [9, 10], [10, 11], [11, 12],
      [9, 13], [13, 14], [14, 15], [15, 16],
      [13, 17], [17, 18], [18, 19], [19, 20],
      [0, 17]
    ];

    // Draw Skeleton Lines
    ctx.strokeStyle = "#00f5d4";
    ctx.lineWidth = 3;
    connections.forEach(([start, end]) => {
      const p1 = landmarks[start];
      const p2 = landmarks[end];
      if (p1 && p2) {
        ctx.beginPath();
        ctx.moveTo(p1.x * ctx.canvas.width, p1.y * ctx.canvas.height);
        ctx.lineTo(p2.x * ctx.canvas.width, p2.y * ctx.canvas.height);
        ctx.stroke();
      }
    });

    // Draw Joints
    ctx.fillStyle = "#ff007f";
    landmarks.forEach((p) => {
      ctx.beginPath();
      ctx.arc(p.x * ctx.canvas.width, p.y * ctx.canvas.height, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  };

  const handleTabChange = (tab) => {
    stopMediaPipe();
    setActiveTab(tab);
    if (tab === "instructions" && inputMode === "gesture") {
      setTimeout(startTestMediaPipe, 200);
    }
  };

  return (
    <div className="app-container">
      {/* Background Image Overlay */}
      <div className="bg-image-overlay" />

      {/* Navigation Header */}
      <header className="navbar">
        <div className="logo" onClick={() => handleTabChange("landing")}>
          AIR<span>DASH</span>
        </div>
        <nav>
          <button 
            className={`nav-link ${activeTab === "landing" ? "active" : ""}`} 
            onClick={() => handleTabChange("landing")}
          >
            Home
          </button>
          <button 
            className={`nav-link ${activeTab === "instructions" ? "active" : ""}`} 
            onClick={() => handleTabChange("instructions")}
          >
            Instructions
          </button>
          <button 
            className={`nav-link ${activeTab === "play" ? "active" : ""}`} 
            onClick={() => handleTabChange("play")}
          >
            Play Game
          </button>
          <button 
            className={`nav-link ${activeTab === "analytics" ? "active" : ""}`} 
            onClick={() => handleTabChange("analytics")}
          >
            Analytics Dashboard
          </button>
        </nav>
      </header>

      {/* Python Wasm Loading Banner */}
      {loadingPyodide && (
        <div className="pyodide-loader-bar">
          <span className="spinner-dot"></span>
          <span>Compiling local Python WebAssembly classifier...</span>
        </div>
      )}


      {/* Error message */}
      {error && (
        <div className="error-toast">
          <span>Connection Error: {error}. Backend is required to log metrics.</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="content-area">
        {activeTab === "landing" && (
          <section className="tab-pane fade-in landing-hero">
            <h1 className="hero-title">
              AIR<span>DASH</span>
            </h1>
            <p className="hero-tagline">
              A high-speed, immersive, hand-gesture controlled runner game. Dodge obstacles, collect stars, and challenge your reflexes directly in the browser!
            </p>
            <div className="hero-actions">
              <button className="btn btn-primary" onClick={() => handleTabChange("instructions")}>
                Get Started
              </button>
              <button className="btn btn-secondary" onClick={() => handleTabChange("analytics")}>
                View Dashboard
              </button>
            </div>
            
            <div className="feature-grid">
              <div className="feature-card">
                <h3>Zero Latency</h3>
                <p>MediaPipe hand landmark extraction runs locally in your browser. Moves trigger in under 10ms.</p>
              </div>
              <div className="feature-card">
                <h3>Advanced Gesture Map</h3>
                <p>Custom gesture logic checks thumb-to-knuckle distance to perfectly separate Fists from Thumbs Up.</p>
              </div>
              <div className="feature-card">
                <h3>Real-Time Analytics</h3>
                <p>Track your prediction accuracy, false trigger rate, frame rates, and latency details post-session.</p>
              </div>
            </div>
          </section>
        )}

        {activeTab === "instructions" && (
          <section className="tab-pane fade-in instructions-pane">
            <h2 className="section-title">Gesture Setup & Warmup</h2>
            
            <div className="input-selector">
              <span>Control Input Mode:</span>
              <button 
                className={`btn btn-toggle ${inputMode === "gesture" ? "active" : ""}`}
                onClick={() => { setInputMode("gesture"); setTimeout(startTestMediaPipe, 200); }}
              >
                🎥 Webcam Gestures
              </button>
              <button 
                className={`btn btn-toggle ${inputMode === "keyboard" ? "active" : ""}`}
                onClick={() => { setInputMode("keyboard"); stopMediaPipe(); }}
              >
                ⌨️ Keyboard (Fallback)
              </button>
            </div>

            <div className="instructions-grid">
              {/* Left Column: Rules */}
              <div className="rules-column">
                <h3>Gesture Control Map</h3>
                <table className="gesture-table">
                  <thead>
                    <tr>
                      <th>Gesture Poses</th>
                      <th>Action</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {GESTURE_MAP.map((g) => (
                      <tr key={g.gesture}>
                        <td className="g-cell">
                          <div>
                            <strong>{g.gesture}</strong> <span className="type-badge">{g.type}</span>
                          </div>
                          {g.image && (
                            <div className="gesture-img-container">
                              <img src={g.image} alt={g.gesture} className="gesture-guide-img" />
                            </div>
                          )}
                        </td>
                        <td className="action-cell">{g.action}</td>
                        <td className="muted">{g.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="note-card">
                  <h4>💡 Gameplay Pro-Tips:</h4>
                  <ul>
                    <li><strong>No more pause conflicts:</strong> Swipe/slide gestures are tracked by movement path. The game only pauses/resumes when you hold a static <strong>Peace Sign</strong> (V-pose).</li>
                    <li><strong>Avoid diagonal motion:</strong> Keep your swipes strictly horizontal or vertical to avoid drifting off-axis.</li>
                    <li><strong>Lifeline limits:</strong> Thumbs Up adds a life, but you can only use a maximum of 3 lifelines per game session.</li>
                  </ul>
                </div>
              </div>

              {/* Right Column: Webcam Test */}
              <div className="webcam-column">
                <h3>Interactive Gesture Check</h3>
                {inputMode === "gesture" ? (
                  <div className="calibrator-box">
                    <div className="video-wrapper">
                      <video ref={testVideoRef} className="webcam-feed" playsInline muted width="640" height="480"></video>
                      <canvas id="test-overlay" className="webcam-overlay" width="640" height="480"></canvas>
                    </div>
                    
                    <div className={`calib-status-card ${testGesture !== "none" ? "detected-flash" : ""}`}>
                      <div className="muted font-small">Current detected gesture:</div>
                      <div className="gesture-text">
                        {testGesture === "none" ? "None" : testGesture.replace("_", " ").toUpperCase()}
                      </div>
                      <p className="calib-feedback">{testFeedback}</p>
                    </div>
                    <button className="btn btn-primary" onClick={() => handleTabChange("play")} style={{ width: "100%", marginTop: 12 }}>
                      Looks Good, Start Playing!
                    </button>
                  </div>
                ) : (
                  <div className="keyboard-instructions">
                    <div className="keyboard-visual">
                      <div className="key">▲</div>
                      <div className="key-row">
                        <div className="key">◀</div>
                        <div className="key">▼</div>
                        <div className="key">▶</div>
                      </div>
                    </div>
                    <div className="key-map">
                      <p><strong>Left / Right Arrow</strong>: Lane Shift</p>
                      <p><strong>Up Arrow / W</strong>: Jump over ground obstacles</p>
                      <p><strong>Down Arrow / S</strong>: Duck under overhead obstacles</p>
                      <p><strong>Space / P</strong>: Pause / Resume</p>
                      <p><strong>Escape / X</strong>: Stop current run</p>
                      <p><strong>L key</strong>: Extra Life (cap of 3)</p>
                    </div>
                    <button className="btn btn-primary" onClick={() => handleTabChange("play")} style={{ width: "100%", marginTop: 24 }}>
                      Start Playing!
                    </button>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {activeTab === "play" && (
          <section className="tab-pane fade-in play-pane">
            <div className="play-grid">
              {/* Left Side: Game Canvas */}
              <div className="canvas-wrapper">
                <canvas 
                  ref={gameCanvasRef} 
                  className="game-canvas" 
                  width="800" 
                  height="600"
                ></canvas>

                {!gameActive && (
                  <div className="game-start-overlay">
                    <h2>Ready to Dash?</h2>
                    <p className="muted">Playing in <strong>{inputMode.toUpperCase()}</strong> input mode.</p>
                    <button className="btn btn-primary btn-lg" onClick={startPlaySession}>
                      Start Run
                    </button>
                  </div>
                )}
              </div>

              {/* Right Side: Webcam PiP and Live Stats */}
              <div className="control-sidebar">
                <div className="sidebar-card">
                  <h3>Input Details</h3>
                  <div className="input-toggle-row">
                    <button 
                      className={`btn btn-toggle ${inputMode === "gesture" ? "active" : ""}`}
                      onClick={() => setInputMode("gesture")}
                      disabled={gameActive}
                    >
                      Webcam
                    </button>
                    <button 
                      className={`btn btn-toggle ${inputMode === "keyboard" ? "active" : ""}`}
                      onClick={() => setInputMode("keyboard")}
                      disabled={gameActive}
                    >
                      Keyboard
                    </button>
                  </div>
                </div>

                {inputMode === "gesture" && (
                  <div className="sidebar-card pip-card">
                    <h3>Webcam Monitor</h3>
                    <div className="pip-video-wrapper">
                      <video ref={gameVideoRef} style={{ display: "none" }} playsInline muted width="320" height="240"></video>
                      <canvas id="game-pip-overlay" className="pip-overlay-canvas" width="320" height="240"></canvas>
                      {!gameActive && <div className="pip-placeholder">Video starts with run...</div>}
                    </div>
                  </div>
                )}

                <div className="sidebar-card stats-card">
                  <h3>Session Diagnostics</h3>
                  <div className="diag-row">
                    <span>Active Gesture:</span>
                    <strong className="gesture-val">{activeGesture.replace("_", " ").toUpperCase()}</strong>
                  </div>
                  <div className="diag-row">
                    <span>Action Dispatched:</span>
                    <strong className="action-val">{activeAction.replace("_", " ").toUpperCase()}</strong>
                  </div>
                  <div className="diag-row">
                    <span>Average Frame Rate:</span>
                    <span>{gameFps} FPS</span>
                  </div>
                  <div className="diag-row">
                    <span>Recognition Latency:</span>
                    <span className={gameLatency > 100 ? "text-danger" : "text-success"}>
                      {gameLatency.toFixed(1)} ms
                    </span>
                  </div>
                  <div className="diag-row">
                    <span>Lifelines Used:</span>
                    <span>{gameLifelinesUsed}/3</span>
                  </div>
                </div>

                <div className="sidebar-card help-card">
                  <h3>Key Bindings</h3>
                  <p className="muted font-small">
                    Use <strong>Arrow Keys</strong> or <strong>W/A/S/D</strong> if in keyboard mode. Pause with <strong>P / Space</strong>. Stop with <strong>Escape / X</strong>.
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === "analytics" && (
          <section className="tab-pane fade-in analytics-pane">
            <h2 className="section-title">Player Performance Analytics</h2>

            {loadingSessions ? (
              <div className="muted">Loading analytics data...</div>
            ) : sessions.length === 0 ? (
              <div className="no-data-card">
                <h3>No sessions logged yet!</h3>
                <p className="muted">Play a game session first to populate the analytics dashboard.</p>
                <button className="btn btn-primary" onClick={() => handleTabChange("play")}>Play Game</button>
              </div>
            ) : (
              <div className="analytics-grid">
                {/* Left Column: Recent Sessions List */}
                <div className="history-column">
                  <h3>Session History</h3>
                  <div className="table-wrapper">
                    <table className="sessions-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Mode</th>
                          <th>Score</th>
                          <th>Status</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sessions.map((s) => (
                          <tr key={s.id} className={s.id === selectedId ? "selected" : ""}>
                            <td>#{s.id}</td>
                            <td><span className="mode-badge">{s.input_mode}</span></td>
                            <td className="score-text">{s.final_score}</td>
                            <td className={s.completed ? "status-success" : "status-fail"}>
                              {s.completed ? "Completed" : "Quit"}
                            </td>
                            <td>
                              <button className="btn btn-sm" onClick={() => loadSingleSummary(s.id)}>View</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Right Column: Detailed Metrics & Charts */}
                <div className="details-column">
                  {summary ? (
                    <>
                      <h3>Session Summary Details (#{summary.session_id})</h3>
                      <div className="metrics-cards-grid">
                        <div className="stat-card">
                          <span className="card-label">Final Score</span>
                          <strong className="card-value">{summary.final_score}</strong>
                        </div>
                        <div className="stat-card">
                          <span className="card-label">Stable prediction rate</span>
                          <strong className={`card-value ${summary.meets_accuracy_target ? "text-success" : "text-warning"}`}>
                            {(summary.stable_prediction_rate * 100).toFixed(1)}%
                          </strong>
                        </div>
                        <div className="stat-card">
                          <span className="card-label">False Triggers / min</span>
                          <strong className={`card-value ${summary.meets_false_trigger_target ? "text-success" : "text-danger"}`}>
                            {summary.false_trigger_rate_per_min.toFixed(2)}
                          </strong>
                        </div>
                        <div className="stat-card">
                          <span className="card-label">Average Latency</span>
                          <strong className={`card-value ${summary.meets_latency_target ? "text-success" : "text-danger"}`}>
                            {summary.avg_latency_ms.toFixed(0)} ms
                          </strong>
                        </div>
                        <div className="stat-card">
                          <span className="card-label">Average FPS</span>
                          <strong className={`card-value ${summary.meets_fps_target ? "text-success" : "text-danger"}`}>
                            {summary.avg_fps.toFixed(1)}
                          </strong>
                        </div>
                        <div className="stat-card">
                          <span className="card-label">Duration</span>
                          <strong className="card-value">{summary.duration_seconds.toFixed(0)}s</strong>
                        </div>
                      </div>

                      {/* SVG Chart: Historical Scores */}
                      <div className="chart-card">
                        <h3>Score History (Last 8 Sessions)</h3>
                        <div className="chart-container">
                          <ScoreHistoryChart sessions={sessions} selectedId={selectedId} />
                        </div>
                      </div>
                      
                      {/* SVG Chart: Latency/FPS comparison */}
                      <div className="chart-card">
                        <h3>Frame Quality Metric Summary</h3>
                        <div className="chart-container">
                          <QualityChart summary={summary} />
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="muted">Select a session from the list to view detailed analytics.</div>
                  )}
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

// Simple Inline SVG Score History Chart
function ScoreHistoryChart({ sessions, selectedId }) {
  const displaySessions = [...sessions].reverse().slice(-8); // older first, limit to 8
  if (displaySessions.length === 0) return null;

  const scores = displaySessions.map(s => s.final_score);
  const maxScore = Math.max(...scores, 100);
  
  const width = 500;
  const height = 150;
  const paddingX = 40;
  const paddingY = 20;
  
  const points = displaySessions.map((s, index) => {
    const x = paddingX + (index * (width - paddingX * 2)) / (displaySessions.length - 1 || 1);
    const y = height - paddingY - (s.final_score / maxScore) * (height - paddingY * 2);
    return { x, y, score: s.final_score, id: s.id };
  });

  const polylinePoints = points.map(p => `${p.x},${p.y}`).join(" ");

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="svg-chart">
      {/* Grid Lines */}
      <line x1={paddingX} y1={paddingY} x2={width - paddingX} y2={paddingY} stroke="rgba(255,255,255,0.05)" />
      <line x1={paddingX} y1={height / 2} x2={width - paddingX} y2={height / 2} stroke="rgba(255,255,255,0.05)" />
      <line x1={paddingX} y1={height - paddingY} x2={width - paddingX} y2={height - paddingY} stroke="rgba(255,255,255,0.1)" strokeWidth="2" />
      
      {/* Chart Line */}
      {points.length > 1 && (
        <polyline
          fill="none"
          stroke="url(#chart-gradient)"
          strokeWidth="3"
          points={polylinePoints}
        />
      )}
      
      {/* Dots and Labels */}
      {points.map((p, i) => (
        <g key={p.id}>
          <circle
            cx={p.x}
            cy={p.y}
            r={p.id === selectedId ? 6 : 4}
            fill={p.id === selectedId ? "#00f5d4" : "#2e86de"}
            stroke="#121218"
            strokeWidth="2"
          />
          <text
            x={p.x}
            y={p.y - 8}
            fill="#ffffff"
            fontSize="10"
            textAnchor="middle"
            fontWeight={p.id === selectedId ? "bold" : "normal"}
          >
            {p.score}
          </text>
          <text
            x={p.x}
            y={height - 4}
            fill="#aaaaaa"
            fontSize="9"
            textAnchor="middle"
          >
            #{p.id}
          </text>
        </g>
      ))}

      <defs>
        <linearGradient id="chart-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#2e86de" />
          <stop offset="100%" stopColor="#00f5d4" />
        </linearGradient>
      </defs>
    </svg>
  );
}

// Simple Inline SVG Chart for Latency and FPS targets
function QualityChart({ summary }) {
  const width = 500;
  const height = 150;
  
  // Latency bar: target max 200ms
  const latPercent = Math.min((summary.avg_latency_ms / 250) * 100, 100);
  // FPS bar: target min 20fps
  const fpsPercent = Math.min((summary.avg_fps / 60) * 100, 100);

  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="svg-chart">
      {/* Latency Bar */}
      <text x="20" y="32" fill="#e0e0e0" fontSize="12" fontWeight="bold">Latency (Average: {summary.avg_latency_ms.toFixed(1)}ms)</text>
      <rect x="20" y="44" width="360" height="14" rx="4" fill="rgba(255,255,255,0.06)" />
      <rect x="20" y="44" width={(360 * latPercent) / 100} height="14" rx="4" fill={summary.meets_latency_target ? "#00f5d4" : "#ff4d4d"} />
      <line x1="20 + 360 * 0.8" y1="40" x2="20 + 360 * 0.8" y2="62" stroke="rgba(255,255,255,0.3)" strokeDasharray="3,3" /> {/* target marker */}
      <text x="390" y="55" fill="#aaaaaa" fontSize="11">Target &lt; 200ms</text>

      {/* FPS Bar */}
      <text x="20" y="96" fill="#e0e0e0" fontSize="12" fontWeight="bold">Frame Rate (Average: {summary.avg_fps.toFixed(1)} FPS)</text>
      <rect x="20" y="108" width="360" height="14" rx="4" fill="rgba(255,255,255,0.06)" />
      <rect x="20" y="108" width={(360 * fpsPercent) / 100} height="14" rx="4" fill={summary.meets_fps_target ? "#2e86de" : "#f1c40f"} />
      <text x="390" y="119" fill="#aaaaaa" fontSize="11">Target &gt; 20 FPS</text>
    </svg>
  );
}
