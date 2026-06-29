
"""
SafeWatch Edge — YOLOv8n-pose Fall & Bed-Exit Detector
=======================================================
Requirements:
    pip install ultralytics requests numpy opencv-python

Usage:
    python edge_detector.py --source 0 --room "ROOM-01" \
        --api-url http://localhost:8000 --api-key YOUR_TOKEN

    # CSI camera (Jetson Nano):
    python edge_detector.py --source csi --room "ROOM-01" \
        --api-url http://localhost:8000 --api-key YOUR_TOKEN

    # Video file:
    python edge_detector.py --source /path/to/video.mp4 --room "ROOM-01" \
        --api-url http://localhost:8000 --api-key YOUR_TOKEN
"""

import argparse
import os
import threading
import time
from collections import deque

import cv2
import numpy as np
import requests
from ultralytics import YOLO

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
YOLO_MODEL    = os.getenv("YOLO_MODEL",    "yolov8n-pose.pt")
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "http://localhost:8000")
EDGE_API_KEY  = os.getenv("EDGE_API_KEY",  "")
ROOM_NUMBER   = os.getenv("ROOM_NUMBER",   "ROOM-01")

# Detection tuning
HISTORY_LEN         = 20
FALL_CONFIRM_FRAMES = 12
RECOVERY_FRAMES     = 25
BED_Y_THRESHOLD     = 0.55
MIN_KEYPOINT_CONF   = 0.35

# Kinematics thresholds
TYPOLOGY_DELTA_Y    = 0.15
TYPOLOGY_DELTA_X    = 0.08
HEAD_VELOCITY_LIMIT = 0.06
HEAD_HIP_FLAT_DELTA = 0.05

# Resolution cap (keeps RAM usage low on Jetson)
FRAME_W = 640
FRAME_H = 480

C = {
    "safe":   (50, 200, 50),
    "warn":   (30, 160, 255),
    "danger": (30,  30, 220),
    "skel":   (160, 160, 160),
    "white":  (255, 255, 255),
}

# ─────────────────────────────────────────────────────────────────────────────
# Camera helpers
# ─────────────────────────────────────────────────────────────────────────────

def gstreamer_pipeline(
    capture_width  = FRAME_W,
    capture_height = FRAME_H,
    display_width  = FRAME_W,
    display_height = FRAME_H,
    framerate      = 15,
    flip_method    = 0,
) -> str:
    return (
        f"nvarguscamerasrc ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, "
        f"height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, width=(int){display_width}, height=(int){display_height}, "
        f"format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! "
        f"appsink"
    )


def open_capture(source: str) -> cv2.VideoCapture:
    if source == "csi":
        cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
    elif source.isdigit():
        cap = cv2.VideoCapture(int(source))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    else:
        cap = cv2.VideoCapture(source)
    return cap


# ─────────────────────────────────────────────────────────────────────────────
# Keypoint mapping (COCO 17 keypoints)
# ─────────────────────────────────────────────────────────────────────────────
COCO_KP = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
]
KP_IDX = {name: i for i, name in enumerate(COCO_KP)}

SKELETON_PAIRS = [
    ("nose", "left_shoulder"),  ("nose", "right_shoulder"),
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),   ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),     ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),   ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
]


def yolo_kps_to_native(raw_kps: np.ndarray, frame_h: int, frame_w: int) -> dict:
    result = {}
    for name, idx in KP_IDX.items():
        px, py, conf = raw_kps[idx]
        result[name] = [float(py) / frame_h, float(px) / frame_w, float(conf)]
    return result


def cluster_mean(kps: dict, names: list):
    valid = [
        (kps[n][0], kps[n][1])
        for n in names
        if n in kps and kps[n][2] >= MIN_KEYPOINT_CONF
    ]
    if not valid:
        return None
    return float(np.mean([v[0] for v in valid])), float(np.mean([v[1] for v in valid]))


# ─────────────────────────────────────────────────────────────────────────────
# Per-person tracker
# ─────────────────────────────────────────────────────────────────────────────

