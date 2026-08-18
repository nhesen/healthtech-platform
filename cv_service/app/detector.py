"""Optional YOLO Pose adapter. No face or identity recognition is performed."""
from __future__ import annotations
from collections.abc import Iterator
import os

def classify_keypoints(points:list[list[float]]) -> tuple[str,float]:
    """Classify a COCO pose from x/y/confidence keypoints using explainable geometry."""
    needed=[5,6,11,12]
    if len(points)<17 or any(points[i][2]<.35 for i in needed): return "UNKNOWN",0.0
    shoulder=((points[5][0]+points[6][0])/2,(points[5][1]+points[6][1])/2)
    hip=((points[11][0]+points[12][0])/2,(points[11][1]+points[12][1])/2)
    torso_dx=abs(hip[0]-shoulder[0]);torso_dy=abs(hip[1]-shoulder[1]);base=min(points[i][2] for i in needed)
    if torso_dx>torso_dy*1.2:return "LYING",base
    legs=[i for i in (13,14,15,16) if points[i][2]>=.35]
    if len(legs)<2:return "UNKNOWN",base*.7
    knee_y=sum(points[i][1] for i in (13,14))/2;ankle_y=sum(points[i][1] for i in (15,16))/2
    if ankle_y-knee_y>torso_dy*.55 and knee_y-hip[1]>torso_dy*.45:return "STANDING",base
    if abs(knee_y-hip[1])<torso_dy*.75:return "SITTING",base
    return "UNKNOWN",base*.7

class PoseDetector:
    def __init__(self,model_name:str|None=None):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install cv_service/requirements-vision.txt for YOLO video mode") from exc
        self.model=YOLO(model_name or os.getenv("CV_MODEL") or os.getenv("YOLO_POSE_MODEL","yolo11n-pose.pt"))
    def states(self,source:str|int,frame_skip:int=2)->Iterator[tuple[str,float]]:
        for index,result in enumerate(self.model.predict(source=source,stream=True,verbose=False)):
            if index%max(1,frame_skip):continue
            if result.keypoints is None or len(result.keypoints)==0:yield "UNKNOWN",0.0;continue
            xy=result.keypoints.xy[0].cpu().tolist();conf=result.keypoints.conf[0].cpu().tolist()
            yield classify_keypoints([[p[0],p[1],conf[i]] for i,p in enumerate(xy)])
