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
    people = []
    for index, person in enumerate(xy):
        confs = raw_conf[index] if raw_conf and index < len(raw_conf) else [1.0] * len(person)
        points = [[pair[0], pair[1], confs[j] if j < len(confs) else 0.0] for j, pair in enumerate(person)]
        state, confidence = classify_keypoints(points)
        people.append({"index": index, "state": state, "confidence": round(float(confidence), 3)})
    return people


class PoseDetector:
    def __init__(self, model_name: str | None = None):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install cv_service/requirements-vision.txt for YOLO video mode") from exc
        self.device = os.getenv("CV_DEVICE", "cpu")
        self.model = YOLO(model_name or os.getenv("CV_MODEL") or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt"))

    def states(self, source: str | int, frame_skip: int = 2) -> Iterator[tuple[str, float]]:
        for index, result in enumerate(self.model.predict(source=source, stream=True, verbose=False, device=self.device)):
            if index % max(1, frame_skip):
                continue
            people = people_from_result(result)
            if not people:
                yield "UNKNOWN", 0.0
                continue
            lead = max(people, key=lambda item: item["confidence"])
            yield lead["state"], lead["confidence"]

    def analyze(self, source: str, frame_skip: int = 2, max_frames: int = 40) -> list[dict]:
        frames = []
        for index, result in enumerate(self.model.predict(source=source, stream=True, verbose=False, save=False, device=self.device)):
            if index % max(1, frame_skip):
                continue
            people = people_from_result(result)
            frames.append({"index": index, "person_count": len(people), "people": people})
            if len(frames) >= max_frames:
                break
        return frames
