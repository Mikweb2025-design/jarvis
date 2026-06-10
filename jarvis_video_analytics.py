#!/usr/bin/env python3
"""jarvis_video_analytics.py — Video Analytics: car/person counting via YOLO + OpenCV"""
import os, json, time, threading, sqlite3, math, urllib.request, zipfile, ssl, traceback
from pathlib import Path
from datetime import datetime, timedelta
import cv2
import numpy as np

DATA_DIR = Path(__file__).parent / "data"
MODEL_DIR = DATA_DIR / "yolo"
DB_PATH = DATA_DIR / "video_analytics.db"
DEFAULT_RTSP = "rtsp://jarvis:dorina79@192.168.1.9:554/h264Preview_01_main"

_instances = {}
_lock = threading.Lock()

# ── YOLO classes we care about ──
COCO_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck", 0: "person"}
VEHICLE_IDS = {2, 3, 5, 7}
# Altezza riferimento per tipo (per velocità) — più stabile della larghezza
REF_HEIGHT = {0: 1.7, 2: 1.5, 3: 1.2, 5: 3.2, 7: 3.0}
# Calibrazione prospettiva: rapporto tra altezza bbox e distanza reale
# Valore più alto = più zoom (pixel per metro). Default per telecamera traffico.
SPEED_CALIBRATION = 1.0

