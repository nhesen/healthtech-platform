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
    peak_index = counts.index(peak) if frames else 0
    peak_frame = frames[peak_index] if frames else {}
    empty_seats = int(peak_frame.get("empty_seat_count") or 0)
    seats_detected = int(peak_frame.get("seat_count") or 0)
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
    empty_text = (
        f" Empty seats: {empty_seats} of {seats_detected} detected chairs/benches."
        if seats_detected else
        " No chairs or benches were detected, so empty-seat count is 0."
    )
    return {
        "frames_analyzed": len(frames),
        "peak_people": peak,
        "average_people": average,
        "empty_seats": empty_seats,
        "seats_detected": seats_detected,
        "latest_people": frames[-1]["people"] if frames else [],
        "crowding": {
            "level": level,
            "peak_people": peak,
            "average_people": average,
            "empty_seats": empty_seats,
            "seats_detected": seats_detected,
            "explanation": (
                f"YOLO counted a peak of {peak} people in the sampled frames. "
                f"Density is {level.lower().replace('_', ' ')}.{empty_text} "
                "This is occupancy decision support, not a diagnosis."
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
    name = str(item.get("label") or "person")
    if name == "empty":
        return "empty"
    score = float(item.get("confidence") or 0)
    return f"{name} {int(round(score * 100))}%"


def _filled_rounded_rect(image: Any, x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], radius: int) -> None:
    import cv2
    if x2 <= x1 or y2 <= y1:
        return
    radius = int(max(2, min(radius, (x2 - x1) // 3, (y2 - y1) // 3)))
    cv2.rectangle(image, (x1 + radius, y1), (x2 - radius, y2), color, -1)
    cv2.rectangle(image, (x1, y1 + radius), (x2, y2 - radius), color, -1)
    for cx, cy in ((x1 + radius, y1 + radius), (x2 - radius, y1 + radius), (x1 + radius, y2 - radius), (x2 - radius, y2 - radius)):
        cv2.circle(image, (cx, cy), radius, color, -1)


def _rounded_rect_border(image: Any, x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], radius: int, thickness: int = 2) -> None:
    import cv2
    if x2 <= x1 or y2 <= y1:
        return
    radius = int(max(2, min(radius, (x2 - x1) // 3, (y2 - y1) // 3)))
    cv2.line(image, (x1 + radius, y1), (x2 - radius, y1), color, thickness, cv2.LINE_AA)
    cv2.line(image, (x1 + radius, y2), (x2 - radius, y2), color, thickness, cv2.LINE_AA)
    cv2.line(image, (x1, y1 + radius), (x1, y2 - radius), color, thickness, cv2.LINE_AA)
    cv2.line(image, (x2, y1 + radius), (x2, y2 - radius), color, thickness, cv2.LINE_AA)
    cv2.ellipse(image, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(image, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(image, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness, cv2.LINE_AA)
    cv2.ellipse(image, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness, cv2.LINE_AA)


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

    seats = [item for item in (objects or []) if item.get("box") and len(item.get("box") or []) >= 4]
    fill = frame.copy()
    mint = (96, 188, 72)
    mint_edge = (48, 150, 42)
    for item in seats:
        x1, y1, x2, y2 = scaled_box(item["box"])
        radius = max(6, min(x2 - x1, y2 - y1) // 5)
        _filled_rounded_rect(fill, x1, y1, x2, y2, mint, radius)
    if seats:
        cv2.addWeighted(fill, 0.38, frame, 0.62, 0, frame)
    for item in seats:
        x1, y1, x2, y2 = scaled_box(item["box"])
        radius = max(6, min(x2 - x1, y2 - y1) // 5)
        _rounded_rect_border(frame, x1, y1, x2, y2, mint_edge, radius, 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    person_scale = max(0.55, min(width, height) / 980)
    red = (0, 0, 255)
    for item in people:
        box = item.get("box")
        if not box or len(box) < 4:
            continue
        x1, y1, x2, y2 = scaled_box(box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), red, 2)
        text = detection_label(item)
        (_text_w, text_h), _ = cv2.getTextSize(text, font, person_scale, 2)
        text_y = y1 - 8 if y1 - text_h - 10 > 0 else y1 + text_h + 8
        cv2.putText(frame, text, (x1, text_y), font, person_scale, red, 2, cv2.LINE_AA)
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not ok:
        return None
    return {"mime": "image/jpeg", "base64": base64.b64encode(buffer.tobytes()).decode("ascii")}
