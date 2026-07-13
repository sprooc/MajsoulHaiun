from typing import Any

from app.domain.events import (
    AbortiveDraw,
    CallEvent,
    CallKind,
    DoraRevealed,
    ExhaustiveDraw,
    RiichiAccepted,
    RiichiDeclared,
    RoundStarted,
    TileDiscarded,
    TileDrawn,
    UnknownEvent,
    WinEvent,
)
from app.domain.game import CanonicalGame, Player, Round
from app.domain.rules import RuleSet
from app.errors import AppError


def _tile_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(tile) for tile in value]
    return []


def _event(action: dict[str, Any]):
    name = str(action.get("name", ""))
    data = action.get("data") if isinstance(action.get("data"), dict) else {}
    sequence = int(action.get("sequence", 0))
    if name == ".lq.RecordNewRound":
        return RoundStarted(
            sequence=sequence,
            dealer=int(data.get("dealer", 0)),
            scores=list(data.get("scores", [])),
            dora_indicator=data.get("dora"),
            starting_hands=data.get("tiles"),
        )
    if name == ".lq.RecordDealTile":
        return TileDrawn(
            sequence=sequence,
            actor=int(data.get("seat", 0)),
            tile=str(data.get("tile", "1z")),
            from_rinshan=bool(data.get("lingshangzimo", False)),
        )
    if name == ".lq.RecordDiscardTile":
        return TileDiscarded(
            sequence=sequence,
            actor=int(data.get("seat", 0)),
            tile=str(data.get("tile", "1z")),
            tsumogiri=bool(data.get("moqie", False)),
        )
    if name == ".lq.RecordBaBei":
        return CallEvent(
            sequence=sequence,
            actor=int(data.get("seat", 0)),
            kind=CallKind.KITA,
            tile="4z",
            consumed_tiles=["4z"],
        )
    if name in {".lq.RecordChiPengGang", ".lq.RecordAnGangAddGang"}:
        actor = int(data.get("seat", 0))
        raw_kind = data.get("kind", data.get("type", "pon"))
        if isinstance(raw_kind, int):
            if name == ".lq.RecordChiPengGang":
                kind = {0: CallKind.CHI, 1: CallKind.PON, 2: CallKind.DAIMINKAN}.get(raw_kind, CallKind.PON)
            else:
                kind = {2: CallKind.ANKAN, 3: CallKind.KAKAN}.get(raw_kind, CallKind.ANKAN)
        else:
            kind_aliases = {
                "chi": "chi",
                "peng": "pon",
                "pon": "pon",
                "gang": "daiminkan",
                "ankan": "ankan",
                "kakan": "kakan",
            }
            kind = CallKind(kind_aliases.get(str(raw_kind).lower(), "pon"))
        tiles = _tile_list(data.get("tiles"))
        if name == ".lq.RecordAnGangAddGang":
            tile = str(data.get("tile") or next(iter(tiles), "1z"))
            consumed_tiles = [tile] * (4 if kind == CallKind.ANKAN else 1)
            target = None
        else:
            froms = [int(seat) for seat in data.get("froms", [])] if isinstance(data.get("froms"), list) else []
            target_index = next((index for index, seat in enumerate(froms) if seat != actor), None)
            tile = str(data.get("tile") or (tiles[target_index] if target_index is not None else next(iter(tiles), "1z")))
            target = froms[target_index] if target_index is not None else data.get("from")
            if len(froms) == len(tiles):
                consumed_tiles = [tile_code for tile_code, source in zip(tiles, froms) if source == actor]
            else:
                consumed_tiles = _tile_list(data.get("consumed_tiles")) or list(tiles)
                if tile in consumed_tiles:
                    consumed_tiles.remove(tile)
        return CallEvent(
            sequence=sequence,
            actor=actor,
            kind=kind,
            tile=tile,
            consumed_tiles=consumed_tiles,
            target=target,
        )
    if name == ".lq.RecordHule":
        return WinEvent(
            sequence=sequence,
            winners=[int(seat) for seat in data.get("winners", [])],
            loser=data.get("loser"),
            score_delta=[int(value) for value in data.get("delta_scores", [])],
            ura_indicators=[str(tile) for tile in data.get("ura_doras", [])],
        )
    if name == ".lq.RecordNoTile":
        return ExhaustiveDraw(
            sequence=sequence,
            tenpai_players=[int(seat) for seat in data.get("tenpai", [])],
            score_delta=[int(value) for value in data.get("delta_scores", [])],
        )
    if name == ".lq.RecordLiuJu":
        return AbortiveDraw(
            sequence=sequence,
            reason=str(data.get("reason", data.get("type", "unknown"))),
            score_delta=[int(value) for value in data.get("delta_scores", [])],
        )
    return UnknownEvent(sequence=sequence, raw_type=name or "unknown", raw_payload=data)


