import hashlib
import json
import struct
from typing import Any

from app.errors import AppError
from app.sources.majsoul.protocol import load_vendored_descriptor


DecodedMajsoulGame = dict[str, Any]

VARINT_TYPES = {"bool", "int32", "int64", "uint32", "uint64", "sint32", "sint64", "enum"}
FIXED32_TYPES = {"fixed32", "sfixed32", "float"}
FIXED64_TYPES = {"fixed64", "sfixed64", "double"}
PRIMITIVE_TYPES = VARINT_TYPES | FIXED32_TYPES | FIXED64_TYPES | {"string", "bytes"}


def _read_varint(payload: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(payload) and shift < 70:
        byte = payload[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
    raise ValueError("invalid protobuf varint")


def _zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _decode_varint(value: int, field_type: str) -> int | bool:
    if field_type == "bool":
        return bool(value)
    if field_type in {"sint32", "sint64"}:
        return _zigzag(value)
    if field_type == "int32":
        value &= 0xFFFFFFFF
        return value - (1 << 32) if value >= 1 << 31 else value
    if field_type == "int64" and value >= 1 << 63:
        return value - (1 << 64)
    return value


def _skip_field(payload: bytes, offset: int, wire_type: int) -> int:
    if wire_type == 0:
        _, offset = _read_varint(payload, offset)
        return offset
    if wire_type == 1:
        return offset + 8
    if wire_type == 2:
        length, offset = _read_varint(payload, offset)
        return offset + length
    if wire_type == 5:
        return offset + 4
    raise ValueError(f"unsupported protobuf wire type: {wire_type}")


class DescriptorDecoder:
    def __init__(self, descriptor: dict[str, object]):
        try:
            root = descriptor["nested"]["lq"]["nested"]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid Mahjong Soul descriptor") from exc
        if not isinstance(root, dict):
            raise ValueError("invalid Mahjong Soul descriptor")
        self.types: dict[str, dict[str, object]] = {}
        self._index(root)

    def _index(self, definitions: dict[str, object], prefix: str = "") -> None:
        for name, raw_definition in definitions.items():
            if not isinstance(raw_definition, dict):
                continue
            qualified = f"{prefix}.{name}" if prefix else name
            if "fields" in raw_definition or "values" in raw_definition:
                self.types[qualified] = raw_definition
                self.types.setdefault(name, raw_definition)
            nested = raw_definition.get("nested")
            if isinstance(nested, dict):
                self._index(nested, qualified)

    def _resolve(self, name: str) -> dict[str, object] | None:
        normalized = name.removeprefix(".").removeprefix("lq.")
        return self.types.get(normalized) or self.types.get(normalized.split(".")[-1])

    def decode(self, type_name: str, payload: bytes) -> dict[str, Any]:
        definition = self._resolve(type_name)
        if not definition or not isinstance(definition.get("fields"), dict):
            raise ValueError(f"unknown protobuf type: {type_name}")
        fields = {
            int(field["id"]): (name, field)
            for name, field in definition["fields"].items()  # type: ignore[union-attr]
            if isinstance(field, dict) and "id" in field
        }
        result: dict[str, Any] = {}
        offset = 0
        while offset < len(payload):
            key, offset = _read_varint(payload, offset)
            field_id, wire_type = key >> 3, key & 0x07
            field_entry = fields.get(field_id)
            if field_entry is None:
                offset = _skip_field(payload, offset, wire_type)
                continue
            name, field = field_entry
            field_type = str(field.get("type", "bytes"))
            target_definition = self._resolve(field_type)
            is_enum = bool(target_definition and "values" in target_definition)
            effective_type = "enum" if is_enum else field_type

            if wire_type == 0:
                raw_value, offset = _read_varint(payload, offset)
                value: Any = _decode_varint(raw_value, effective_type)
            elif wire_type == 1:
                raw = payload[offset : offset + 8]
                offset += 8
                value = struct.unpack("<d" if field_type == "double" else "<Q", raw)[0]
            elif wire_type == 5:
                raw = payload[offset : offset + 4]
                offset += 4
                value = struct.unpack("<f" if field_type == "float" else "<I", raw)[0]
            elif wire_type == 2:
                length, offset = _read_varint(payload, offset)
                raw = payload[offset : offset + length]
                offset += length
                if field_type == "string":
                    value = raw.decode("utf-8", errors="replace")
                elif field_type == "bytes":
                    value = raw
                elif effective_type in VARINT_TYPES and field.get("rule") == "repeated":
                    packed: list[Any] = []
                    packed_offset = 0
                    while packed_offset < len(raw):
                        raw_value, packed_offset = _read_varint(raw, packed_offset)
                        packed.append(_decode_varint(raw_value, effective_type))
                    value = packed
                elif effective_type in FIXED32_TYPES and field.get("rule") == "repeated":
                    fmt = "<f" if field_type == "float" else "<I"
                    value = [struct.unpack(fmt, raw[index : index + 4])[0] for index in range(0, len(raw), 4)]
                elif effective_type in FIXED64_TYPES and field.get("rule") == "repeated":
                    fmt = "<d" if field_type == "double" else "<Q"
                    value = [struct.unpack(fmt, raw[index : index + 8])[0] for index in range(0, len(raw), 8)]
                elif target_definition and "fields" in target_definition:
                    value = self.decode(field_type, raw)
                else:
                    value = raw
            else:
                offset = _skip_field(payload, offset, wire_type)
                continue

            if field.get("rule") == "repeated":
                values = value if isinstance(value, list) and wire_type == 2 and effective_type in PRIMITIVE_TYPES else [value]
                result.setdefault(name, []).extend(values)
            else:
                result[name] = value
        return result


def _unwrap_record(decoder: DescriptorDecoder, payload: bytes) -> tuple[str, dict[str, Any], int | None]:
    wrapper = decoder.decode("Wrapper", payload)
    name = str(wrapper.get("name", ""))
    data = wrapper.get("data", b"")
    if name.startswith(".lq.") and isinstance(data, bytes):
        return name, decoder.decode(name, data), None
    prototype = decoder.decode("ActionPrototype", payload)
    name = str(prototype.get("name", ""))
    data = prototype.get("data", b"")
    if not name.startswith(".lq.") or not isinstance(data, bytes):
        raise ValueError("invalid Mahjong Soul record wrapper")
    return name, decoder.decode(name, data), int(prototype.get("step", 0))


def _normalize_action(name: str, data: dict[str, Any], sequence: int) -> dict[str, Any]:
    if name.endswith("RecordNewRound"):
        data["dealer"] = int(data.get("ju", 0))
        data["dora"] = data.get("dora") or next(iter(data.get("doras", [])), None)
        data["tiles"] = [list(data.get(f"tiles{seat}", [])) for seat in range(4)]
    elif name.endswith("RecordHule"):
        hules = data.get("hules") if isinstance(data.get("hules"), list) else []
        data["winners"] = [int(hule.get("seat", 0)) for hule in hules if isinstance(hule, dict)]
        delta = data.get("delta_scores") if isinstance(data.get("delta_scores"), list) else []
        negative = [index for index, value in enumerate(delta) if value < 0]
        data["loser"] = min(negative, key=lambda index: delta[index]) if negative else None
        data["ura_doras"] = [
            tile
            for hule in hules
            if isinstance(hule, dict)
            for tile in hule.get("li_doras", [])
        ]
    elif name.endswith("RecordNoTile"):
        players = data.get("players") if isinstance(data.get("players"), list) else []
        data["tenpai"] = [
            seat for seat, player in enumerate(players) if isinstance(player, dict) and player.get("tingpai")
        ]
        score_entries = data.get("scores") if isinstance(data.get("scores"), list) else []
        score_entry = next((entry for entry in score_entries if isinstance(entry, dict) and entry.get("delta_scores")), {})
        data["delta_scores"] = list(score_entry.get("delta_scores", []))
    return {"name": name, "data": data, "sequence": sequence}


def _binary_to_game(payload: bytes, descriptor: dict[str, object]) -> DecodedMajsoulGame:
    decoder = DescriptorDecoder(descriptor)
    head: dict[str, Any] = {}
    try:
        outer = decoder.decode("Wrapper", payload)
        outer_name = str(outer.get("name", ""))
        outer_data = outer.get("data")
        if outer_name.endswith("ResGameRecord") and isinstance(outer_data, bytes):
            response = decoder.decode("ResGameRecord", outer_data)
            head = response.get("head") if isinstance(response.get("head"), dict) else {}
            detail_data = response.get("data")
            if not isinstance(detail_data, bytes):
                raise ValueError("replay response does not contain game data")
            possible_wrapper = decoder.decode("Wrapper", detail_data)
            if str(possible_wrapper.get("name", "")).endswith("GameDetailRecords") and isinstance(possible_wrapper.get("data"), bytes):
                details = decoder.decode("GameDetailRecords", possible_wrapper["data"])
            else:
                details = decoder.decode("GameDetailRecords", detail_data)
        elif outer_name.endswith("GameDetailRecords") and isinstance(outer_data, bytes):
            details = decoder.decode("GameDetailRecords", outer_data)
        else:
            details = decoder.decode("GameDetailRecords", payload)
    except (ValueError, KeyError) as exc:
        raise AppError("INVALID_REPLAY_DATA", "Invalid Mahjong Soul protobuf container.", status_code=422) from exc

    wrapped_records: list[bytes] = []
    wrapped_records.extend(record for record in details.get("records", []) if isinstance(record, bytes))
    for action in details.get("actions", []):
        if isinstance(action, dict) and isinstance(action.get("result"), bytes):
            wrapped_records.append(action["result"])

    actions: list[dict[str, Any]] = []
    for sequence, record in enumerate(wrapped_records):
        try:
            name, data, record_step = _unwrap_record(decoder, record)
        except ValueError:
            actions.append({"name": ".lq.UnknownRecord", "data": {"raw_hex": record.hex()}, "sequence": sequence})
            continue
        actions.append(_normalize_action(name, data, record_step if record_step is not None else sequence))

    rounds: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_scores: list[int] = []
    for action in actions:
        data = action["data"]
        if action["name"].endswith("RecordNewRound"):
            chang = int(data.get("chang", 0))
            winds = ["east", "south", "west", "north"]
            current_scores = [int(value) for value in data.get("scores", current_scores)]
            current = {
                "wind": winds[chang] if chang < len(winds) else "east",
                "hand": int(data.get("ju", 0)) + 1,
                "dealer": int(data.get("ju", 0)),
                "honba": int(data.get("ben", 0)),
                "riichi_sticks": int(data.get("liqibang", 0)),
                "starting_scores": list(current_scores),
                "actions": [],
            }
            rounds.append(current)
        if current is None:
            current = {
                "wind": "east",
                "hand": 1,
                "dealer": 0,
                "honba": 0,
                "riichi_sticks": 0,
                "starting_scores": list(current_scores),
                "actions": [],
            }
            rounds.append(current)
        current["actions"].append(action)
        if action["name"].endswith("RecordHule"):
            if isinstance(data.get("scores"), list) and data["scores"]:
                current_scores = [int(value) for value in data["scores"]]
            elif isinstance(data.get("delta_scores"), list) and len(data["delta_scores"]) == len(current_scores):
                current_scores = [score + int(delta) for score, delta in zip(current_scores, data["delta_scores"])]

    head_accounts = head.get("accounts") if isinstance(head.get("accounts"), list) else []
    player_count = len(head_accounts) or (len(rounds[0].get("starting_scores", [])) if rounds else 0)
    if player_count not in {3, 4}:
        seats = [
            int(action["data"]["seat"])
            for action in actions
            if isinstance(action.get("data"), dict) and "seat" in action["data"]
        ]
        player_count = max(seats, default=3) + 1
    player_count = 3 if player_count == 3 else 4
    result = head.get("result") if isinstance(head.get("result"), dict) else {}
    result_players = result.get("players") if isinstance(result.get("players"), list) else []
    if result_players:
        ordered_results = sorted(
            (item for item in result_players if isinstance(item, dict)),
            key=lambda item: int(item.get("seat", 0)),
        )
        if len(ordered_results) == player_count:
            current_scores = [int(item.get("total_point", 0)) for item in ordered_results]
    if not current_scores:
        current_scores = [35000 if player_count == 3 else 25000] * player_count
    ranks = [rank + 1 for rank, _ in sorted(enumerate(current_scores), key=lambda item: (-item[1], item[0]))]
    final_ranks = [ranks.index(seat + 1) + 1 for seat in range(player_count)]
    accounts = [
        {
            "seat": int(account.get("seat", index)),
            "nickname": str(account.get("nickname", f"P{index + 1}")),
            "account_id": account.get("account_id"),
            "level_id": (
                account.get("level", {}).get("id")
                if isinstance(account.get("level"), dict)
                else None
            ),
        }
        for index, account in enumerate(head_accounts)
        if isinstance(account, dict)
    ]
    if len(accounts) != player_count:
        accounts = [{"seat": seat, "nickname": f"P{seat + 1}"} for seat in range(player_count)]
    config = head.get("config") if isinstance(head.get("config"), dict) else {}
    mode = config.get("mode") if isinstance(config.get("mode"), dict) else {}
    detail_rule = mode.get("detail_rule") if isinstance(mode.get("detail_rule"), dict) else {}
    return {
        "external_id": str(head.get("uuid") or hashlib.sha256(payload).hexdigest()[:24]),
        "accounts": accounts,
        "rules": {
            "player_count": player_count,
            "tsumo_loss": bool(detail_rule.get("have_zimosun")) if "have_zimosun" in detail_rule else None,
            "initial_score": detail_rule.get("init_point"),
        },
        "final_scores": current_scores,
        "final_ranks": final_ranks,
        "rounds": rounds,
    }


def decode_majsoul(payload: bytes, descriptor: dict[str, object] | None = None) -> DecodedMajsoulGame:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _binary_to_game(payload, descriptor or load_vendored_descriptor())
    if not isinstance(decoded, dict):
        raise AppError("INVALID_REPLAY_DATA", "Replay root must be an object.", status_code=422)
    return decoded
