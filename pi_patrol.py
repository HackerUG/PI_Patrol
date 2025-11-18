#pi_patrol.py
#!/usr/bin/env python3
"""
Pi-Patrol Smart Security System (Optimized)
- PIR-triggered camera wake/sleep
- CLAHE-enhanced LBPH-based face recognition (no dlib)
- Auto-preprocessing, confidence threshold, and face resizing
- Saves snapshots and clips for unknowns
- Logs events to patrol.db (dashboard compatible)
- Writes live.jpg for web preview
"""

import os
import time
import sqlite3
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
import threading
from picamera2 import Picamera2
from web_server import set_frame, launch_in_background

# GPIO handling
try:
    import RPi.GPIO as GPIO
except ImportError:
    print("⚠ Warning: RPi.GPIO not available — running in simulation mode.")
    GPIO = None


# ========== CONFIGURATION ==========
class Config:
    BASE_DIR = Path("/home/pi/Security/pi_patrol")
    DB_PATH = BASE_DIR / "patrol.db"
    EVENTS_DIR = BASE_DIR / "events"
    RECORDINGS_DIR = BASE_DIR / "recordings"
    FACES_DIR = BASE_DIR / "faces"
    PIR_PIN = 17
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    VIDEO_DURATION = 5  # seconds
    FACE_SIZE = (200, 200)
    CONFIDENCE_THRESHOLD = 70  # lower = stricter
    IDLE_TIMEOUT = 10  # seconds of no motion before sleeping camera


