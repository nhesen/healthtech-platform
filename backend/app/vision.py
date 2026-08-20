"""Hospital vision upload: run YOLO Pose in a separate process, then discard the file."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException

CV_ROOT = Path(__file__).resolve().parents[2] / "cv_service"
ANALYZE_CLI = CV_ROOT / "analyze_cli.py"
MAX_VISION_BYTES = 25 * 1024 * 1024
ANALYZE_TIMEOUT_SECONDS = 180

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_WEBM = b"\x1aE\xdf\xa3"


def yolo_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except ImportError:
        return False


def vision_status() -> dict:
    active = yolo_available()
    model = os.getenv("CV_MODEL") or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt")
    return {
        "yolo_active": active,
        "engine": "ultralytics-yolo-pose" if active else None,
        "model": model if active else None,
        "device": os.getenv("CV_DEVICE", "cpu") if active else None,
        "identity_recognition": False,
        "frames_sent_to_api": False,
        "install_hint": None if active else "pip install -r cv_service/requirements-vision.txt",
    }


def sniff_media(data: bytes, content_type: str, filename: str) -> tuple[str, str]:
    ctype = (content_type or "").split(";")[0].strip().lower()
    name = (filename or "scene").lower()
    if data.startswith(_JPEG) or ctype == "image/jpeg" or name.endswith((".jpg", ".jpeg")):
        if data.startswith(_JPEG):
            return "image/jpeg", ".jpg"
    if data.startswith(_PNG) or ctype == "image/png" or name.endswith(".png"):
        if data.startswith(_PNG):
            return "image/png", ".png"
    if (len(data) > 12 and data[4:8] == b"ftyp") or ctype in {"video/mp4", "video/quicktime"} or name.endswith((".mp4", ".mov", ".m4v")):
        if len(data) > 12 and data[4:8] == b"ftyp":
            suffix = ".mov" if name.endswith(".mov") or ctype == "video/quicktime" else ".mp4"
            return "video/mp4" if suffix == ".mp4" else "video/quicktime", suffix
    if data.startswith(_WEBM) or ctype == "video/webm" or name.endswith(".webm"):
        if data.startswith(_WEBM):
            return "video/webm", ".webm"
    raise HTTPException(422, "Upload a JPEG, PNG, MP4, MOV, or WebM scene. Face-cropped identity photos are not used.")


def run_pose_analysis(data: bytes, suffix: str) -> dict:
    if not ANALYZE_CLI.exists():
        raise HTTPException(503, "The computer-vision analyzer is missing from this deployment.")
    with tempfile.TemporaryDirectory(prefix="ht-vision-") as folder:
        source = Path(folder) / f"scene{suffix}"
        result_path = Path(folder) / "result.json"
        source.write_bytes(data)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(CV_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        env["YOLO_VERBOSE"] = "False"
        env.setdefault("CV_DEVICE", "cpu")
        try:
            proc = subprocess.run(
                [sys.executable, str(ANALYZE_CLI), str(source), str(result_path)],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(CV_ROOT),
                timeout=ANALYZE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(504, "YOLO analysis timed out.") from exc
        payload: dict = {}
        if result_path.exists():
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
        if proc.returncode != 0 or not payload.get("yolo_active"):
            detail = payload.get("error") or (proc.stderr or "").strip() or "YOLO Pose is not active on this machine."
            raise HTTPException(503, f"{detail} Install cv_service/requirements-vision.txt and retry.")
        return payload
