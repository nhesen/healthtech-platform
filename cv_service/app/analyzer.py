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
                f"YOLO Pose counted a peak of {peak} people in the sampled frames. "
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


def render_occupancy_overlay(image_bgr: Any, people: list[dict[str, Any]]) -> dict[str, str] | None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
        return None
    frame = image_bgr.copy()
    height, width = frame.shape[:2]
    max_width = 1280
    if width > max_width:
        scale = max_width / width
        frame = cv2.resize(frame, (max_width, int(height * scale)))
        height, width = frame.shape[:2]
        scaled = []
        for person in people:
            item = dict(person)
            if item.get("center"):
                item["center"] = [item["center"][0] * scale, item["center"][1] * scale]
            if item.get("box"):
                item["box"] = [value * scale for value in item["box"]]
            scaled.append(item)
        people = scaled
    overlay = frame.copy()
    cols, rows = 8, 6
    cell_w, cell_h = width / cols, height / rows
    counts = occupancy_grid(width, height, people, cols, rows)
    for row in range(rows):
        for col in range(cols):
            count = counts[row][col]
            color = cell_color(count)
            alpha = 0.22 if count == 0 else 0.38 if count == 1 else 0.52
            x1, y1 = int(col * cell_w), int(row * cell_h)
            x2, y2 = int((col + 1) * cell_w), int((row + 1) * cell_h)
            roi = overlay[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            tint = np.full_like(roi, color)
            overlay[y1:y2, x1:x2] = cv2.addWeighted(roi, 1 - alpha, tint, alpha, 0)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 1)
    for person in people:
        box = person.get("box")
        if box and len(box) >= 4:
            x1, y1, x2, y2 = [int(value) for value in box]
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (40, 40, 220), 2)
            label = str(person.get("state") or "PERSON")
            cv2.putText(overlay, label, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 220), 2, cv2.LINE_AA)
        elif person.get("center"):
            cx, cy = int(person["center"][0]), int(person["center"][1])
            cv2.circle(overlay, (cx, cy), 10, (40, 40, 220), 2)
    cv2.rectangle(overlay, (8, 8), (268, 78), (0, 0, 0), -1)
    cv2.putText(overlay, "EMPTY / BOS", (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (46, 180, 70), 2, cv2.LINE_AA)
    cv2.putText(overlay, "OCCUPIED / DOLU", (16, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 220), 2, cv2.LINE_AA)
    ok, buffer = cv2.imencode(".jpg", overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return None
    return {"mime": "image/jpeg", "base64": base64.b64encode(buffer.tobytes()).decode("ascii")}
