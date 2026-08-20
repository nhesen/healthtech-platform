"""Scene occupancy helpers. YOLO Pose only; no face or identity recognition."""
from __future__ import annotations

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
