from app.sources.majsoul.canonicalizer import canonicalize_majsoul


def test_four_player_actions_become_ordered_events(load_fixture):
    game = canonicalize_majsoul(load_fixture("majsoul/four_player_actions.json"))
    assert game.rules.player_count == 4
    assert [event.sequence for event in game.rounds[0].events] == sorted(
        event.sequence for event in game.rounds[0].events
    )


def test_three_player_babei_becomes_kita_and_unknown_is_preserved(load_fixture):
    game = canonicalize_majsoul(load_fixture("majsoul/three_player_kita.json"))
    calls = [event for event in game.rounds[0].events if event.event_type == "call"]
    unknown = [event for event in game.rounds[0].events if event.event_type == "unknown"]
    assert any(event.kind == "kita" for event in calls)
    assert unknown[0].raw_type == ".lq.RecordMystery"


def test_settlement_delta_is_kept_as_replay_fact(load_fixture):
    game = canonicalize_majsoul(load_fixture("majsoul/four_player_actions.json"))
    win = next(event for event in game.rounds[0].events if event.event_type == "win")
    assert win.score_delta == [6200, -6200, 0, 0]


def test_embedded_dora_and_riichi_fields_become_distinct_canonical_events():
    decoded = {
        "external_id": "embedded-events",
        "accounts": [{"seat": seat, "nickname": f"P{seat}"} for seat in range(4)],
        "final_scores": [25000] * 4,
        "final_ranks": [1, 2, 3, 4],
        "rounds": [
            {
                "starting_scores": [25000] * 4,
                "actions": [
                    {
                        "name": ".lq.RecordNewRound",
                        "data": {"dealer": 0, "scores": [25000] * 4, "dora": "1z"},
                        "sequence": 0,
                    },
                    {
                        "name": ".lq.RecordDiscardTile",
                        "data": {"seat": 0, "tile": "9s", "is_liqi": True, "doras": ["1z"]},
                        "sequence": 1,
                    },
                    {
                        "name": ".lq.RecordAnGangAddGang",
                        "data": {"seat": 1, "type": 2, "tiles": "5p", "doras": ["1z", "4p"]},
                        "sequence": 2,
                    },
                    {
                        "name": ".lq.RecordDealTile",
                        "data": {"seat": 1, "tile": "6p", "liqi": {"seat": 0}, "doras": ["1z", "4p"]},
                        "sequence": 3,
                    },
                ],
            }
        ],
    }

    game = canonicalize_majsoul(decoded)
    events = game.rounds[0].events
    calls = [event for event in events if event.event_type == "call"]
    dora_reveals = [event for event in events if event.event_type == "dora_revealed"]

    assert [event.sequence for event in events] == list(range(len(events)))
    assert any(event.event_type == "riichi_declared" and event.actor == 0 for event in events)
    assert any(event.event_type == "riichi_accepted" and event.actor == 0 for event in events)
    assert [(event.indicator, event.reason) for event in dora_reveals] == [("4p", "kan")]
    assert calls[0].tile == "5p"
    assert calls[0].consumed_tiles == ["5p"] * 4
