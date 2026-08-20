"""Optional YOLO Pose adapter. No face or identity recognition is performed."""
from __future__ import annotations

from collections.abc import Iterator
import os
from typing import Any


def classify_keypoints(points: list[list[float]]) -> tuple[str, float]:
    """Classify a COCO pose from x/y/confidence keypoints using explainable geometry."""
    needed = [5, 6, 11, 12]
    if len(points) < 17 or any(points[i][2] < .35 for i in needed):
        return "UNKNOWN", 0.0
    shoulder = ((points[5][0] + points[6][0]) / 2, (points[5][1] + points[6][1]) / 2)
    hip = ((points[11][0] + points[12][0]) / 2, (points[11][1] + points[12][1]) / 2)
    torso_dx = abs(hip[0] - shoulder[0])
    torso_dy = abs(hip[1] - shoulder[1])
    base = min(points[i][2] for i in needed)
    if torso_dx > torso_dy * 1.2:
        return "LYING", base
    legs = [i for i in (13, 14, 15, 16) if points[i][2] >= .35]
    if len(legs) < 2:
        return "UNKNOWN", base * .7
    knee_y = sum(points[i][1] for i in (13, 14)) / 2
    ankle_y = sum(points[i][1] for i in (15, 16)) / 2
    if ankle_y - knee_y > torso_dy * .55 and knee_y - hip[1] > torso_dy * .45:
        return "STANDING", base
    if abs(knee_y - hip[1]) < torso_dy * .75:
        return "SITTING", base
    return "UNKNOWN", base * .7


def people_from_result(result: Any) -> list[dict[str, Any]]:
    if result.keypoints is None or getattr(result.keypoints, "xy", None) is None:
        return []
    xy = result.keypoints.xy.cpu().tolist()
    if not xy:
        return []
    raw_conf = result.keypoints.conf.cpu().tolist() if result.keypoints.conf is not None else None
    boxes = []
    box_confs = []
    if result.boxes is not None:
        if getattr(result.boxes, "xyxy", None) is not None:
            boxes = result.boxes.xyxy.cpu().tolist()
        if getattr(result.boxes, "conf", None) is not None:
            box_confs = result.boxes.conf.cpu().tolist()
    people = []
    for index, person in enumerate(xy):
        confs = raw_conf[index] if raw_conf and index < len(raw_conf) else [1.0] * len(person)
        points = [[pair[0], pair[1], confs[j] if j < len(confs) else 0.0] for j, pair in enumerate(person)]
        state, confidence = classify_keypoints(points)
        box = boxes[index] if index < len(boxes) else _box_from_points(points)
        center = _person_center(points, box)
        score = box_confs[index] if index < len(box_confs) else confidence
        item = {"index": index, "state": state, "confidence": round(float(score if score else confidence), 3), "label": "person"}
        if box:
            item["box"] = [round(float(value), 1) for value in box]
        if center:
            item["center"] = [round(float(center[0]), 1), round(float(center[1]), 1)]
        people.append(item)
    return people


def _box_from_points(points: list[list[float]]) -> list[float] | None:
    visible = [point for point in points if len(point) >= 3 and point[2] >= 0.35]
    if len(visible) < 4:
        return None
    xs = [point[0] for point in visible]
    ys = [point[1] for point in visible]
    pad = 12
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