class PersonTracker:
    def __init__(self, track_id: int):
        self.track_id              = track_id
        self.head_hist             = deque(maxlen=HISTORY_LEN)
        self.torso_hist            = deque(maxlen=HISTORY_LEN)
        self.hip_hist              = deque(maxlen=HISTORY_LEN)
        self.knee_hist             = deque(maxlen=HISTORY_LEN)
        self.fall_counter          = 0
        self.recovery_counter      = 0
        self.fall_active           = False
        self.bed_exit_active       = False
        self.floor_api_transmitted = False
        self.bed_api_transmitted   = False
        self.kinematics            = None
        self.primary_impact        = None
        self.head_strike_risk      = None

    def _update_history(self, kps: dict):
        head  = cluster_mean(kps, ["nose", "left_ear", "right_ear"])
        torso = cluster_mean(kps, ["left_shoulder", "right_shoulder"])
        hip   = cluster_mean(kps, ["left_hip", "right_hip"])
        knee  = cluster_mean(kps, ["left_knee", "right_knee"])
        if head:  self.head_hist.append(head)
        if torso: self.torso_hist.append(torso)
        if hip:   self.hip_hist.append(hip)
        if knee:  self.knee_hist.append(knee)

    def _fall_signals(self, kps: dict):
        signals = []
        torso = cluster_mean(kps, ["left_shoulder", "right_shoulder"])
        hip   = cluster_mean(kps, ["left_hip", "right_hip"])
        ankle = cluster_mean(kps, ["left_ankle", "right_ankle"])

        if torso and hip:
            dy    = hip[0] - torso[0]
            dx    = hip[1] - torso[1]
            angle = abs(np.degrees(np.arctan2(abs(dx), abs(dy) + 1e-6)))
            signals.append(angle > 45)

        if hip and ankle:
            ratio = 1.0 - (hip[0] / (ankle[0] + 1e-6))
            signals.append(ratio < 0.25)

        pts = [
            (kps[n][0], kps[n][1])
            for n in COCO_KP
            if n in kps and kps[n][2] >= MIN_KEYPOINT_CONF
        ]
        if len(pts) >= 4:
            ys     = [p[0] for p in pts]
            xs     = [p[1] for p in pts]
            aspect = (max(xs) - min(xs)) / (max(ys) - min(ys) + 1e-6)
            signals.append(aspect > 1.2)

        return sum(signals), len(signals)

    def _compute_kinematics(self):
        if len(self.hip_hist) >= 2:
            start   = self.hip_hist[0]
            end     = self.hip_hist[-1]
            delta_y = end[0] - start[0]
            delta_x = abs(end[1] - start[1])
            if delta_y > TYPOLOGY_DELTA_Y and delta_x < TYPOLOGY_DELTA_X:
                self.kinematics = "Vertical Collapse (Fainting/Slipping)"
            elif delta_x >= TYPOLOGY_DELTA_X:
                self.kinematics = "Forward/Backward Trip"
            else:
                self.kinematics = "Undetermined"
        else:
            self.kinematics = "Insufficient data"

        def peak_velocity(hist):
            if len(hist) < 2:
                return 0.0
            dys = [hist[i][0] - hist[i - 1][0] for i in range(1, len(hist))]
            return max(dys) if dys else 0.0

        v_torso = peak_velocity(self.torso_hist)
        v_hip   = peak_velocity(self.hip_hist)
        v_knee  = peak_velocity(self.knee_hist)

        if v_hip >= v_torso and v_hip >= v_knee:
            self.primary_impact = "Hip (Central/Unknown)"
        elif v_torso >= v_knee:
            self.primary_impact = "Torso/Shoulder"
        else:
            self.primary_impact = "Knee"

        v_head        = peak_velocity(self.head_hist)
        head_y        = self.head_hist[-1][0] if self.head_hist else None
        hip_y         = self.hip_hist[-1][0]  if self.hip_hist  else None
        high_velocity = v_head > HEAD_VELOCITY_LIMIT
        flat_position = (
            head_y is not None and hip_y is not None
            and head_y >= hip_y - HEAD_HIP_FLAT_DELTA
        )
        self.head_strike_risk = "HIGH RISK" if (high_velocity or flat_position) else "Low Risk"

    def update(self, kps: dict, person_bbox_cy: float) -> dict:
        self._update_history(kps)
        n_true, n_valid = self._fall_signals(kps)
        fall_now = n_valid >= 2 and n_true >= 2
        bed_area = person_bbox_cy < BED_Y_THRESHOLD

        if fall_now:
            self.fall_counter     += 1
            self.recovery_counter  = 0
        else:
            self.recovery_counter += 1
            self.fall_counter      = max(0, self.fall_counter - 1)

        newly_confirmed = False
        if self.fall_counter >= FALL_CONFIRM_FRAMES and not self.fall_active:
            self.fall_active  = True
            newly_confirmed   = True
            self._compute_kinematics()

        if self.recovery_counter >= RECOVERY_FRAMES and self.fall_active:
            self.fall_active           = False
            self.fall_counter          = 0
            self.floor_api_transmitted = False

        if bed_area and not self.bed_exit_active:
            self.bed_exit_active = True
        if not bed_area and self.bed_exit_active:
            self.bed_exit_active     = False
            self.bed_api_transmitted = False

        return {
            "track_id"              : self.track_id,
            "fall_active"           : self.fall_active,
            "newly_confirmed"       : newly_confirmed,
            "fall_now"              : fall_now,
            "bed_exit_active"       : self.bed_exit_active,
            "floor_api_transmitted" : self.floor_api_transmitted,
            "bed_api_transmitted"   : self.bed_api_transmitted,
            "kinematics"            : self.kinematics,
            "primary_impact"        : self.primary_impact,
            "head_strike_risk"      : self.head_strike_risk,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Cloud telemetry (non-blocking thread)
# ─────────────────────────────────────────────────────────────────────────────

def _post_to_cloud(event_type, state, room_number, cloud_api_url, edge_api_key):
    payload = {
        "room_number"      : room_number,
        "patient_track_id" : state["track_id"],
        "event_type"       : event_type,
        "kinematics"       : state.get("kinematics")       or None,
        "primary_impact"   : state.get("primary_impact")   or None,
        "head_strike_risk" : state.get("head_strike_risk") or None,
        "image_url"        : None,
    }
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{cloud_api_url}/api/v1/telemetry/events",
                json    = payload,
                headers = {
                    "X-API-KEY"    : edge_api_key,
                    "Content-Type" : "application/json",
                },
                timeout = 10,
            )
            print(f"[CLOUD] {event_type} → HTTP {resp.status_code} (track {state['track_id']})")
            return
        except requests.RequestException as exc:
            print(f"[WARN] Attempt {attempt+1}/3 failed: {exc}")
            time.sleep(2 ** attempt)
    print(f"[ERROR] All retries exhausted for {event_type} track {state['track_id']}")


