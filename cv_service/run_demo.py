import argparse,logging
from app.config import Settings
from app.detector import PoseDetector
from app.event_client import send_event
from app.risk_engine import RiskEngine
from app.state_machine import StateMachine

logging.basicConfig(level=logging.INFO,format="[CV] %(message)s")
def process(states,settings):
    machine=StateMachine(settings.confirm_frames);risk=RiskEngine(settings.cooldown_seconds)
    for state,confidence in states:
        change=machine.update(state)
        if not change:continue
        logging.info("Room %s: %s -> %s",settings.room_id,*change);event=risk.evaluate(*change,confidence)
        if event:
            event["room_id"]=settings.room_id;event["metadata"]={"source":"yolo_pose_or_simulator","identity_recognition":False}
            try:logging.info("FALL_RISK sent: %s",send_event(settings.backend_url,event))
            except Exception as exc:logging.warning("Backend unavailable; event retained in logs: %s",exc)
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--simulate",action="store_true");parser.add_argument("--video");parser.add_argument("--camera",type=int);args=parser.parse_args();settings=Settings()
    if not (args.simulate or args.video or args.camera is not None):parser.error("Use --simulate, --video, or --camera")
    fallback=((state,.91) for state in ["LYING"]*5+["SITTING"]*5+["STANDING"]*5)
    if args.simulate:process(fallback,settings);return
    try:process(PoseDetector().states(args.video if args.video else args.camera,settings.frame_skip),settings)
    except RuntimeError as exc:
        logging.warning("%s; running deterministic safety fallback",exc)
        process(((state,.91) for state in ["LYING"]*5+["SITTING"]*5+["STANDING"]*5),settings)
if __name__=="__main__":main()
