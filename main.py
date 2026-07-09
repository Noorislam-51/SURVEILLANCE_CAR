"""
==============================================================================
 AI Surveillance Car — Real-Time Object + Traffic Light Command HUD
 Target: local Python, output served via web dashboard
 Pipeline: YOLOv8n detection -> HSV traffic-light colour classification
           -> priority-based driving command -> HUD overlay -> MJPEG stream

 PERFORMANCE NOTES (read before tuning further):
 - Capture and inference now run on SEPARATE threads. cap.read() never blocks
   waiting for YOLO, and YOLO never blocks waiting for the camera. This alone
   fixes most of the "video feels laggy/stuttery" complaint, because a slow
   video source no longer stalls the whole pipeline and vice versa.
 - Inference does NOT run on every captured frame (see FRAME_SKIP). Between
   inference frames we redraw the last known HUD/boxes onto the freshest raw
   frame, so the stream still looks live even though detection itself runs
   at a lower rate than capture.
 - imgsz=320 cuts YOLO inference time roughly in half vs default 640, with a
   real accuracy tradeoff on small/far objects. If your demo needs to detect
   small traffic lights at distance, bump this back up and accept fewer FPS.
 - This is still a CPU compute ceiling problem if you don't have CUDA. Check
   torch.cuda.is_available() below at startup — it's printed on launch.
==============================================================================
"""

import threading
import time
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from flask import Flask, Response

# ── Device check — tells you immediately whether you even have a chance
# at real smoothness, instead of you guessing after the fact ──────────
DEVICE = 0 if torch.cuda.is_available() else "cpu"
print(f"[startup] torch.cuda.is_available() = {torch.cuda.is_available()} -> using device={DEVICE}")
if DEVICE == "cpu":
    print("[startup] WARNING: running YOLO on CPU. Frame-skipping and imgsz=320 "
          "will help, but expect a hard ceiling around 10-15 FPS on typical "
          "laptop/Pi hardware. This is a compute limit, not a code bug.")

model = YOLO("yolov8n.pt")

# ── Tuning knobs ───────────────────────────────────────────────────
INFER_IMGSZ = 320       # lower = faster inference, worse small-object accuracy
FRAME_SKIP = 2          # run YOLO every Nth captured frame (1 = every frame)
STREAM_FPS_CAP = 20     # max frames/sec sent to the browser
JPEG_QUALITY = 75        # lower = faster encode + less bandwidth, more artifacts

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


def run_detection(frame):
    """One inference pass at reduced resolution. Returns raw detection DATA
    only — no drawing here. Drawing is separated out into draw_boxes() so
    the caller can re-apply the same box list to every subsequent frame
    until the next inference pass, instead of boxes only existing on the
    exact frame where YOLO happened to run (that was the flicker bug —
    boxes were popping in/out every other frame instead of persisting)."""
    results = model(frame, imgsz=INFER_IMGSZ, device=DEVICE, verbose=False)
    names, tl_colors, box_list = [], [], []

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
            box_list.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "color": box_col, "label": f"TL:{tl_color} {conf:.0%}", "thickness": 3,
            })
        else:
            box_list.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "color": (0, 255, 0), "label": f"{cls_name} {conf:.0%}", "thickness": 2,
            })

    cmd, col = get_command(results, frame)
    return cmd, col, names, tl_colors, box_list


