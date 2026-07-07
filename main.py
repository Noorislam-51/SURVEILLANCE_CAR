"""
==============================================================================
 AI Surveillance Car — Real-Time Object + Traffic Light Command HUD
 Target: VS Code / local Python, output served ONLY via web dashboard
 Pipeline: YOLOv8n detection -> HSV traffic-light colour classification
           -> priority-based driving command -> HUD overlay -> MJPEG stream
==============================================================================
"""

import threading
import cv2
import numpy as np
from ultralytics import YOLO
from flask import Flask, Response

# Initialize your model
model = YOLO("yolov8n.pt")

# ── HSV colour ranges for traffic light signals ──────────────────
TL_COLOR_RANGES = {
    "red": [
        (np.array([0,   120, 100]), np.array([10,  255, 255])),
        (np.array([160, 120, 100]), np.array([180, 255, 255])),
    ],
    "yellow": [
        (np.array([15, 120, 100]), np.array([40, 255, 255])),
    ],
    "green": [
        (np.array([40, 60, 60]), np.array([90, 255, 255])),
    ],
}

TL_COMMANDS = {
    "red":     ("BRAKE",   (0, 0, 220),   1),
    "yellow":  ("SLOW",    (0, 140, 255), 2),
    "green":   ("GO",      (0, 200, 80),  5),
    "unknown": ("CAUTION", (0, 200, 200), 4),
}

MIN_PIXELS = 30   # ignore tiny colour blobs


