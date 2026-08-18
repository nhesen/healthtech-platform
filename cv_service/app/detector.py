def classify_frame(frame) -> tuple[str,float]:
    """Extension point for Ultralytics/MediaPipe pose. Return UNKNOWN when pose confidence is insufficient."""
    return "UNKNOWN",0.0
