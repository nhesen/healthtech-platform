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


def people_from_detect(result: Any, min_conf: float = 0.15) -> list[dict[str, Any]]:
    if result.boxes is None or getattr(result.boxes, "xyxy", None) is None:
        return []
    xyxy = result.boxes.xyxy.cpu().tolist()
    if not xyxy:
        return []
    confs = result.boxes.conf.cpu().tolist() if result.boxes.conf is not None else [1.0] * len(xyxy)
    classes = result.boxes.cls.cpu().tolist() if result.boxes.cls is not None else [0] * len(xyxy)
    names = result.names or {}
    people = []
    for index, box in enumerate(xyxy):
        cls_id = int(classes[index])
        if isinstance(names, dict):
            name = names.get(cls_id, "person")
        elif isinstance(names, (list, tuple)) and 0 <= cls_id < len(names):
            name = names[cls_id]
        else:
            name = "person"
        if str(name).lower() != "person":
            continue
        score = float(confs[index] if index < len(confs) else 0)
        if score < min_conf:
            continue
        center = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
        people.append({
            "index": len(people),
            "label": "person",
            "state": "UNKNOWN",
            "confidence": round(score, 3),
            "box": [round(float(value), 1) for value in box],
            "center": [round(float(center[0]), 1), round(float(center[1]), 1)],
        })
    return people


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
        self.device = os.getenv("CV_DEVICE", "cpu")
        self.imgsz = int(os.getenv("CV_IMGSZ", "960"))
        self.conf = float(os.getenv("CV_CONF", "0.15"))
        self.pose = YOLO(model_name or os.getenv("CV_MODEL") or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt"))
        self.detect = YOLO(os.getenv("CV_DETECT_MODEL", "yolo11n.pt"))
        self.model = self.pose

    def _kwargs(self) -> dict:
        return {"verbose": False, "save": False, "device": self.device, "imgsz": self.imgsz, "conf": self.conf, "iou": 0.45}

    def states(self, source: str | int, frame_skip: int = 2) -> Iterator[tuple[str, float]]:
        for index, result in enumerate(self.pose.predict(source=source, stream=True, **self._kwargs())):
            if index % max(1, frame_skip):
                continue
            people = people_from_result(result)
            if not people:
                yield "UNKNOWN", 0.0
                continue
            lead = max(people, key=lambda item: item["confidence"])
            yield lead["state"], lead["confidence"]

    def analyze(self, source: str, frame_skip: int = 2, max_frames: int = 40) -> tuple[list[dict], tuple[Any, list[dict]] | None]:
        skip = 1 if str(source).lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")) else max(1, frame_skip)
        frames = []
        preview = None
        best = -1
        for index, result in enumerate(self.detect.predict(source=source, stream=True, **self._kwargs())):
            if index % skip:
                continue
            people = people_from_detect(result, self.conf)
            if result.orig_img is not None:
                posed = people_from_result(self.pose.predict(source=result.orig_img, **self._kwargs())[0])
                people = merge_pose_into_detect(people, posed)
            frames.append({"index": index, "person_count": len(people), "people": people})
            if result.orig_img is not None and len(people) >= best:
                preview = (result.orig_img.copy(), people)
                best = len(people)
            if len(frames) >= max_frames:
                break
        return frames, preview