def detect_tl_color(frame, x1, y1, x2, y2):
    pad = 4
    fh, fw = frame.shape[:2]
    cx1 = max(0, x1 - pad)
    cy1 = max(0, y1 - pad)
    cx2 = min(fw, x2 + pad)
    cy2 = min(fh, y2 + pad)

    crop = frame[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return "unknown"

    crop = cv2.resize(crop, (30, 90))
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    thirds = {
        "red":    hsv[0:30, :],
        "yellow": hsv[30:60, :],
        "green":  hsv[60:90, :],
    }

    scores = {}
    for color, zone in thirds.items():
        count = 0
        for (lo, hi) in TL_COLOR_RANGES[color]:
            mask = cv2.inRange(zone, lo, hi)
            count += int(np.count_nonzero(mask))
        scores[color] = count

    best_color = max(scores, key=scores.get)
    if scores[best_color] < MIN_PIXELS:
        return "unknown"
    return best_color


# ── Command engine ────────────────────────────────────────────────
COMMAND_RULES = [
    (1, "BRAKE",   (0, 0, 220),   {"person", "stop sign"}),
    (2, "SLOW",    (0, 140, 255), {"dog", "cat", "bicycle", "horse"}),
    (3, "HORN",    (0, 100, 200), {"bird", "bear", "backpack", "suitcase"}),
    (4, "CAUTION", (0, 200, 200), {"car", "truck", "bus", "motorcycle"}),
    (5, "GO",      (0, 200, 80),  set()),
]

CONF_THRESHOLD = 0.45
CLOSE_FRACTION = 0.30


def get_command(results, frame):
    fh = frame.shape[0]
    best_pri, best_cmd, best_col = 5, "GO", (0, 200, 80)

    for box in results[0].boxes:
        conf = float(box.conf[0])
        if conf < CONF_THRESHOLD:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cls_name = model.names[int(box.cls[0])].lower()
        close = (y2 - y1) / fh > CLOSE_FRACTION

        if cls_name == "traffic light":
            tl_color = detect_tl_color(frame, x1, y1, x2, y2)
            cmd_lbl, col, pri = TL_COMMANDS[tl_color]
            if not close:
                pri = max(pri, 4)
            if pri < best_pri:
                best_pri, best_cmd, best_col = pri, cmd_lbl, col
            continue

        for pri, cmd, col, triggers in COMMAND_RULES[:-1]:
            if cls_name in triggers:
                if not close and pri <= 2:
                    pri, cmd, col = 4, "CAUTION", (0, 200, 200)
                if pri < best_pri:
                    best_pri, best_cmd, best_col = pri, cmd, col
                break

    return best_cmd, best_col


def draw_hud(frame, cmd, col, names, tl_colors):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], 70), (20, 20, 20), -1)
    frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)
    cv2.putText(frame, cmd, (12, 48),
                cv2.FONT_HERSHEY_DUPLEX, 1.5, col, 2, cv2.LINE_AA)
    info = "  |  " + ", ".join(sorted(set(names))) if names else ""
    cv2.putText(frame, info, (200, 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

    badge_x = 12
    for tl_c in tl_colors:
        badge_col = {"red": (0, 0, 200), "yellow": (0, 180, 220),
                     "green": (0, 180, 60), "unknown": (100, 100, 100)}[tl_c]
        cv2.rectangle(frame, (badge_x, 54), (badge_x + 80, 68), badge_col, -1)
        cv2.putText(frame, f"TL:{tl_c}", (badge_x + 4, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        badge_x += 90
    return frame


# ── Shared state between the capture thread and the Flask server ──
# latest_frame holds the most recent ANNOTATED (boxes + HUD drawn) frame.
# A lock guards it since two threads touch it: the capture loop writes,
# the Flask generator reads. Without the lock you can read a half-written
# frame and get visual tearing/corruption in the stream.
latest_frame = None
frame_lock = threading.Lock()

# VIDEO_SOURCE:
#   0                              -> default local webcam
#   "http://<esp32-ip>:81/stream"  -> ESP32-CAM / IP camera MJPEG stream
VIDEO_SOURCE = 0


def capture_loop():
    """Runs forever in a background thread: grab frame, detect, annotate,
    store into latest_frame. No cv2.imshow — display happens only in the
    browser dashboard via the /video_feed route below."""
    global latest_frame

    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open video source: {VIDEO_SOURCE}. "
            "If using an IP camera, try appending /stream, /video, or /mjpeg to the URL. "
            "If using a local webcam on Windows and it still fails, try "
            "cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_DSHOW)."
        )

    print("Capture thread started.")

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame or stream ended.")
                break

            results = model(frame, verbose=False)
            names, tl_colors = [], []

            for box in results[0].boxes:
                conf = float(box.conf[0])
                if conf < CONF_THRESHOLD:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_name = model.names[int(box.cls[0])].lower()
                names.append(cls_name)

                if cls_name == "traffic light":
                    tl_color = detect_tl_color(frame, x1, y1, x2, y2)
                    tl_colors.append(tl_color)
                    box_col = {"red": (0, 0, 255), "yellow": (0, 220, 255),
                               "green": (0, 255, 60), "unknown": (128, 128, 128)}[tl_color]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_col, 3)
                    cv2.putText(frame, f"TL:{tl_color} {conf:.0%}",
                                (x1, max(y1 - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX,
                                0.55, box_col, 1)
                else:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{cls_name} {conf:.0%}",
                                (x1, max(y1 - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 255, 0), 1)

            cmd, col = get_command(results, frame)
            frame = draw_hud(frame, cmd, col, names, tl_colors)

            with frame_lock:
                latest_frame = frame

    finally:
        cap.release()
        print("Capture thread stopped.")


# ── Flask MJPEG server (this is what the dashboard HTML points at) ─
app = Flask(__name__)


def gen_frames():
    while True:
        with frame_lock:
            if latest_frame is None:
                continue
            ret, jpeg = cv2.imencode('.jpg', latest_frame)
        if not ret:
            continue
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/')
def dashboard():
    # Serves surveillance_dashboard.html directly, so hitting the bare
    # host in a browser shows the dashboard instead of 404ing.
    # Requires surveillance_dashboard.html to sit in the same folder as this script.
    with open('surveillance_dashboard.html', 'r', encoding='utf-8') as f:
        return f.read()


if __name__ == '__main__':
    # Capture/detection runs in the background; Flask owns the main thread
    # so it can actually accept HTTP connections from the dashboard.
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    # host='0.0.0.0' is required if the dashboard is opened from a different
    # device than the one running this script (e.g. viewing from your phone
    # while this runs on a laptop/Pi attached to the camera).
    app.run(host='0.0.0.0', port=5000)