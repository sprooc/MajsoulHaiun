from app.algorithms.baseline_v1 import calibration


def test_dealer_calibration_uses_fourteen_tiles(monkeypatch):
    hand_sizes: list[int] = []

    def record_hand_size(state, _rules):
        hand_sizes.append(len(state.codes))
        return 0.0

    monkeypatch.setattr(calibration, "hand_value", record_hand_size)

    calibration.generate(seed=20260713, samples=1)

    assert hand_sizes == [14, 13, 14, 13]