def draw_boxes(frame, box_list):
    """Redraws a cached box list onto ANY frame. Called every loop
    iteration — inference frames and skipped frames alike — so boxes stay
    visibly present and just update in position every FRAME_SKIP frames,
    instead of blinking on/off."""
    for b in box_list:
        cv2.rectangle(frame, (b["x1"], b["y1"]), (b["x2"], b["y2"]), b["color"], b["thickness"])
        cv2.putText(frame, b["label"], (b["x1"], max(b["y1"] - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, b["color"], 1)
    return frame


# ── Shared state ────────────────────────────────────────────────────
# raw_frame: latest frame straight from the camera, no processing.
# latest_frame: latest ANNOTATED frame actually sent to the browser.
# Two separate locks because the capture thread and inference thread
# write to different things at different rates — sharing one lock would
# make the fast capture thread wait on the slow inference thread for no
# reason.
raw_frame = None
raw_lock = threading.Lock()

latest_frame = None
frame_lock = threading.Lock()

# VIDEO_SOURCE:
#   0                              -> default local webcam
#   "http://<esp32-ip>:81/stream"  -> ESP32-CAM / IP camera MJPEG stream
VIDEO_SOURCE = 0

stop_event = threading.Event()


def capture_loop():
    """ONLY grabs frames as fast as the camera can deliver them. Never
    touches YOLO. This is what was blocking your video before — capture
    and inference used to be the same loop, so a slow model made the
    camera read look slow too, even though the camera itself was fine."""
    global raw_frame

    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open video source: {VIDEO_SOURCE}. "
            "If using an IP camera, try appending /stream, /video, or /mjpeg to the URL. "
            "If using a local webcam on Windows and it still fails, try "
            "cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_DSHOW)."
        )
    # Ask the camera for a smaller frame directly, if it supports it.
    # Cheaper than capturing large and downscaling in software.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # avoid queued stale frames

    print("Capture thread started.")

    try:
        while not stop_event.is_set() and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame or stream ended.")
                break
            with raw_lock:
                raw_frame = frame
    finally:
        cap.release()
        print("Capture thread stopped.")


def inference_loop():
    """Runs YOLO on the freshest available raw frame, skipping frames as
    configured. Between inference passes, redraws the last known HUD onto
    fresh raw frames so the stream keeps moving at full capture rate even
    though detection itself is slower."""
    global latest_frame

    frame_count = 0
    last_cmd, last_col = "GO", (0, 200, 80)
    last_names, last_tl_colors, last_boxes = [], [], []

    while not stop_event.is_set():
        with raw_lock:
            frame = None if raw_frame is None else raw_frame.copy()
        if frame is None:
            time.sleep(0.01)
            continue

        frame_count += 1
        if frame_count % FRAME_SKIP == 0:
            last_cmd, last_col, last_names, last_tl_colors, last_boxes = run_detection(frame)

        # Runs EVERY frame, whether or not inference ran this iteration.
        # Boxes/HUD are drawn from the cached (last_*) values so they never
        # disappear — they just update in position/label every FRAME_SKIP
        # frames instead of every single frame.
        frame = draw_boxes(frame, last_boxes)
        frame = draw_hud(frame, last_cmd, last_col, last_names, last_tl_colors)
        with frame_lock:
            latest_frame = frame


# ── Flask MJPEG server ─────────────────────────────────────────────
app = Flask(__name__)


def gen_frames():
    """Rate-limited generator. Previously this busy-waited with a bare
    `continue` whenever latest_frame was None, pegging a CPU core doing
    nothing useful. Now it sleeps when idle and caps send rate so we're
    not re-encoding/re-sending frames faster than the browser can render
    or faster than the frame actually changes."""
    last_sent_id = None
    min_interval = 1.0 / STREAM_FPS_CAP

    while True:
        loop_start = time.time()

        with frame_lock:
            frame = latest_frame

        if frame is None or id(frame) == last_sent_id:
            time.sleep(0.01)
            continue

        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ret:
            continue

        last_sent_id = id(frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        elapsed = time.time() - loop_start
        sleep_left = min_interval - elapsed
        if sleep_left > 0:
            time.sleep(sleep_left)


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/')
def dashboard():
    with open('surveillance_dashboard.html', 'r', encoding='utf-8') as f:
        return f.read()


if __name__ == '__main__':
    t_capture = threading.Thread(target=capture_loop, daemon=True)
    t_infer = threading.Thread(target=inference_loop, daemon=True)
    t_capture.start()
    t_infer.start()

    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        stop_event.set()