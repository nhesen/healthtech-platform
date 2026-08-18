from app.state_machine import StateMachine
from app.risk_engine import RiskEngine
def test_standing_requires_stable_frames_and_triggers_risk():
    machine=StateMachine(confirm_frames=3); risk=RiskEngine(cooldown_seconds=0)
    for _ in range(3): change=machine.update("SITTING")
    assert change==("UNKNOWN","SITTING")
    assert machine.update("STANDING") is None
    for _ in range(2): change=machine.update("STANDING")
    assert change==("SITTING","STANDING")
    assert risk.evaluate(*change,.91)["event_type"]=="FALL_RISK"
