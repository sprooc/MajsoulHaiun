from app.sources.majsoul.canonicalizer import canonicalize_majsoul
from app.sources.majsoul.decoder import decode_majsoul
from app.sources.majsoul.protocol import load_vendored_descriptor


def varint(value: int) -> bytes:
    output = bytearray()
    while value > 0x7F:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def field_varint(field_id: int, value: int) -> bytes:
    return varint(field_id << 3) + varint(value)


def field_bytes(field_id: int, value: bytes) -> bytes:
    return varint((field_id << 3) | 2) + varint(len(value)) + value


def wrapper(name: str, data: bytes) -> bytes:
    return field_bytes(1, name.encode()) + field_bytes(2, data)


def test_decodes_legacy_binary_game_detail_records_with_vendored_descriptor():
    new_round = b"".join(
        [
            field_varint(1, 0),
            field_varint(2, 0),
            field_varint(3, 0),
            field_bytes(4, b"1z"),
            field_bytes(5, b"".join(varint(25000) for _ in range(4))),
            field_bytes(7, b"1m"),
            field_bytes(8, b"2m"),
            field_bytes(9, b"3m"),
            field_bytes(10, b"4m"),
        ]
    )
    detail_records = field_bytes(1, wrapper(".lq.RecordNewRound", new_round))
    payload = wrapper(".lq.GameDetailRecords", detail_records)

    decoded = decode_majsoul(payload, load_vendored_descriptor())
    game = canonicalize_majsoul(decoded)

    assert game.rules.player_count == 4
    assert len(game.players) == 4
    assert game.rounds[0].events[0].event_type == "round_started"
    assert game.rounds[0].events[0].dora_indicator == "1z"


def test_json_replays_remain_supported():
    decoded = decode_majsoul(b'{"accounts": [], "rounds": []}')
    assert decoded["rounds"] == []


def test_decodes_current_actions_container_and_preserves_step_sequence():
    deal_tile = field_varint(1, 0) + field_bytes(2, b"0m")
    prototype = (
        field_varint(1, 7)
        + field_bytes(2, b".lq.RecordDealTile")
        + field_bytes(3, deal_tile)
    )
    game_action = field_bytes(3, prototype)
    details = field_bytes(3, game_action)
    payload = wrapper(".lq.GameDetailRecords", details)

    decoded = decode_majsoul(payload, load_vendored_descriptor())

    assert decoded["rounds"][0]["actions"][0]["sequence"] == 7
    assert decoded["rounds"][0]["actions"][0]["data"]["tile"] == "0m"


def test_binary_negative_int32_score_delta_is_restored():
    new_round = field_bytes(5, b"".join(varint(25000) for _ in range(4)))
    hule_info = field_varint(4, 0)
    deltas = field_bytes(3, varint(8000) + varint((1 << 64) - 8000) + varint(0) + varint(0))
    final_scores = field_bytes(5, b"".join(varint(value) for value in [33000, 17000, 25000, 25000]))
    hule = field_bytes(1, hule_info) + deltas + final_scores
    details = (
        field_bytes(1, wrapper(".lq.RecordNewRound", new_round))
        + field_bytes(1, wrapper(".lq.RecordHule", hule))
    )
    game = canonicalize_majsoul(decode_majsoul(wrapper(".lq.GameDetailRecords", details), load_vendored_descriptor()))
    win = next(event for event in game.rounds[0].events if event.event_type == "win")
    assert win.score_delta == [8000, -8000, 0, 0]


def test_res_game_record_outer_container_preserves_accounts_and_uuid():
    accounts = b"".join(
        field_bytes(11, field_varint(2, seat) + field_bytes(3, f"Player {seat + 1}".encode()))
        for seat in range(4)
    )
    head = field_bytes(1, b"record-uuid") + accounts
    new_round = field_bytes(5, b"".join(varint(25000) for _ in range(4)))
    details = field_bytes(1, wrapper(".lq.RecordNewRound", new_round))
    response = field_bytes(3, head) + field_bytes(4, details)

    decoded = decode_majsoul(wrapper(".lq.ResGameRecord", response), load_vendored_descriptor())

    assert decoded["external_id"] == "record-uuid"
    assert [account["nickname"] for account in decoded["accounts"]] == [
        "Player 1", "Player 2", "Player 3", "Player 4"
    ]
