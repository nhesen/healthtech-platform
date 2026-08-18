from dataclasses import dataclass
import os
@dataclass
class Settings:
    backend_url: str=os.getenv("CV_BACKEND_URL","http://localhost:8000")
    room_id: str=os.getenv("DEMO_ROOM_ID","204")
    confirm_frames: int=int(os.getenv("STATE_CONFIRM_FRAMES","5"))
    cooldown_seconds: int=int(os.getenv("EVENT_COOLDOWN_SECONDS","30"))
    frame_skip: int=int(os.getenv("FRAME_SKIP","2"))
