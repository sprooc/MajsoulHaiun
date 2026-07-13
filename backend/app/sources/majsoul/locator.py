import re
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict


RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,159}$")
ALLOWED_HOSTS = {"game.maj-soul.com", "mahjongsoul.game.yo-star.com"}


class MajsoulLocator(BaseModel):
    model_config = ConfigDict(frozen=True)

    original: str
    record_id: str
    account_token: str | None = None

    @classmethod
    def parse(cls, value: str) -> "MajsoulLocator":
        raw = value.strip()
        if not raw or len(raw) > 512:
            raise ValueError("invalid Mahjong Soul replay locator")
        parsed = urlparse(raw)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
                raise ValueError("invalid Mahjong Soul replay locator")
            paipu = parse_qs(parsed.query).get("paipu", [""])[0]
        else:
            paipu = raw
        base, *suffixes = paipu.split("_")
        if not RECORD_ID.fullmatch(base):
            raise ValueError("invalid Mahjong Soul replay locator")
        account = next((suffix[1:] for suffix in suffixes if suffix.startswith("a") and suffix[1:].isdigit()), None)
        return cls(original=raw, record_id=base, account_token=account)
