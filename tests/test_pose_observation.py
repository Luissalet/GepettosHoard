import pytest
from pose_engine.core.card_pose_vision import reject_calibration_echo


def test_calibration_echo_is_rejected_even_when_fit_would_be_exact():
    points = {f'joint{i}': [i / 20, .5] for i in range(10)}
    raw = {'keypoints': [{'name': name, 'x': xy[0], 'y': xy[1]} for name, xy in points.items()]}
    with pytest.raises(ValueError, match='copied the calibration'):
        reject_calibration_echo(raw, points)


def test_genuine_target_observations_and_missing_calibration_are_allowed():
    points = {f'joint{i}': [i / 20, .5] for i in range(10)}
    raw = {'keypoints': [{'name': name, 'x': xy[0] + .12, 'y': .3} for name, xy in points.items()]}
    reject_calibration_echo(raw, points)
    reject_calibration_echo(raw, {})
