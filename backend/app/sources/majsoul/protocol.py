import hashlib
import json
from pathlib import Path


PROTOCOL_PATH = Path(__file__).with_name("protocol") / "liqi.json"
VERSION_URL = "https://game.maj-soul.com/1/version.json"


def descriptor_url(version: str, resversion: dict[str, object]) -> str:
    resources = resversion.get("res", resversion)
    if not isinstance(resources, dict):
        raise ValueError("invalid Mahjong Soul resource manifest")
    entry = resources["res/proto/liqi.json"]
    if not isinstance(entry, dict) or "prefix" not in entry:
        raise ValueError("invalid Mahjong Soul resource manifest")
    return f"https://game.maj-soul.com/1/{entry['prefix']}/res/proto/liqi.json"


def load_vendored_descriptor() -> dict[str, object]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def descriptor_sha256() -> str:
    return hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
