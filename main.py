import cv2
import numpy as np
from ultralytics import YOLO

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
    "yellow":  ("SLOW",    (0, 140, 255),  2),
    "green":   ("GO",      (0, 200, 80),   5),
    "unknown": ("CAUTION", (0, 200, 200),  4),
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
    hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    thirds = {
        "red":    hsv[0:30,  :],
        "yellow": hsv[30:60, :],
        "green":  hsv[60:90, :],
    }

    scores = {}
    for color, zone in thirds.items():
        count = 0
        for (lo, hi) in TL_COLOR_RANGES[color]:
            mask   = cv2.inRange(zone, lo, hi)
            count += int(np.count_nonzero(mask))
        scores[color] = count

    best_color = max(scores, key=scores.get)
    if scores[best_color] < MIN_PIXELS:
        return "unknown"
    return best_color


# ── Updated command engine ────────────────────────────────────────
COMMAND_RULES = [
    (1, "BRAKE",   (0, 0, 220),   {"person", "stop sign"}),
    (2, "SLOW",    (0, 140, 255), {"dog", "cat", "bicycle", "horse"}),
    (3, "HORN",    (0, 100, 200), {"bird", "bear", "backpack", "suitcase"}),
    (4, "CAUTION", (0, 200, 200), {"car", "truck", "bus", "motorcycle"}),
    (5, "GO",      (0, 200, 80),  set()),
]

CONF_THRESHOLD  = 0.45
CLOSE_FRACTION  = 0.30

def get_command(results, frame):
    fh = frame.shape[0]
    best_pri, best_cmd, best_col = 5, "GO", (0, 200, 80)

    for box in results[0].boxes:
        conf = float(box.conf[0])
        if conf < CONF_THRESHOLD:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cls_name = model.names[int(box.cls[0])].lower()
        close    = (y2 - y1) / fh > CLOSE_FRACTION

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
        badge_col = {"red": (0,0,200), "yellow": (0,180,220),
                     "green": (0,180,60), "unknown": (100,100,100)}[tl_c]
        cv2.rectangle(frame, (badge_x, 54), (badge_x + 80, 68), badge_col, -1)
        cv2.putText(frame, f"TL:{tl_c}", (badge_x + 4, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        badge_x += 90
    return frame


# ── Main loop configured for your active Ngrok Tunnel ───────────────────────

# Changed URL to pull directly from your ngrok public address root.
# Note: If your hardware needs a specific path, you can append it here (e.g., /stream or /mjpeg)

# cap = cv2.VideoCapture("http://192.168.4.1:81/stream")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print(f"Error: Unable to open video stream at {NGROK_STREAM_URL}")
    print("If it fails, try adding common stream paths (e.g., suffixing /stream, /video, or /mjpeg)")
else:
    print("Streaming started in Colab. Click 'Stop' on the cell execution to stop.")

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
                box_col = {"red": (0,0,255), "yellow": (0,220,255),
                           "green": (0,255,60), "unknown": (128,128,128)}[tl_color]
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_col, 3)
                cv2.putText(frame, f"TL:{tl_color} {conf:.0%}",
                            (x1, max(y1-6, 12)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, box_col, 1)
            else:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{cls_name} {conf:.0%}",
                            (x1, max(y1-6, 12)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 0), 1)

        cmd, col = get_command(results, frame)
        frame = draw_hud(frame, cmd, col, names, tl_colors)

        # Clear output to create a cohesive video playback effect inside the notebook
        cv2.imshow("AI Surveillance Car", frame)

        # Press Q to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("Stream stopped manually.")

finally:
    cap.release()
    cv2.destroyAllWindows()