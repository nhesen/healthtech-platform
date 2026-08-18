from app.state_machine import StateMachine
from app.risk_engine import RiskEngine
from app.detector import classify_keypoints
def test_standing_requires_stable_frames_and_triggers_risk():
    machine=StateMachine(confirm_frames=3); risk=RiskEngine(cooldown_seconds=0)
    for _ in range(3): change=machine.update("SITTING")
    assert change==("UNKNOWN","SITTING")
    assert machine.update("STANDING") is None
    for _ in range(2): change=machine.update("STANDING")
    assert change==("SITTING","STANDING")
    assert risk.evaluate(*change,.91)["event_type"]=="FALL_RISK"

def pose(shoulder,hip,knee,ankle):
    points=[[0,0,0] for _ in range(17)]
    for left,right,center in [(5,6,shoulder),(11,12,hip),(13,14,knee),(15,16,ankle)]:
        points[left]=[center[0]-5,center[1],.9];points[right]=[center[0]+5,center[1],.9]
    return points

def test_explainable_pose_geometry_states():
    assert classify_keypoints(pose((0,0),(0,100),(0,170),(0,240)))[0]=="STANDING"
    assert classify_keypoints(pose((0,0),(0,100),(0,130),(0,180)))[0]=="SITTING"
    assert classify_keypoints(pose((0,0),(150,10),(210,12),(270,14)))[0]=="LYING"
