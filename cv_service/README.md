# Patient Safety CV Demo

This service is intentionally video/simulation-first. It does not perform face recognition, diagnosis, or patient identity recognition.

```powershell
$env:CV_BACKEND_URL="https://healthtech-api.onrender.com"
$env:CV_SERVICE_TOKEN="..."
$env:CV_MODEL="yolo11n-pose.pt"
$env:CV_VIDEO_PATH="videos\fall_risk_demo.mp4"
python run_demo.py --simulate
python run_demo.py --video $env:CV_VIDEO_PATH
python analyze_cli.py path\to\corridor.jpg result.json
```

For real video/camera inference, install `requirements-vision.txt`. The adapter uses YOLO Pose keypoints and explainable body geometry; it never performs face or identity recognition. Stable-frame confirmation, cooldown, and backend deduplication prevent one-frame alert spam.

Hospital Admin Safety uploads are analyzed through `analyze_cli.py`. If the optional model is unavailable, that path fails honestly with `yolo_active: false`. The `--simulate` demo sequence remains available for fall-risk walkthroughs and does not pretend to count a crowd.
