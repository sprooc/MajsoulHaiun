#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "backend/app/sources/majsoul/protocol/liqi.json"
METADATA = OUTPUT.with_suffix(".sha256.json")
BASE = "https://game.maj-soul.com/1/"


def get_json(url: str) -> dict:
    with urlopen(url, timeout=20) as response:  # noqa: S310 - fixed trusted upstream
        return json.load(response)


def main() -> None:
    version_payload = get_json(BASE + "version.json")
    version = str(version_payload["version"])
    resources = get_json(BASE + f"resversion{version}.json")
    resource_map = resources.get("res", resources)
    entry = resource_map["res/proto/liqi.json"]
    descriptor_url = BASE + f"{entry['prefix']}/res/proto/liqi.json"
    with urlopen(descriptor_url, timeout=20) as response:  # noqa: S310 - fixed trusted upstream
        payload = response.read()
    json.loads(payload)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(payload)
    METADATA.write_text(
        json.dumps(
            {"version": version, "url": descriptor_url, "sha256": hashlib.sha256(payload).hexdigest()},
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