def _person_center(points: list[list[float]], box: list[float] | None) -> list[float] | None:
    if len(points) >= 13 and points[11][2] >= 0.35 and points[12][2] >= 0.35:
        return [(points[11][0] + points[12][0]) / 2, (points[11][1] + points[12][1]) / 2]
    if box and len(box) >= 4:
        return [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
    visible = [point for point in points if len(point) >= 3 and point[2] >= 0.35]
    if visible:
        return [sum(point[0] for point in visible) / len(visible), sum(point[1] for point in visible) / len(visible)]
    return None


SEAT_LABELS = {"chair", "bench", "couch"}
OCCUPANCY_CLASSES = [0, 13, 56, 57]


def detections_from_result(result: Any, labels: set[str] | None = None, min_conf: float = 0.15) -> list[dict[str, Any]]:
    if result.boxes is None or getattr(result.boxes, "xyxy", None) is None:
        return []
    xyxy = result.boxes.xyxy.cpu().tolist()
    if not xyxy:
        return []
    confs = result.boxes.conf.cpu().tolist() if result.boxes.conf is not None else [1.0] * len(xyxy)
    classes = result.boxes.cls.cpu().tolist() if result.boxes.cls is not None else [0] * len(xyxy)
    names = result.names or {}
    items = []
    for index, box in enumerate(xyxy):
        cls_id = int(classes[index])
        if isinstance(names, dict):
            name = str(names.get(cls_id, "object"))
        elif isinstance(names, (list, tuple)) and 0 <= cls_id < len(names):
            name = str(names[cls_id])
        else:
            name = "object"
        label = name.lower()
        if labels is not None and label not in labels:
            continue
        score = float(confs[index] if index < len(confs) else 0)
        if score < min_conf:
            continue
        center = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
        items.append({
            "index": len(items),
            "label": label,
            "state": "UNKNOWN" if label == "person" else "EMPTY",
            "confidence": round(score, 3),
            "box": [round(float(value), 1) for value in box],
            "center": [round(float(center[0]), 1), round(float(center[1]), 1)],
        })
    return items


def people_from_detect(result: Any, min_conf: float = 0.15) -> list[dict[str, Any]]:
    return detections_from_result(result, {"person"}, min_conf)


def seats_from_detect(result: Any, min_conf: float = 0.12) -> list[dict[str, Any]]:
    return detections_from_result(result, SEAT_LABELS, min_conf)


def _box(item: dict[str, Any]) -> list[float] | None:
    box = item.get("box")
    if not box or len(box) < 4:
        return None
    return [float(box[0]), float(box[1]), float(box[2]), float(box[3])]


def typical_person_size(people: list[dict[str, Any]], image_size: tuple[int, int]) -> tuple[float, float]:
    widths = []
    heights = []
    for person in people:
        box = _box(person)
        if not box:
            continue
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    if widths:
        widths.sort()
        heights.sort()
        mid = len(widths) // 2
        return max(widths[mid], 8.0), max(heights[mid], 8.0)
    width, height = image_size if image_size[0] > 0 else (1280, 720)
    return width * 0.08, height * 0.28


def nms_detections(items: list[dict[str, Any]], iou_thresh: float = 0.4) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: float(item.get("confidence") or 0), reverse=True)
    kept: list[dict[str, Any]] = []
    for item in ordered:
        box = _box(item)
        if not box:
            continue
        if any(box_iou(box, other["box"]) >= iou_thresh for other in kept if other.get("box")):
            continue
        kept.append(item)
    return kept


def filter_furniture_boxes(
    seats: list[dict[str, Any]],
    people: list[dict[str, Any]],
    image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    width, height = image_size if image_size[0] > 0 else (1, 1)
    person_w, person_h = typical_person_size(people, (width, height))
    kept = []
    for item in seats:
        box = _box(item)
        if not box:
            continue
        bw, bh = box[2] - box[0], box[3] - box[1]
        if bw <= 1 or bh <= 1:
            continue
        cy = (box[1] + box[3]) / 2
        if height > 1 and cy < height * 0.16:
            continue
        if bw < person_w * 0.32 or bh < person_h * 0.18:
            continue
        if width * height > 1 and bw * bh > 0.55 * width * height:
            continue
        if bh > bw * 3.8:
            continue
        if float(item.get("confidence") or 0) < 0.2:
            continue
        kept.append(item)
    return kept


def seat_cushion_size(people: list[dict[str, Any]], image_size: tuple[int, int]) -> tuple[float, float]:
    width, height = image_size if image_size[0] > 0 else (1280, 720)
    person_w, _person_h = typical_person_size(people, (width, height))
    seat_w = min(max(person_w * 0.82, width * 0.045), width * 0.16)
    seat_h = min(max(seat_w * 0.58, height * 0.045), height * 0.12)
    return seat_w, seat_h


def _canonical_seat(center_x: float, bottom: float, seat_w: float, seat_h: float, confidence: float, image_size: tuple[int, int]) -> dict[str, Any]:
    width, height = image_size
    x1 = center_x - seat_w / 2
    x2 = center_x + seat_w / 2
    y2 = bottom
    y1 = bottom - seat_h
    box = [
        round(max(0.0, x1), 1),
        round(max(0.0, y1), 1),
        round(min(float(width - 1), x2), 1) if width > 1 else round(x2, 1),
        round(min(float(height - 1), y2), 1) if height > 1 else round(y2, 1),
    ]
    return {
        "label": "empty",
        "state": "EMPTY",
        "confidence": round(float(confidence), 3),
        "box": box,
        "center": [round((box[0] + box[2]) / 2, 1), round((box[1] + box[3]) / 2, 1)],
    }


def nms_by_center(items: list[dict[str, Any]], min_dist: float) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: float(item.get("confidence") or 0), reverse=True)
    kept: list[dict[str, Any]] = []
    for item in ordered:
        center = item.get("center")
        if not center:
            continue
        if any(((center[0] - other["center"][0]) ** 2 + (center[1] - other["center"][1]) ** 2) ** 0.5 < min_dist for other in kept):
            continue
        kept.append(item)
    return kept