def _canonical_events(actions: list[dict[str, Any]]) -> list[object]:
    events: list[object] = []
    known_doras: list[str] = []
    for action in sorted(actions, key=lambda item: int(item.get("sequence", 0))):
        data = action.get("data") if isinstance(action.get("data"), dict) else {}
        expanded: list[object] = []
        liqi = data.get("liqi") if isinstance(data.get("liqi"), dict) else None
        if liqi and "seat" in liqi and not liqi.get("failed", False):
            expanded.append(
                RiichiAccepted(
                    sequence=0,
                    actor=int(liqi["seat"]),
                )
            )

        primary = _event(action)
        expanded.append(primary)
        if isinstance(primary, RoundStarted):
            known_doras = [primary.dora_indicator] if primary.dora_indicator else []
        elif isinstance(primary, TileDiscarded) and (data.get("is_liqi") or data.get("is_wliqi")):
            expanded.append(RiichiDeclared(sequence=0, actor=primary.actor))

        reported_doras = _tile_list(data.get("doras"))
        if reported_doras:
            remaining = list(known_doras)
            newly_revealed: list[str] = []
            for indicator in reported_doras:
                if indicator in remaining:
                    remaining.remove(indicator)
                else:
                    newly_revealed.append(indicator)
            expanded.extend(
                DoraRevealed(sequence=0, indicator=indicator, reason="kan")
                for indicator in newly_revealed
            )
            known_doras = reported_doras

        for event in expanded:
            events.append(event.model_copy(update={"sequence": len(events)}))
    return events


def canonicalize_majsoul(decoded: dict[str, Any]) -> CanonicalGame:
    accounts = decoded.get("accounts")
    rounds_data = decoded.get("rounds")
    if not isinstance(accounts, list) or not isinstance(rounds_data, list):
        raise AppError("INVALID_REPLAY_DATA", "Replay is missing accounts or rounds.", status_code=422)
    count = len(accounts)
    if count == 4:
        rules = RuleSet.standard_four_player()
    elif count == 3:
        rules = RuleSet.standard_three_player()
    else:
        raise AppError("UNSUPPORTED_GAME_MODE", "Only standard three- and four-player games are supported.", status_code=422)
    source_rules = decoded.get("rules") if isinstance(decoded.get("rules"), dict) else {}
    rules = rules.model_copy(update={"source_rules": source_rules, "tsumo_loss": source_rules.get("tsumo_loss", rules.tsumo_loss)})
    players = [
        Player(
            seat=int(account.get("seat", index)),
            name=str(account.get("nickname", account.get("name", f"P{index}"))),
            external_id=str(account["account_id"]) if "account_id" in account else None,
            level_id=account.get("level_id"),
        )
        for index, account in enumerate(accounts)
        if isinstance(account, dict)
    ]
    rounds: list[Round] = []
    for index, item in enumerate(rounds_data):
        if not isinstance(item, dict):
            continue
        actions = item.get("actions") if isinstance(item.get("actions"), list) else item.get("records", [])
        typed_actions = [action for action in actions if isinstance(action, dict)]
        rounds.append(
            Round(
                index=index,
                wind=item.get("wind", "east"),
                hand=int(item.get("hand", index % count + 1)),
                dealer=int(item.get("dealer", index % count)),
                honba=int(item.get("honba", 0)),
                riichi_sticks=int(item.get("riichi_sticks", 0)),
                starting_scores=[int(value) for value in item.get("starting_scores", [rules.initial_score] * count)],
                events=_canonical_events(typed_actions),
            )
        )
    return CanonicalGame(
        source="majsoul",
        external_id=str(decoded.get("external_id", decoded.get("uuid", "unknown"))),
        rules=rules,
        players=players,
        rounds=rounds,
        final_scores=[int(value) for value in decoded.get("final_scores", [rules.initial_score] * count)],
        final_ranks=[int(value) for value in decoded.get("final_ranks", list(range(1, count + 1)))],
    )