def dispatch_telemetry(event_type, state, room_number, cloud_api_url, edge_api_key):
    threading.Thread(
        target = _post_to_cloud,
        args   = (event_type, state, room_number, cloud_api_url, edge_api_key),
        daemon = True,
    ).start()


# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────

def draw_skeleton(frame, kps, fall):
    h, w    = frame.shape[:2]
    j_color = C["danger"] if fall else C["safe"]
    l_color = C["warn"]   if fall else C["skel"]

    for name, (ky, kx, kc) in kps.items():
        if kc >= MIN_KEYPOINT_CONF:
            cv2.circle(frame, (int(kx * w), int(ky * h)), 4, j_color, -1, cv2.LINE_AA)

    for a, b in SKELETON_PAIRS:
        if a in kps and b in kps:
            ay, ax, ac = kps[a]
            by, bx, bc = kps[b]
            if ac >= MIN_KEYPOINT_CONF and bc >= MIN_KEYPOINT_CONF:
                cv2.line(
                    frame,
                    (int(ax * w), int(ay * h)),
                    (int(bx * w), int(by * h)),
                    l_color, 2, cv2.LINE_AA,
                )


def draw_hud(frame, states, fps, room):
    h, w = frame.shape[:2]
    cv2.putText(frame, f"Room: {room}  FPS:{fps:.0f}", (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, C["white"], 1, cv2.LINE_AA)

    for idx, s in enumerate(states):
        if not (s["fall_active"] or s["bed_exit_active"]):
            continue
        fall  = s["fall_active"]
        label = f"ID {s['track_id']}: {'!!! FALL !!!' if fall else 'BED EXIT'}"
        col   = C["danger"] if fall else C["warn"]
        if fall and int(time.time() * 2) % 2 == 0:
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), C["danger"], 4)
        py = 52 + idx * 40
        cv2.putText(frame, label, (10, py),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, col, 2, cv2.LINE_AA)
        if fall and s.get("kinematics"):
            info = f"  {s['kinematics']} | {s['primary_impact']} | {s['head_strike_risk']}"
            cv2.putText(frame, info, (10, py + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, C["white"], 1, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SafeWatch Edge Detector — YOLOv8n-pose")
    parser.add_argument("--source",     default="0",
                        help="0=webcam, csi=Jetson CSI cam, or path to video file")
    parser.add_argument("--room",       default=ROOM_NUMBER)
    parser.add_argument("--api-url",    default=CLOUD_API_URL)
    parser.add_argument("--api-key",    default=EDGE_API_KEY)
    parser.add_argument("--model",      default=YOLO_MODEL,
                        help="Path to .pt file (default: yolov8n-pose.pt)")
    parser.add_argument("--save",       default=None,
                        help="Save output video to this path")
    parser.add_argument("--no-display", action="store_true",
                        help="Run headless — no window (for SSH)")
    args = parser.parse_args()

    if not args.api_key:
        print("[ERROR] Set --api-key  (get it from the /auth/register endpoint)")
        return

    print(f"[INFO] Loading {args.model} ...")
    model = YOLO(args.model)

    cap = open_capture(args.source)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open source: {args.source}")
        return

    fw      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  or FRAME_W
    fh      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or FRAME_H
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 15

    writer = None
    if args.save:
        writer = cv2.VideoWriter(
            args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps_src, (fw, fh)
        )

    trackers: dict[int, PersonTracker] = {}
    fps_buf  = deque(maxlen=30)
    prev_t   = time.time()

    print(f"[INFO] SafeWatch running — Room: {args.room}")
    print(f"[INFO] Sending events to: {args.api_url}")
    print("[INFO] Press Q to quit" if not args.no_display else "[INFO] Headless mode — Ctrl-C to stop")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        now = time.time()
        fps_buf.append(1.0 / max(now - prev_t, 1e-6))
        prev_t = now

        # ── YOLOv8 inference + tracking ───────────────────────────────────
        results = model.track(frame, persist=True, verbose=False, classes=[0])
        frame_states: list[dict] = []

        if results and results[0].keypoints is not None:
            r       = results[0]
            kp_data = r.keypoints.data.cpu().numpy()
            boxes   = r.boxes

            for i in range(len(kp_data)):
                tid    = int(boxes.id[i].item()) if boxes.id is not None else i
                kps    = yolo_kps_to_native(kp_data[i], fh, fw)
                box_cy = float(boxes.xyxyn[i][1] + boxes.xyxyn[i][3]) / 2.0

                if tid not in trackers:
                    trackers[tid] = PersonTracker(tid)
                tracker = trackers[tid]
                state   = tracker.update(kps, box_cy)
                frame_states.append(state)

                if state["fall_active"] and not state["floor_api_transmitted"]:
                    tracker.floor_api_transmitted = True
                    dispatch_telemetry(
                        "FLOOR_FALL", state, args.room, args.api_url, args.api_key
                    )

                if state["bed_exit_active"] and not state["bed_api_transmitted"]:
                    tracker.bed_api_transmitted = True
                    dispatch_telemetry(
                        "BED_EXIT", state, args.room, args.api_url, args.api_key
                    )

                draw_skeleton(frame, kps, state["fall_active"])

        # Prune lost tracks
        active_ids = set()
        if results and results[0].boxes.id is not None:
            active_ids = {
                int(results[0].boxes.id[i].item())
                for i in range(len(results[0].boxes.id))
            }
        for gone_id in list(trackers.keys()):
            if gone_id not in active_ids:
                del trackers[gone_id]

        fps_avg = float(np.mean(fps_buf)) if fps_buf else 0.0
        draw_hud(frame, frame_states, fps_avg, args.room)

        if writer:
            writer.write(frame)

        if not args.no_display:
            cv2.imshow("SafeWatch Edge", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
    print("[INFO] SafeWatch stopped.")


if __name__ == "__main__":
    main()