def snap_seat_rows(items: list[dict[str, Any]], row_tol: float) -> list[dict[str, Any]]:
    if not items:
        return items
    rows: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda seat: seat["box"][3]):
        bottom = item["box"][3]
        matched = None
        for row in rows:
            if abs(row["y"] - bottom) <= row_tol:
                matched = row
                break
        if matched is None:
            rows.append({"y": bottom, "items": [item]})
            continue
        matched["items"].append(item)
        matched["y"] = sum(seat["box"][3] for seat in matched["items"]) / len(matched["items"])
    snapped = []
    for row in rows:
        for item in row["items"]:
            box = item["box"]
            height = box[3] - box[1]
            new_box = [box[0], round(row["y"] - height, 1), box[2], round(row["y"], 1)]
            snapped.append({
                **item,
                "box": new_box,
                "center": [round((new_box[0] + new_box[2]) / 2, 1), round((new_box[1] + new_box[3]) / 2, 1)],
            })
    return snapped


def sitting_slots_from_furniture(
    seats: list[dict[str, Any]],
    people: list[dict[str, Any]],
    image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    width, height = image_size if image_size and image_size[0] > 0 else (1280, 720)
    seat_w, seat_h = seat_cushion_size(people, (width, height))
    furniture = nms_detections(filter_furniture_boxes(seats, people, (width, height)), 0.45)
    frames: list[dict[str, Any]] = []
    for item in furniture:
        box = _box(item)
        if not box:
            continue
        bw, bh = box[2] - box[0], box[3] - box[1]
        label = str(item.get("label") or "chair")
        if label == "chair" and bw < seat_w * 1.85:
            count = 1
        else:
            count = max(1, min(8, int(round(bw / (seat_w * 1.15)))))
        inset = bw * 0.1 if count > 1 else 0.0
        left, right = box[0] + inset, box[2] - inset
        bottom = box[3] - bh * 0.08
        if count == 1:
            xs = [(box[0] + box[2]) / 2]
        else:
            span = max(right - left, seat_w)
            xs = [left + (index + 0.5) * span / count for index in range(count)]
        for center_x in xs:
            frames.append(_canonical_seat(center_x, bottom, seat_w, seat_h, float(item.get("confidence") or 0), (width, height)))
    aligned = snap_seat_rows(frames, seat_h * 0.75)
    cleaned = nms_by_center(aligned, seat_w * 0.62)
    for index, item in enumerate(cleaned):
        item["index"] = index
    return cleaned[:40]


def box_iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / area if area else 0.0


def person_occupies_seat(person: dict[str, Any], seat: dict[str, Any]) -> bool:
    pbox = person.get("box")
    sbox = seat.get("box")
    if not pbox or not sbox or len(pbox) < 4 or len(sbox) < 4:
        return False
    sit_x = (pbox[0] + pbox[2]) / 2
    sit_y = pbox[1] + 0.7 * (pbox[3] - pbox[1])
    pad_x = max(8.0, (sbox[2] - sbox[0]) * 0.18)
    pad_y = max(8.0, (sbox[3] - sbox[1]) * 0.22)
    if sbox[0] - pad_x <= sit_x <= sbox[2] + pad_x and sbox[1] - pad_y <= sit_y <= sbox[3] + pad_y:
        return True
    sit_region = [pbox[0], pbox[1] + 0.55 * (pbox[3] - pbox[1]), pbox[2], pbox[3]]
    return box_iou(sit_region, sbox) >= 0.12


def empty_seats_from_people(people: list[dict[str, Any]], seats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    empty = []
    for seat in seats:
        if any(person_occupies_seat(person, seat) for person in people):
            continue
        item = dict(seat)
        item["label"] = "empty"
        item["state"] = "EMPTY"
        empty.append(item)
    return empty


def merge_pose_into_detect(detected: list[dict[str, Any]], posed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not detected:
        return posed
    used: set[int] = set()
    merged = []
    for person in detected:
        item = dict(person)
        box = item.get("box")
        best_index, best = -1, 0.0
        if box:
            for index, pose in enumerate(posed):
                if index in used or not pose.get("box"):
                    continue
                score = box_iou(box, pose["box"])
                if score > best:
                    best, best_index = score, index
        if best_index >= 0 and best >= 0.25:
            used.add(best_index)
            pose = posed[best_index]
            if pose.get("state") and pose["state"] != "UNKNOWN":
                item["state"] = pose["state"]
        merged.append(item)
    return merged


class PoseDetector:
    def __init__(self, model_name: str | None = None):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install cv_service/requirements-vision.txt for YOLO video mode") from exc
        self._YOLO = YOLO
        self.device = os.getenv("CV_DEVICE", "cpu")
        self.imgsz = int(os.getenv("CV_IMGSZ", "1280"))
        self.conf = float(os.getenv("CV_CONF", "0.12"))
        self._pose_name = model_name or os.getenv("CV_MODEL") or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt")
        self._detect_name = os.getenv("CV_DETECT_MODEL", "yolo11s.pt")
        self._pose = None
        self._detect = None
        self.model = None

    @property
    def pose(self):
        if self._pose is None:
            self._pose = self._YOLO(self._pose_name)
            self.model = self._pose
        return self._pose

    @property
    def detect(self):
        if self._detect is None:
            self._detect = self._YOLO(self._detect_name)
        return self._detect

    def _kwargs(self, classes: list[int] | None = None) -> dict:
        return {
            "verbose": False,
            "save": False,
            "device": self.device,
            "imgsz": self.imgsz,
            "conf": self.conf,
            "iou": 0.6,
            "max_det": 300,
            "classes": classes if classes is not None else [0],
        }

    def states(self, source: str | int, frame_skip: int = 2) -> Iterator[tuple[str, float]]:
        for index, result in enumerate(self.pose.predict(source=source, stream=True, **self._kwargs([0]))):
            if index % max(1, frame_skip):
                continue
            people = people_from_result(result)
            if not people:
                yield "UNKNOWN", 0.0
                continue
            lead = max(people, key=lambda item: item["confidence"])
            yield lead["state"], lead["confidence"]

    def analyze(self, source: str, frame_skip: int = 2, max_frames: int = 8) -> tuple[list[dict], tuple[Any, list[dict]] | None]:
        is_image = str(source).lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp"))
        skip = 1 if is_image else max(2, frame_skip)
        frames = []
        preview = None
        best = -1
        for index, result in enumerate(self.detect.predict(source=source, stream=True, **self._kwargs(OCCUPANCY_CLASSES))):
            if index % skip:
                continue
            people = people_from_detect(result, self.conf)
            shape = getattr(result.orig_img, "shape", None)
            image_size = (int(shape[1]), int(shape[0])) if shape is not None and len(shape) >= 2 else (0, 0)
            seats = sitting_slots_from_furniture(
                seats_from_detect(result, max(self.conf, 0.2)),
                people,
                image_size,
            )
            if not is_image and result.orig_img is not None:
                posed = people_from_result(self.pose.predict(source=result.orig_img, **self._kwargs([0]))[0])
                people = merge_pose_into_detect(people, posed)
            empty = empty_seats_from_people(people, seats)
            frames.append({
                "index": index,
                "person_count": len(people),
                "people": people,
                "seat_count": len(seats),
                "empty_seat_count": len(empty),
                "empty_seats": empty,
            })
            if result.orig_img is not None and len(people) >= best:
                preview = (result.orig_img.copy(), people, empty)
                best = len(people)
            if len(frames) >= (1 if is_image else max_frames):
                break
        return frames, preview
