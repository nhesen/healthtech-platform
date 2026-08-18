from collections import deque
from dataclasses import dataclass, field

STATES={"LYING","SITTING","STANDING","UNKNOWN"}
@dataclass
class StateMachine:
    confirm_frames:int=5
    history:deque=field(default_factory=lambda:deque(maxlen=7))
    stable_state:str="UNKNOWN"
    previous_state:str="UNKNOWN"
    def update(self, state:str)->tuple[str,str]|None:
        self.history.append(state if state in STATES else "UNKNOWN")
        candidate=self.history[-1]
        consecutive=0
        for value in reversed(self.history):
            if value != candidate: break
            consecutive += 1
        if candidate != "UNKNOWN" and consecutive >= self.confirm_frames and candidate != self.stable_state:
            self.previous_state,self.stable_state=self.stable_state,candidate
            return self.previous_state,self.stable_state
        return None
