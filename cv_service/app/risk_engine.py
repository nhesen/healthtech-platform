from dataclasses import dataclass
from time import monotonic
@dataclass
class RiskEngine:
    cooldown_seconds:int=30
    last_event:float=-9999
    def evaluate(self, previous:str,current:str,confidence:float,high_risk:bool=True):
        if not high_risk or confidence<.5 or monotonic()-self.last_event<self.cooldown_seconds:return None
        if (previous,current) in {("SITTING","STANDING"),("LYING","STANDING")}:
            self.last_event=monotonic(); return {"event_type":"FALL_RISK","severity":"HIGH","patient_state":current,"previous_state":previous,"confidence":confidence}
        return None
