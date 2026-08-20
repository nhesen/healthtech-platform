"""Scene occupancy helpers. YOLO Pose only; no face or identity recognition."""
from __future__ import annotations

import base64
from typing import Any


def crowding_level(person_count: int) -> str:
    if person_count <= 0:
        return "EMPTY"
    if person_count <= 2:
        return "LOW"
    if person_count <= 4:
        return "MODERATE"
    if person_count <= 7:
        return "BUSY"
    return "OVERCROWDED"


def majority_pose(people: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for person in people:
        state = person.get("state")
        if state in {"STANDING", "SITTING", "LYING"}:
            counts[state] = counts.get(state, 0) + 1
    if not counts:
        return "UNKNOWN"
    return max(counts, key=counts.get)


def occupancy_grid(width: int, height: int, people: list[dict[str, Any]], cols: int = 8, rows: int = 6) -> list[list[int]]:
    cells = [[0] * cols for _ in range(rows)]
    if width <= 0 or height <= 0:
        return cells
    for person in people:
        center = person.get("center")
        if not center or len(center) < 2:
            continue
        col = min(cols - 1, max(0, int(center[0] / width * cols)))
        row = min(rows - 1, max(0, int(center[1] / height * rows)))
        cells[row][col] += 1
    return cells


def cell_color(count: int) -> tuple[int, int, int]:
    """OpenCV BGR: empty green, sparse amber, crowded red."""
    if count <= 0:
        return (46, 180, 70)
    if count == 1:
        return (0, 165, 255)
    return (40, 40, 220)


def summarize_frames(frames: list[dict[str, Any]]) -> dict[str, Any]:
    counts = [item["person_count"] for item in frames] or [0]
    peak = max(counts)
    average = round(sum(counts) / len(counts), 2)
    pose_counts: dict[str, int] = {}
    transitions: list[str] = []
    previous_majority = None
    for item in frames:
        for person in item.get("people") or []:
            pose_counts[person["state"]] = pose_counts.get(person["state"], 0) + 1
        majority = majority_pose(item.get("people") or [])
        if previous_majority and majority != "UNKNOWN" and majority != previous_majority:
            transitions.append(f"{previous_majority}->{majority}")
        if majority != "UNKNOWN":
            previous_majority = majority
    fall_risk = any(item in {"SITTING->STANDING", "LYING->STANDING"} for item in transitions)
    incoming = len(counts) > 1 and counts[-1] > counts[0]
    level = crowding_level(peak)
    return {
        "frames_analyzed": len(frames),
        "peak_people": peak,
        "average_people": average,
        "latest_people": frames[-1]["people"] if frames else [],
        "crowding": {
            "level": level,
            "peak_people": peak,
            "average_people": average,
            "explanation": (
                f"YOLO counted a peak of {peak} people in the sampled frames. "
                f"Density is {level.lower().replace('_', ' ')}. This is occupancy decision support, not a diagnosis."
            ),
        },
        "movement": {
            "pose_counts": pose_counts,
            "transitions": transitions,
            "incoming_people": incoming,
            "fall_risk_signal": fall_risk,
            "explanation": (
                "Pose transitions were observed across sampled frames."
                if transitions else
                "No stable pose transition was observed in the sampled frames."
            ),
        },
    }


def detection_label(item: dict[str, Any]) -> str:
    score = float(item.get("confidence") or 0)
    name = str(item.get("label") or "person")
    return f"{name} {int(round(score * 100))}%"


def render_occupancy_overlay(image_bgr: Any, people: list[dict[str, Any]], objects: list[dict[str, Any]] | None = None) -> dict[str, str] | None:
    try:
        import cv2
    except ImportError:
        return None
    if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
        return None
    frame = image_bgr.copy()
    height, width = frame.shape[:2]
    max_width = 1280
    scale = 1.0
    if width > max_width:
        scale = max_width / width
        frame = cv2.resize(frame, (max_width, int(height * scale)))
        height, width = frame.shape[:2]

    def scaled_box(box: list[float]) -> list[int]:
        return [int(value * scale) for value in box]

    red = (0, 0, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.55, min(width, height) / 980)
    thickness = 2
    detections = list(people) + list(objects or [])
    for item in detections:
        box = item.get("box")
        if not box or len(box) < 4:
            continue
        x1, y1, x2, y2 = scaled_box(box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), red, 2)
        text = detection_label(item)
        (_text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        text_y = y1 - 8 if y1 - text_h - 10 > 0 else y1 + text_h + 8
        cv2.putText(frame, text, (x1, text_y), font, font_scale, red, thickness, cv2.LINE_AA)
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not ok:
        return None
    return {"mime": "image/jpeg", "base64": base64.b64encode(buffer.tobytes()).decode("ascii")}
