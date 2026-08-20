from app.analyzer import cell_color, crowding_level, detection_label, majority_pose, occupancy_grid, render_occupancy_overlay, summarize_frames
from app.detector import box_iou, classify_keypoints, empty_seats_from_people, merge_pose_into_detect, nms_detections, people_from_detect, seats_from_detect, sitting_slots_from_furniture


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
    assert summary["empty_seats"] == 0
    assert summary["seats_detected"] == 0
    assert summary["crowding"]["level"] == "OVERCROWDED"
    assert summary["movement"]["incoming_people"] is True
    assert summary["movement"]["fall_risk_signal"] is True
    assert "SITTING->STANDING" in summary["movement"]["transitions"]
    assert majority_pose([sitting, standing, standing]) == "STANDING"


def test_occupancy_grid_marks_people_cells():
    grid = occupancy_grid(800, 600, [{"center": [50, 50]}, {"center": [790, 590]}])
    assert grid[0][0] == 1
    assert grid[5][7] == 1
    assert sum(value for row in grid for value in row) == 2
    assert cell_color(0)[1] > cell_color(2)[1]


def test_detection_label_matches_classic_yolo_format():
    assert detection_label({"label": "person", "confidence": 0.85}) == "person 85%"
    assert detection_label({"label": "person", "confidence": 0.9}) == "person 90%"
    assert detection_label({"label": "empty", "confidence": 0.8}) == "empty"


def test_occupancy_overlay_encodes_jpeg():
    numpy = __import__("numpy")
    image = numpy.zeros((120, 160, 3), dtype=numpy.uint8)
    overlay = render_occupancy_overlay(
        image,
        [{"label": "person", "confidence": 0.85, "box": [5, 20, 40, 90]}],
        [{"label": "empty", "confidence": 0.8, "box": [70, 70, 110, 100]}],
    )
    assert overlay and overlay["mime"] == "image/jpeg" and overlay["base64"]


class _T:
    def __init__(self, data):
        self._data = data
    def cpu(self):
        return self
    def tolist(self):
        return self._data


def test_summarize_frames_reports_empty_seats_from_peak_frame():
    summary = summarize_frames([
        {"index": 0, "person_count": 2, "people": [], "seat_count": 8, "empty_seat_count": 6},
        {"index": 1, "person_count": 4, "people": [], "seat_count": 8, "empty_seat_count": 4},
    ])
    assert summary["peak_people"] == 4
    assert summary["empty_seats"] == 4
    assert summary["seats_detected"] == 8
    assert summary["crowding"]["empty_seats"] == 4
    assert "Empty seats: 4 of 8" in summary["crowding"]["explanation"]


def test_nms_drops_overlapping_seat_fragments():
    kept = nms_detections([
        {"confidence": 0.9, "box": [10, 40, 50, 90]},
        {"confidence": 0.4, "box": [12, 42, 48, 88]},
        {"confidence": 0.8, "box": [80, 40, 120, 90]},
    ], 0.4)
    assert len(kept) == 2
    assert kept[0]["box"] == [10, 40, 50, 90]


def test_wide_bench_becomes_multiple_sitting_slots():
    people = [{"box": [10, 20, 60, 140]}]
    slots = sitting_slots_from_furniture(
        [{"label": "bench", "confidence": 0.8, "box": [0, 90, 360, 150]}],
        people,
        (360, 180),
    )
    assert len(slots) >= 5
    widths = [item["box"][2] - item["box"][0] for item in slots]
    heights = [item["box"][3] - item["box"][1] for item in slots]
    assert max(widths) - min(widths) < 2
    assert max(heights) - min(heights) < 2


def test_chair_slot_uses_seat_pan_not_backrest():
    people = [{"box": [20, 30, 70, 160]}]
    slots = sitting_slots_from_furniture(
        [{"label": "chair", "confidence": 0.85, "box": [20, 40, 80, 150]}],
        people,
        (400, 200),
    )
    assert len(slots) == 1
    assert slots[0]["box"][1] > 70
    assert slots[0]["box"][3] <= 150
    assert slots[0]["box"][3] - slots[0]["box"][1] < 50


def test_filter_drops_tiny_high_and_low_conf_chairs():
    people = [{"box": [20, 30, 70, 160]}]
    slots = sitting_slots_from_furniture([
        {"label": "chair", "confidence": 0.9, "box": [30, 2, 50, 20]},
        {"label": "chair", "confidence": 0.15, "box": [200, 80, 250, 140]},
        {"label": "chair", "confidence": 0.8, "box": [200, 70, 260, 150]},
    ], people, (400, 200))
    assert len(slots) == 1
    assert slots[0]["box"][0] >= 190


def test_empty_seats_skip_chairs_occupied_by_people():
    people = [{"box": [10, 10, 40, 80], "center": [25, 45]}]
    seats = [
        {"label": "chair", "confidence": 0.8, "box": [8, 50, 42, 90], "center": [25, 70]},
        {"label": "chair", "confidence": 0.7, "box": [80, 50, 120, 90], "center": [100, 70]},
    ]
    empty = empty_seats_from_people(people, seats)
    assert len(empty) == 1
    assert empty[0]["label"] == "empty"
    assert empty[0]["box"] == [80, 50, 120, 90]


def test_detect_keeps_person_and_chair_boxes_separate():
    boxes = type("Boxes", (), {})()
    boxes.xyxy = _T([[10, 10, 40, 80], [50, 10, 90, 80], [5, 5, 20, 20]])
    boxes.conf = _T([0.91, 0.44, 0.9])
    boxes.cls = _T([0, 0, 56])
    result = type("R", (), {"boxes": boxes, "names": {0: "person", 56: "chair"}})()
    people = people_from_detect(result, min_conf=0.15)
    seats = seats_from_detect(result, min_conf=0.15)
    assert len(people) == 2
    assert len(seats) == 1
    assert seats[0]["label"] == "chair"
    assert all(item["label"] == "person" and item["box"] for item in people)


def test_merge_keeps_detect_count_and_copies_pose_state():
    detected = [{"label": "person", "state": "UNKNOWN", "confidence": 0.9, "box": [0, 0, 50, 100]}]
    posed = [{"label": "person", "state": "SITTING", "confidence": 0.8, "box": [2, 2, 48, 98]}]
    merged = merge_pose_into_detect(detected, posed)
    assert len(merged) == 1 and merged[0]["state"] == "SITTING"
    assert box_iou(detected[0]["box"], posed[0]["box"]) > 0.5


def test_explainable_pose_geometry_states():
    assert classify_keypoints(pose((0, 0), (0, 100), (0, 170), (0, 240)))[0] == "STANDING"
    assert classify_keypoints(pose((0, 0), (0, 100), (0, 130), (0, 180)))[0] == "SITTING"
    assert classify_keypoints(pose((0, 0), (150, 10), (210, 12), (270, 14)))[0] == "LYING"
