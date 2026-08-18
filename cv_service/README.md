# Patient Safety CV Demo

This service is intentionally video/simulation-first. It does not perform face recognition, diagnosis, or patient identity recognition.

```powershell
$env:CV_BACKEND_URL="https://healthtech-api.onrender.com"
$env:CV_SERVICE_TOKEN="..."
$env:CV_MODEL="yolo11n-pose.pt"
$env:CV_VIDEO_PATH="videos\fall_risk_demo.mp4"
python run_demo.py --simulate
python run_demo.py --video $env:CV_VIDEO_PATH
```

For real video/camera inference, install `requirements-vision.txt`. The adapter uses YOLO Pose keypoints and explainable body geometry; it never performs face or identity recognition. Stable-frame confirmation, cooldown, and backend deduplication prevent one-frame alert spam. If the optional model is unavailable, video mode fails over to the deterministic demo sequence without breaking the safety workflow.
