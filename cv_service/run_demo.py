import argparse, logging, sys
from app.config import Settings
from app.event_client import send_event
from app.risk_engine import RiskEngine
from app.state_machine import StateMachine

logging.basicConfig(level=logging.INFO,format="[CV] %(message)s")
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--simulate",action="store_true"); parser.add_argument("--video"); parser.add_argument("--camera",type=int); args=parser.parse_args(); settings=Settings()
    if not (args.simulate or args.video or args.camera is not None): parser.error("Use --simulate, --video, or --camera")
    if args.video: logging.info("Prepared video mode: %s (pose model optional; using demo transition fallback)",args.video)
    if args.camera is not None: logging.info("Webcam mode is optional; no model installed, using safe fallback.")
    machine=StateMachine(settings.confirm_frames); risk=RiskEngine(settings.cooldown_seconds)
    for state in ["LYING"]*5+["SITTING"]*5+["STANDING"]*5:
        change=machine.update(state)
        if change:
            logging.info("Room %s: %s -> %s",settings.room_id,*change)
            event=risk.evaluate(*change,.91)
            if event:
                event["room_id"]=settings.room_id; event["metadata"]={"source":"prepared_video_simulator","model":"optional_pose"}
                try: logging.info("FALL_RISK sent: %s",send_event(settings.backend_url,event))
                except Exception as exc: logging.warning("Backend unavailable; demo state remains valid: %s",exc)
if __name__=="__main__": main()