def _db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            hour TEXT NOT NULL,
            stream_url TEXT NOT NULL,
            cars INTEGER DEFAULT 0,
            people INTEGER DEFAULT 0,
            vehicles INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS speed_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            obj_type TEXT NOT NULL,
            speed REAL DEFAULT 0
        )
    """)
    conn.commit()
    return conn

def _urlretrieve(url, path):
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(url, context=ctx, timeout=30) as src:
        with open(path, "wb") as dst:
            dst.write(src.read())

def _download_yolo():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    cfg_path = MODEL_DIR / "yolov4-tiny.cfg"
    weights_path = MODEL_DIR / "yolov4-tiny.weights"
    names_path = MODEL_DIR / "coco.names"

    if not cfg_path.exists():
        print("[VIDEO] Downloading YOLOv4-tiny config...")
        _urlretrieve(
            "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg",
            cfg_path)

    if not weights_path.exists():
        print("[VIDEO] Downloading YOLOv4-tiny weights (23 MB)...")
        _urlretrieve(
            "https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights",
            weights_path)

    if not names_path.exists():
        print("[VIDEO] Downloading COCO names...")
        _urlretrieve(
            "https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names",
            names_path)

    return str(cfg_path), str(weights_path), str(names_path)


class IouTracker:
    def __init__(self, max_disappeared=30, iou_threshold=0.25):
        self.next_id = 0
        self.objects = {}
        self.disappeared = {}
        self.max_disappeared = max_disappeared
        self.iou_threshold = iou_threshold

    def _iou(self, a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1 = max(ax, bx); y1 = max(ay, by)
        x2 = min(ax + aw, bx + bw); y2 = min(ay + ah, by + bh)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = aw * ah; area_b = bw * bh
        return inter / (area_a + area_b - inter) if (area_a + area_b - inter) > 0 else 0

    def update(self, detections):
        if not detections:
            for oid in list(self.disappeared.keys()):
                self.disappeared[oid] += 1
                if self.disappeared[oid] > self.max_disappeared:
                    del self.objects[oid]
                    del self.disappeared[oid]
            return {oid: self.objects[oid]["centroid"] for oid in self.objects}

        if not self.objects:
            for d in detections:
                self.objects[self.next_id] = {"centroid": d["centroid"], "bbox": d["bbox"], "class_id": d["class_id"]}
                self.disappeared[self.next_id] = 0
                self.next_id += 1
        else:
            oids = list(self.objects.keys())
            old_bboxes = [self.objects[oid]["bbox"] for oid in oids]
            new_bboxes = [d["bbox"] for d in detections]
            iou_matrix = np.zeros((len(oids), len(detections)))
            for i, ob in enumerate(old_bboxes):
                for j, nb in enumerate(new_bboxes):
                    iou_matrix[i, j] = self._iou(ob, nb)
            matched_oids = set()
            matched_dets = set()
            for _ in range(min(len(oids), len(detections))):
                idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                if iou_matrix[idx] < self.iou_threshold:
                    break
                oid = oids[idx[0]]
                det = detections[idx[1]]
                self.objects[oid] = {"centroid": det["centroid"], "bbox": det["bbox"], "class_id": det["class_id"]}
                self.disappeared[oid] = 0
                matched_oids.add(idx[0]); matched_dets.add(idx[1])
                iou_matrix[idx[0], :] = -1
                iou_matrix[:, idx[1]] = -1
            for i, d in enumerate(detections):
                if i not in matched_dets:
                    self.objects[self.next_id] = {"centroid": d["centroid"], "bbox": d["bbox"], "class_id": d["class_id"]}
                    self.disappeared[self.next_id] = 0
                    self.next_id += 1
            for i, oid in enumerate(oids):
                if i not in matched_oids:
                    self.disappeared[oid] += 1
                    if self.disappeared[oid] > self.max_disappeared:
                        del self.objects[oid]
                        del self.disappeared[oid]
        return {oid: self.objects[oid]["centroid"] for oid in self.objects}


class VideoAnalytics:
    def __init__(self, stream_url=None):
        self.stream_url = stream_url
        self.running = False
        self.thread = None
        self.cap = None
        self.net = None
        self.model_loaded = False
        self.fps = 0
        self.frame_count = 0
        self.detection_line_y = None
        self.crossed_ids = set()
        self._prev_positions = {}
        self.people_count = 0
        self.car_count = 0
        self.truck_count = 0
        self.bus_count = 0
        self.moto_count = 0
        self.last_hour = None
        self._last_flushed_cars = 0
        self._last_flushed_people = 0
        self._last_flushed_trucks = 0
        self._last_flushed_buses = 0
        self._last_flushed_motos = 0
        self._last_flush_time = time.time()
        self.speed_samples = []
        self.tracker = IouTracker(max_disappeared=30, iou_threshold=0.15)
        self.object_speeds = {}
        self._frame_skip_counter = 0
        self._yolo_every = 3
        self._detect_h = 480
        self._jpeg_cache = None
        self._load_model()

    def _load_model(self):
        try:
            cfg, weights, names = _download_yolo()
            self.net = cv2.dnn.readNet(weights, cfg)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.model_loaded = True
            self.input_w, self.input_h = 416, 416
            print(f"[VIDEO] YOLOv4-tiny loaded")
        except Exception as e:
            print(f"[VIDEO] YOLO load failed ({e}), using MOG2 fallback")

    def _detect_yolo(self, frame):
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (self.input_w, self.input_h), swapRB=True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        boxes, confs, class_ids = [], [], []
        for out in outs:
            for det in out:
                scores = det[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > 0.3 and class_id in COCO_CLASSES:
                    cx, cy, bw, bh = det[:4] * np.array([w, h, w, h])
                    x = int(cx - bw/2)
                    y = int(cy - bh/2)
                    boxes.append([x, y, int(bw), int(bh)])
                    confs.append(float(confidence))
                    class_ids.append(class_id)
        idxs = cv2.dnn.NMSBoxes(boxes, confs, 0.3, 0.3)
        detections = []
        if len(idxs) > 0:
            for i in idxs.flatten():
                x, y, bw, bh = boxes[i]
                cx, cy = x + bw // 2, y + bh // 2
                detections.append({
                    "bbox": (x, y, bw, bh),
                    "centroid": (cx, cy),
                    "class_id": class_ids[i],
                    "label": COCO_CLASSES[class_ids[i]],
                    "confidence": confs[i]
                })
        return detections

    def _detect_motion(self, frame):
        h, w = frame.shape[:2]
        frame_area = h * w
        if not hasattr(self, '_mog2'):
            self._mog2 = cv2.createBackgroundSubtractorMOG2()
            self._last_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return []
        fg = self._mog2.apply(frame)
        _, thresh = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            area_ratio = area / frame_area
            if area_ratio < 0.002:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            cx, cy = x + bw//2, y + bh//2
            aspect = bw / max(bh, 1)
            if area_ratio > 0.04 and aspect > 1.6:
                label, class_id = "truck", 7
            elif area_ratio > 0.012 and 0.6 < aspect < 2.8:
                label, class_id = "car", 2
            elif area_ratio > 0.006 and aspect < 1.4:
                label, class_id = "person", 0
            elif area_ratio > 0.003 and aspect > 1.0:
                label, class_id = "car", 2
            else:
                continue
            detections.append({
                "bbox": (x, y, bw, bh),
                "centroid": (cx, cy),
                "class_id": class_id,
                "label": label,
                "confidence": 0.5
            })
        return detections

    COLORS = {
        0: (255, 255, 0),    # person → yellow
        2: (0, 255, 255),    # car → cyan
        3: (0, 255, 0),      # motorcycle → green
        5: (0, 128, 255),    # bus → orange
        7: (0, 0, 255),      # truck → red
    }



    def get_jpeg(self, max_w=640):
        if self._jpeg_cache is not None:
            return self._jpeg_cache
        return None

    def _estimate_speed(self, obj_id, centroid, bbox=None, class_id=None):
        if not hasattr(self, '_prev_pos'):
            self._prev_pos = {}
        if not hasattr(self, '_prev_time'):
            self._prev_time = {}
        if not hasattr(self, '_scale_history'):
            self._scale_history = {}
        now = time.time()
        if obj_id in self._prev_pos and obj_id in self._prev_time:
            bbox_x, bbox_y, bbox_w, bbox_h = bbox if bbox else (0, 0, 0, 0)
            # Usa il punto inferiore del bbox (contatto con strada) invece del centroide
            bottom_x = centroid[0]
            bottom_y = bbox_y + bbox_h
            prev_bottom_y = self._prev_pos[obj_id][2] if len(self._prev_pos[obj_id]) > 2 else bottom_y
            # Movimento verticale (lungo la strada) — più rilevante della distanza euclidea
            dy = bottom_y - prev_bottom_y
            dt = now - self._prev_time[obj_id]
            if dt > 0 and abs(dy) > 0.5 and bbox and bbox_h > 8:
                ref_h = REF_HEIGHT.get(class_id, 1.5)
                scale = ref_h / bbox_h
                if obj_id not in self._scale_history:
                    self._scale_history[obj_id] = scale
                else:
                    self._scale_history[obj_id] = self._scale_history[obj_id] * 0.7 + scale * 0.3
                smooth_scale = self._scale_history[obj_id]
                speed_kmh = (abs(dy) * smooth_scale / dt) * 3.6 * SPEED_CALIBRATION
                min_sp = 2 if class_id in VEHICLE_IDS else 1
                speed_kmh = max(min_sp, min(speed_kmh, 200))
                if obj_id in self.object_speeds:
                    speed_kmh = self.object_speeds[obj_id] * 0.6 + speed_kmh * 0.4
                self.object_speeds[obj_id] = speed_kmh
                obj_type = COCO_CLASSES.get(class_id, "vehicle")
                self.speed_samples.append({"type": obj_type, "speed": speed_kmh, "ts": datetime.now().isoformat()})
                if len(self.speed_samples) > 500:
                    self.speed_samples = self.speed_samples[-500:]
                return speed_kmh
        self._prev_pos[obj_id] = centroid + (bbox[1] + bbox[3],) if bbox else centroid + (0,)
        self._prev_time[obj_id] = now
        return None

    def _flush_hour(self, hour):
        try:
            # SALVA DELTA (differenza dall'ultimo flush), non cumulativo
            delta_cars = self.car_count - self._last_flushed_cars
            delta_people = self.people_count - self._last_flushed_people
            delta_trucks = self.truck_count - self._last_flushed_trucks
            delta_buses = self.bus_count - self._last_flushed_buses
            delta_motos = self.moto_count - self._last_flushed_motos
            delta_vehicles = delta_cars + delta_trucks + delta_buses + delta_motos
            conn = _db()
            conn.execute(
                "INSERT INTO counts (ts, hour, stream_url, cars, people, vehicles) VALUES (?,?,?,?,?,?)",
                (datetime.now().isoformat(), hour, self.stream_url or "unknown",
                 delta_cars, delta_people, delta_vehicles))
            conn.commit()
            conn.close()
            self._last_flushed_cars = self.car_count
            self._last_flushed_people = self.people_count
            self._last_flushed_trucks = self.truck_count
            self._last_flushed_buses = self.bus_count
            self._last_flushed_motos = self.moto_count
        except Exception as e:
            print(f"[VIDEO] Flush error: {e}")

    def _capture_loop(self):
        try:
            self.cap = cv2.VideoCapture(self.stream_url if self.stream_url else 0)
            fps_start = time.time()
            fps_frames = 0
            while self.running:
                if not self.cap or not self.cap.isOpened():
                    print("[VIDEO] Camera disconnected, reconnecting...")
                    time.sleep(2)
                    self.cap = cv2.VideoCapture(self.stream_url if self.stream_url else 0)
                    continue
                ret, frame = self.cap.read()
                if not ret:
                    print("[VIDEO] Stream ended, reconnecting...")
                    time.sleep(2)
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.stream_url if self.stream_url else 0)
                    continue

                fps_frames += 1
                if fps_frames >= 30:
                    elapsed = time.time() - fps_start
                    self.fps = fps_frames / elapsed if elapsed > 0 else 0
                    fps_start = time.time()
                    fps_frames = 0

                h, w = frame.shape[:2]
                if self.detection_line_y is None:
                    self.detection_line_y = int(h * 0.55)
                line_y = self.detection_line_y

                # YOLO ogni N frame su versione scalata
                self._frame_skip_counter += 1
                run_detection = self._frame_skip_counter % self._yolo_every == 0
                if run_detection and self.model_loaded:
                    detect_h = min(self._detect_h, h)
                    scale = detect_h / h
                    detect_w = int(w * scale)
                    if scale < 1:
                        small = cv2.resize(frame, (detect_w, detect_h), interpolation=cv2.INTER_LINEAR)
                    else:
                        small = frame
                    detections = self._detect_yolo(small)
                    if scale < 1:
                        for d in detections:
                            bx, by, bw, bh = d["bbox"]
                            cx, cy = d["centroid"]
                            d["bbox"] = (int(bx/scale), int(by/scale), int(bw/scale), int(bh/scale))
                            d["centroid"] = (int(cx/scale), int(cy/scale))
                    self._last_detections = detections
                else:
                    detections = getattr(self, '_last_detections', [])

                # Riconversione veicoli grandi
                for d in detections:
                    if d["class_id"] == 2 and d["bbox"][2] > w * 0.25:
                        d["class_id"] = 7; d["label"] = "truck"
                    elif d["class_id"] == 2 and d["bbox"][2] * d["bbox"][3] > w * h * 0.08:
                        d["class_id"] = 7; d["label"] = "truck"

                # Tracking e conteggio
                tracker_objects = {}
                if detections:
                    tracked = self.tracker.update(detections)
                    for oid, (cx, cy) in tracked.items():
                        prev_y = self._prev_positions.get(oid, cy)
                        crossing = prev_y < line_y <= cy or prev_y > line_y >= cy
                        self._prev_positions[oid] = cy
                        if crossing and oid not in self.crossed_ids:
                            self.crossed_ids.add(oid)
                            info = self.tracker.objects.get(oid)
                            if info:
                                cid = info["class_id"]
                                if cid == 0: self.people_count += 1
                                elif cid == 2: self.car_count += 1
                                elif cid == 7: self.truck_count += 1
                                elif cid == 5: self.bus_count += 1
                                elif cid == 3: self.moto_count += 1
                        info = self.tracker.objects.get(oid)
                        if info and info["class_id"] in VEHICLE_IDS and self._frame_skip_counter % 2 == 0:
                            speed = self._estimate_speed(oid, (cx, cy), info["bbox"], info["class_id"])
                            tracker_objects[oid] = {"centroid": (cx, cy), "speed": speed}

                # Annotazioni
                ov = frame
                cv2.line(ov, (0, line_y), (w, line_y), (0, 255, 255), 2)
                if run_detection:
                    for d in detections:
                        x, y, bw, bh = d["bbox"]
                        cid = d["class_id"]
                        color = self.COLORS.get(cid, (255, 255, 255))
                        cv2.rectangle(ov, (x, y), (x + bw, y + bh), color, 1)
                        cv2.putText(ov, f"{d['label']} {d['confidence']:.2f}", (x, y-4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    for oid, info in tracker_objects.items():
                        if info.get("speed") and info.get("centroid"):
                            cv2.putText(ov, f"{info['speed']:.0f} km/h", (info['centroid'][0]+6, info['centroid'][1]),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255,255,255), 1)
                # HUD
                overlay = ov[0:96, 0:360]
                cv2.rectangle(overlay, (0,0), (360,96), (0,0,0), -1)
                cv2.addWeighted(overlay, 0.6, overlay, 0.0, 0, overlay)
                y0 = 14
                cv2.putText(ov, "JARVIS", (8,y0), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,255), 1)
                cv2.putText(ov, f"FPS:{self.fps:.1f}  FR:{self.frame_count}", (8,y0+16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200,200,200), 1)
                cv2.putText(ov, f"CAR:{self.car_count} TRK:{self.truck_count} BUS:{self.bus_count} MOTO:{self.moto_count}", (8,y0+32),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200,200,200), 1)
                cv2.putText(ov, f"PPL:{self.people_count}  x:{len(self.crossed_ids)}", (8,y0+48),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200,200,200), 1)
                if self.speed_samples:
                    avg_s = sum(s["speed"] for s in self.speed_samples[-30:]) / min(len(self.speed_samples), 30)
                    cv2.putText(ov, f"AVG SPD:{avg_s:.0f} km/h", (8,y0+64),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0,255,255), 1)

                # JPEG encode e cache
                ret_jpg, buf = cv2.imencode(".jpg", ov, [cv2.IMWRITE_JPEG_QUALITY, 50])
                if ret_jpg:
                    self._jpeg_cache = buf.tobytes()

                self.frame_count += 1

                # Flush ogni 60s
                now = datetime.now()
                current_hour = now.strftime("%Y-%m-%d %H:00")
                if current_hour != self.last_hour:
                    if self.last_hour is not None:
                        self._flush_hour(self.last_hour)
                    self.last_hour = current_hour
                elif time.time() - self._last_flush_time > 60 and (self.car_count > 0 or self.people_count > 0):
                    self._flush_hour(current_hour)
                    self._last_flush_time = time.time()
        except Exception as e:
            print(f"[VIDEO] Capture error: {e}")
            traceback.print_exc()
            self.running = False
        finally:
            if self.cap:
                self.cap.release()
            if self.last_hour:
                self._flush_hour(self.last_hour)

    def start(self, stream_url=None):
        if self.running:
            return "Already running"
        if stream_url:
            self.stream_url = stream_url
        if not self.stream_url and not stream_url:
            return "No stream URL provided"
        self.running = True
        self.people_count = 0
        self.car_count = 0
        self.truck_count = 0
        self.bus_count = 0
        self.moto_count = 0
        self.frame_count = 0
        self._last_flushed_cars = 0
        self._last_flushed_people = 0
        self._last_flush_time = time.time()
        self.crossed_ids.clear()
        self._prev_positions.clear()
        self.tracker = IouTracker(max_disappeared=30, iou_threshold=0.15)
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        return f"Analisi avviata su {self.stream_url or 'webcam 0'}"

    def stop(self):
        if not self.running:
            return "Not running"
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.last_hour:
            self._flush_hour(self.last_hour)
        return "Analisi fermata"

    def get_counts(self, hours=1):
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        try:
            conn = _db()
            cur = conn.execute(
                "SELECT SUM(cars), SUM(people), SUM(vehicles), COUNT(*) FROM counts WHERE ts >= ?",
                (since,))
            row = cur.fetchone()
            conn.close()
            cars = row[0] or 0
            people = row[1] or 0
            vehicles = row[2] or 0
            intervals = row[3] or 0
            # Aggiungi conteggi di sessione non ancora salvati nel DB
            session_cars = self.car_count - self._last_flushed_cars
            session_people = self.people_count - self._last_flushed_people
            session_trucks = self.truck_count - self._last_flushed_trucks
            session_buses = self.bus_count - self._last_flushed_buses
            session_motos = self.moto_count - self._last_flushed_motos
            session_vehicles = session_cars + session_trucks + session_buses + session_motos
            cars += session_cars
            people += session_people
            vehicles += session_vehicles
            avg_speed = 0
            if self.speed_samples:
                speeds = [s["speed"] for s in self.speed_samples
                         if s["ts"] >= since]
                if speeds:
                    avg_speed = sum(speeds) / len(speeds)
            return {
                "cars": cars,
                "people": people,
                "vehicles": vehicles,
                "intervals": intervals,
                "avg_speed_kmh": round(avg_speed, 1),
                "since": since,
                "hours": hours
            }
        except Exception as e:
            return {"error": str(e)}

    def get_status(self):
        latest_spd = 0
        if self.speed_samples:
            latest_spd = round(self.speed_samples[-1]["speed"], 1)
        avg_spd = 0
        if self.speed_samples:
            recent = self.speed_samples[-30:]
            avg_spd = round(sum(s["speed"] for s in recent) / len(recent), 1)
        return {
            "running": self.running,
            "stream_url": self.stream_url or "N/A",
            "fps": round(self.fps, 1) if self.fps else 0,
            "frames_processed": self.frame_count,
            "people_count_session": self.people_count,
            "car_count_session": self.car_count,
            "truck_count_session": self.truck_count,
            "bus_count_session": self.bus_count,
            "moto_count_session": self.moto_count,
            "model": "YOLOv4-tiny" if self.model_loaded else "MOG2 fallback",
            "detection_line": self.detection_line_y,
            "latest_speed_kmh": latest_spd,
            "avg_speed_kmh": avg_spd
        }

    def set_detection_line(self, y_pct=0.7):
        self.detection_line_y = y_pct
        return f"Detection line set to {y_pct*100:.0f}% from top"

    def reset_history(self):
        self.people_count = 0
        self.car_count = 0
        self.truck_count = 0
        self.bus_count = 0
        self.moto_count = 0
        self.frame_count = 0
        self._last_flushed_cars = 0
        self._last_flushed_people = 0
        self._last_flushed_trucks = 0
        self._last_flushed_buses = 0
        self._last_flushed_motos = 0
        self._last_flush_time = time.time()
        self.speed_samples.clear()
        self.crossed_ids.clear()
        self._prev_positions.clear()
        self.object_speeds.clear()
        self._jpeg_cache = None
        self.tracker = IouTracker(max_disappeared=60, iou_threshold=0.1)
        if hasattr(self, '_prev_pos'): self._prev_pos.clear()
        if hasattr(self, '_prev_time'): self._prev_time.clear()
        try:
            conn = _db()
            conn.execute("DELETE FROM counts")
            conn.execute("DELETE FROM speed_samples")
            conn.commit()
            conn.close()
            return "Storico azzerato (db + memoria)"
        except Exception as e:
            return f"Errore reset: {e}"


# ── Singleton manager ──
def get_analytics(name="default"):
    with _lock:
        if name not in _instances:
            _instances[name] = VideoAnalytics()
        return _instances[name]

def start_analytics(stream_url="", name="default"):
    a = get_analytics(name)
    if not stream_url:
        stream_url = DEFAULT_RTSP
    return a.start(stream_url)

def stop_analytics(name="default"):
    a = get_analytics(name)
    return a.stop()

def get_counts(hours=1, name="default"):
    a = get_analytics(name)
    return a.get_counts(hours)

def get_status(name="default"):
    a = get_analytics(name)
    return a.get_status()

def set_detection_line(y_pct=0.7, name="default"):
    a = get_analytics(name)
    return a.set_detection_line(y_pct)

def reset_history(name="default"):
    a = get_analytics(name)
    return a.reset_history()

def set_calibration(value=1.0, name="default"):
    global SPEED_CALIBRATION
    SPEED_CALIBRATION = max(0.1, min(10.0, value))
    return f"Calibrazione velocità impostata a {SPEED_CALIBRATION}"


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else None
    a = VideoAnalytics(url)
    if url:
        print(a.start())
        try:
            while True:
                time.sleep(10)
                s = a.get_status()
                c = a.get_counts(1)
                print(f"  Frame {s['frames_processed']} | Cars: {c['cars']} | People: {c['people']} | FPS: {s['fps']}")
        except KeyboardInterrupt:
            print(a.stop())
    else:
        print("Usage: python3 jarvis_video_analytics.py <stream_url>")
        print("  or:   python3 jarvis_video_analytics.py 0  (for webcam)")
