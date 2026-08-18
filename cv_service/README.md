# Patient Safety CV Demo

This service is intentionally video/simulation-first. It does not perform face recognition, diagnosis, or patient identity recognition.

```powershell
python run_demo.py --simulate
python run_demo.py --video videos/fall_risk_demo.mp4
```

`--video` currently uses the explainable fallback state sequence when an optional pose model is not installed. Install Ultralytics later to replace `classify_frame` without changing the backend event contract.
