"""Analyze one image or video with YOLO Pose and write JSON. No identity recognition."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    os.environ.setdefault("YOLO_VERBOSE", "False")
    if len(sys.argv) < 3:
        print("usage: analyze_cli.py SOURCE RESULT.json", file=sys.stderr)
        return 2
    source, dest = Path(sys.argv[1]), Path(sys.argv[2])
    payload = {"yolo_active": False, "identity_recognition": False, "frames_discarded": True}
    try:
        from app.detector import PoseDetector
        from app.analyzer import render_occupancy_overlay, summarize_frames
        detector = PoseDetector()
        frames, preview = detector.analyze(str(source))
        payload = summarize_frames(frames)
        overlay = None
        if preview:
            overlay = render_occupancy_overlay(*preview)
        payload.update({
            "yolo_active": True,
            "engine": "ultralytics-yolo-pose",
            "model": os.getenv("CV_MODEL") or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt"),
            "device": os.getenv("CV_DEVICE", "cpu"),
            "identity_recognition": False,
            "frames_discarded": True,
            "overlay_image": overlay,
        })
        dest.write_text(json.dumps(payload), encoding="utf-8")
        return 0
    except Exception as exc:
        payload["error"] = str(exc)
        dest.write_text(json.dumps(payload), encoding="utf-8")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