# ========== DATABASE ==========
def init_database():
    Config.BASE_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(Config.DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            file_path TEXT,
            person_name TEXT
        )
        """)
        conn.commit()


# ========== FACE RECOGNIZER ==========
class LBPHRecognizer:
    def _init_(self, faces_dir: Path):
        self.faces_dir = Path(faces_dir)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        # Tuned LBPH parameters
        self.recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=2,
            neighbors=8,
            grid_x=8,
            grid_y=8,
            threshold=80
        )

        self.labels = {}
        self.model_path = self.faces_dir / "model.yml"

        # Load if trained before
        if self.model_path.exists():
            self.recognizer.read(str(self.model_path))
            print("[INFO] Loaded existing LBPH model.")
            self._load_labels()
        else:
            self.train()

    def _load_labels(self):
        """Rebuild labels from folder names"""
        self.labels = {i: folder.name for i, folder in enumerate(self.faces_dir.iterdir()) if folder.is_dir()}

    def preprocess_face(self, img):
        """Apply grayscale, CLAHE, and resize"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        return cv2.resize(gray, Config.FACE_SIZE)

    def train(self):
        """Train LBPH recognizer from /faces directory"""
        print("[INFO] Training LBPH recognizer...")
        if not self.faces_dir.exists():
            self.faces_dir.mkdir(parents=True, exist_ok=True)

        faces, labels = [], []
        label_id = 0
        self.labels = {}

        for person_folder in self.faces_dir.iterdir():
            if not person_folder.is_dir():
                continue
            person_name = person_folder.name
            self.labels[label_id] = person_name

            for img_path in person_folder.glob("*.jpg"):
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                face = self.preprocess_face(img)
                faces.append(face)
                labels.append(label_id)
            label_id += 1

        if faces:
            self.recognizer.train(faces, np.array(labels))
            self.recognizer.save(str(self.model_path))
            print(f"[INFO] Trained on {len(faces)} face images ({len(self.labels)} persons)")
        else:
            print("[WARN] No faces found — running in unknown-only mode")

    def recognize_faces(self, frame):
        """Detect and recognize faces in a frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=4, minSize=(80, 80)
        )

        results = []
        for (x, y, w, h) in faces:
            roi = gray[y:y+h, x:x+w]
            roi = cv2.resize(roi, Config.FACE_SIZE)
            try:
                label_id, conf = self.recognizer.predict(roi)
                if conf < Config.CONFIDENCE_THRESHOLD:
                    name = self.labels.get(label_id, "Unknown")
                else:
                    name = "Unknown"
            except Exception:
                name, conf = "Unknown", 100.0

            results.append((name, conf, (x, y, w, h)))
        return results


# ========== MAIN SYSTEM ==========
class PiPatrol:
    def _init_(self, config=Config):
        self.config = config
        self.camera = None
        self.last_motion_time = 0
        self.recognizer = LBPHRecognizer(config.FACES_DIR)

        init_database()
        self.setup_gpio()
        self.initialize_camera()

    def setup_gpio(self):
        """Setup GPIO for PIR sensor"""
        if not GPIO:
            print("[WARN] GPIO not available. Running in simulation mode.")
            return
        GPIO.setmode(GPIO.BCM)
        try:
            GPIO.setup(self.config.PIR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        except Exception:
            GPIO.setup(self.config.PIR_PIN, GPIO.IN)
        print(f"[INFO] PIR sensor configured on GPIO {self.config.PIR_PIN}")

    def initialize_camera(self):
        """Initialize camera when motion detected"""
        try:
            self.camera = Picamera2()
            cfg = self.camera.create_preview_configuration(
                main={"size": (self.config.CAMERA_WIDTH, self.config.CAMERA_HEIGHT), "format": "RGB888"}
            )
            self.camera.configure(cfg)
            self.camera.start()
            self.camera.set_controls({"ExposureTime": 15000, "AnalogueGain": 2.0})
            print("[INFO] Camera initialized.")
        except Exception as e:
            print(f"[ERROR] Camera initialization failed: {e}")
            self.camera = None

    def stop_camera(self):
        """Stop camera to save power"""
        if self.camera:
            try:
                self.camera.stop()
                self.camera.close()
                print("[INFO] Camera stopped (idle).")
            except Exception:
                pass
            self.camera = None

    def wake_camera(self):
        """Wake camera if not active"""
        if self.camera is None:
            print("[INFO] Waking camera...")
            self.initialize_camera()

    def capture_frame(self):
        """Capture and process frame"""
        if not self.camera:
            return None

        try:
            frame = self.camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            detections = self.recognizer.recognize_faces(frame)
            for (name, conf, (x, y, w, h)) in detections:
                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                label = f"{name} ({conf:.1f})"
                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            self.config.EVENTS_DIR.mkdir(exist_ok=True)
            live_path = self.config.EVENTS_DIR / "live.jpg"
            cv2.imwrite(str(live_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            set_frame(frame)
            return frame

        except Exception as e:
            print(f"[ERROR] Capture failed: {e}")
            return None

    def check_pir_motion(self):
        """Read PIR state"""
        if not GPIO:
            import random
            return random.random() < 0.05  # simulation
        try:
            return GPIO.input(self.config.PIR_PIN) == GPIO.HIGH
        except Exception:
            return False

    def log_event(self, event_type, file_path=None, person=None):
        """Log events to DB"""
        try:
            with sqlite3.connect(self.config.DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO events (timestamp, event_type, file_path, person_name) VALUES (?, ?, ?, ?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), event_type, file_path, person),
                )
                conn.commit()
        except Exception as e:
            print(f"[ERROR] Logging failed: {e}")

    def record_clip(self, filename):
        """Record short clip"""
        if not self.camera:
            return
        path = self.config.RECORDINGS_DIR / filename
        self.config.RECORDINGS_DIR.mkdir(exist_ok=True)
        try:
            print(f"[INFO] Recording video: {path}")
            self.camera.start_recording(str(path))
            time.sleep(self.config.VIDEO_DURATION)
            self.camera.stop_recording()
            self.log_event("motion_recorded", str(path))
        except Exception as e:
            print(f"[ERROR] Recording failed: {e}")

    def run(self):
        """Main loop"""
        print("[INFO] Pi-Patrol active. Waiting for motion...")
        self.config.EVENTS_DIR.mkdir(exist_ok=True)
        self.config.RECORDINGS_DIR.mkdir(exist_ok=True)

        while True:
            motion = self.check_pir_motion()

            if motion:
                self.last_motion_time = time.time()
                self.wake_camera()
                print("[EVENT] Motion detected!")

                frame = self.capture_frame()
                if frame is not None:
                    detections = self.recognizer.recognize_faces(frame)
                    person = detections[0][0] if detections else "Unknown"

                    img_path = self.config.EVENTS_DIR / f"{person}_{int(time.time())}.jpg"
                    cv2.imwrite(str(img_path), frame)
                    self.log_event("motion_detected", str(img_path), person)

                    filename = f"record_{int(time.time())}.mp4"
                    threading.Thread(target=self.record_clip, args=(filename,)).start()
                    time.sleep(self.config.VIDEO_DURATION + 1)

            else:
                # If camera has been idle for a while — sleep it
                if self.camera and (time.time() - self.last_motion_time > self.config.IDLE_TIMEOUT):
                    self.stop_camera()

            time.sleep(0.3)


# ========== MAIN ==========
if _name_ == "_main_":
    launch_in_background()
    PiPatrol().run()
