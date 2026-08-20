from app.analyzer import crowding_level, majority_pose, summarize_frames
from app.detector import classify_keypoints


def pose(shoulder, hip, knee, ankle):
    points = [[0, 0, 0] for _ in range(17)]
    for left, right, center in [(5, 6, shoulder), (11, 12, hip), (13, 14, knee), (15, 16, ankle)]:
        points[left] = [center[0] - 5, center[1], .9]
        points[right] = [center[0] + 5, center[1], .9]
    return points


def test_crowding_thresholds_are_explainable():
    assert crowding_level(0) == "EMPTY"
    assert crowding_level(2) == "LOW"
    assert crowding_level(4) == "MODERATE"
    assert crowding_level(7) == "BUSY"
    assert crowding_level(8) == "OVERCROWDED"


def test_summarize_frames_counts_people_and_pose_transitions():
    sitting = {"index": 0, "state": "SITTING", "confidence": 0.9}
    standing = {"index": 0, "state": "STANDING", "confidence": 0.91}
    summary = summarize_frames([
        {"index": 0, "person_count": 3, "people": [sitting, sitting, sitting]},
        {"index": 2, "person_count": 9, "people": [standing] * 9},
    ])
    assert summary["peak_people"] == 9
    assert summary["crowding"]["level"] == "OVERCROWDED"
    assert summary["movement"]["incoming_people"] is True
    assert summary["movement"]["fall_risk_signal"] is True
    assert "SITTING->STANDING" in summary["movement"]["transitions"]
    assert majority_pose([sitting, standing, standing]) == "STANDING"


def test_explainable_pose_geometry_states():
    assert classify_keypoints(pose((0, 0), (0, 100), (0, 170), (0, 240)))[0] == "STANDING"
    assert classify_keypoints(pose((0, 0), (0, 100), (0, 130), (0, 180)))[0] == "SITTING"
    assert classify_keypoints(pose((0, 0), (150, 10), (210, 12), (270, 14)))[0] == "LYING"
