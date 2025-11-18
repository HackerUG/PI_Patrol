#web_server.py
#!/usr/bin/env python3
"""
Pi-Patrol Web Server (final low-latency + stable)
Provides responsive MJPEG live stream, enroll API, and face event broadcast.
"""

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
from datetime import datetime
from pathlib import Path
import threading
import time
import cv2
import os

# ========================
# Configuration
# ========================
BASE_DIR = Path("/home/pi/Security/pi_patrol")
FACES_DIR = BASE_DIR / "faces"
LIVE_PATH = BASE_DIR / "events/live.jpg"

app = Flask(_name_)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ========================
# Globals
# ========================
camera_lock = threading.Lock()
current_frame = None
encoded_jpeg = None
current_label = "Unknown"
live_preview_enabled = False
last_frame_time = 0
stream_thread_running = False
stream_fps = 15  # 10 FPS target

# ========================
# Frame Handling
# ========================
def set_frame(frame, label="Unknown"):
    """Update current frame and encoded JPEG buffer."""
    global current_frame, encoded_jpeg, current_label, last_frame_time
    with camera_lock:
        current_frame = frame
        current_label = label
        ret, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ret:
            encoded_jpeg = buf.tobytes()
            last_frame_time = time.time()
            cv2.imwrite(str(LIVE_PATH), frame)


def generate_stream():
    """Fast MJPEG generator (non-blocking, low-latency)."""
    global encoded_jpeg
    last_sent_time = 0
    frame_interval = 1 / stream_fps

    while True:
        if not live_preview_enabled:
            time.sleep(0.2)
            continue

        now = time.time()
        if now - last_sent_time < frame_interval:
            time.sleep(0.01)
            continue

        with camera_lock:
            frame = encoded_jpeg

        if frame:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            last_sent_time = now
        else:
            time.sleep(0.05)


def emit_face_event(event_data):
    """Emit recognition/motion events to dashboard."""
    try:
        socketio.emit("face_event", event_data)
    except Exception as e:
        print(f"[WARN] emit_face_event failed: {e}")


# ========================
# API Routes
# ========================

@app.route("/live")
def live_feed():
    """Serve MJPEG stream for live preview."""
    global stream_thread_running
    if not stream_thread_running:
        stream_thread_running = True
        print("[INFO] Live stream started.")
    return Response(generate_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/enroll", methods=["POST"])
def enroll_face():
    """Save a captured frame as known face under /faces/."""
    name = request.form.get("name")
    if not name:
        return jsonify({"error": "Missing name"}), 400

    FACES_DIR.mkdir(parents=True, exist_ok=True)
    with camera_lock:
        frame_to_save = current_frame.copy() if current_frame is not None else None

    if frame_to_save is None and LIVE_PATH.exists():
        frame_to_save = cv2.imread(str(LIVE_PATH))

    if frame_to_save is None:
        return jsonify({"error": "No live frame available"}), 500

    filename = f"{name}{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    face_path = FACES_DIR / filename

    success = cv2.imwrite(str(face_path), frame_to_save)
    if not success:
        return jsonify({"error": "cv2.imwrite failed"}), 500

    print(f"[INFO] ✅ Enrolled new face: {filename}")
    return jsonify({"success": True, "filename": filename})


@app.route("/api/toggle_preview", methods=["POST"])
def toggle_preview():
    """Enable or disable live preview mode."""
    global live_preview_enabled
    data = request.get_json(force=True)
    live_preview_enabled = bool(data.get("enable", False))
    state = "ON" if live_preview_enabled else "OFF"
    print(f"[INFO] Live preview toggled {state}")
    return jsonify({"live_preview": live_preview_enabled})


@app.route("/api/status")
def status():
    """Return recognition label + system status."""
    return jsonify({
        "current_label": current_label,
        "live_preview": live_preview_enabled,
        "last_frame_time": last_frame_time
    })


@app.route("/media/live.jpg")
def live_jpg():
    """Provide the latest saved frame for dashboard snapshot."""
    if LIVE_PATH.exists():
        return send_from_directory(LIVE_PATH.parent, LIVE_PATH.name)
    return "No live frame", 404


# ========================
# Launcher
# ========================

def launch_in_background():
    """Start the Flask-SocketIO web server in background thread."""
    threading.Thread(
        target=lambda: socketio.run(app, host="0.0.0.0", port=5050, debug=False, use_reloader=False),
        daemon=True,
    ).start()
    print("[INFO] Flask-SocketIO server running at http://0.0.0.0:5050")


if _name_ == "_main_":
    launch_in_background()
    socketio.run(app, host="0.0.0.0", port=5050)
