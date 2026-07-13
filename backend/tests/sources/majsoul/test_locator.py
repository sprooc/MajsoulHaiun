import pytest

from app.sources.majsoul.locator import MajsoulLocator


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("260307-76323960-cf3c-494e-be24-26dd6ba81c98", "260307-76323960-cf3c-494e-be24-26dd6ba81c98"),
        (
            "https://game.maj-soul.com/1/?paipu=260307-76323960-cf3c-494e-be24-26dd6ba81c98_a21590812",
            "260307-76323960-cf3c-494e-be24-26dd6ba81c98",
        ),
    ],
)
def test_parse_majsoul_locator(value, expected):
    assert MajsoulLocator.parse(value).record_id == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://127.0.0.1/private",
        "https://example.com/?paipu=260307-76323960-cf3c-494e-be24-26dd6ba81c98",
        "not a replay id",
        "x" * 161,
    ],
)
def test_locator_rejects_arbitrary_urls_and_invalid_ids(value):
    with pytest.raises(ValueError):
        MajsoulLocator.parse(value)
