import asyncio
import hashlib
import hmac

import httpx
import pytest
from ms import protocol_pb2 as pb

from app.sources.majsoul.client import (
    MajsoulClient,
    MajsoulGatewayError,
    MajsoulLoginRejected,
    MajsoulRecordUnavailable,
    extract_client_version,
)


RECORD_ID = "260714-ec4c890c-abec-4758-9337-2bce7085dbe6"
HOST = "https://game.maj-soul.com"


class FakeHttpClient:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def get(self, url: str, *, params: dict[str, str] | None = None, timeout: float | None = None):
        self.calls.append((url, params))
        request = httpx.Request("GET", url, params=params)
        if url == f"{HOST}/1/":
            return httpx.Response(200, text='productVersion: "4.0.45"', request=request)
        if url == f"{HOST}/1/version.json":
            return httpx.Response(200, json={"version": "0.11.252.w"}, request=request)
        if url == f"{HOST}/1/v0.11.252.w/config.json":
            return httpx.Response(
                200,
                json={
                    "ip": [
                        {
                            "gateways": [{"url": "https://gateway.example"}],
                            "region_urls": [{"url": "https://legacy.example"}],
                        }
                    ]
                },
                request=request,
            )
        if url == "https://gateway.example/api/clientgate/routes":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "routes": [
                            {"domain": "busy.example", "ssl": True, "state": "busy", "level": 0},
                            {"domain": "route.example", "ssl": True, "state": "open", "level": 1},
                        ]
                    }
                },
                request=request,
            )
        raise AssertionError(f"unexpected URL: {url}")


class HangingHttpClient:
    async def get(self, *_args, **_kwargs):
        await asyncio.sleep(1)


class FakeChannel:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.origin: str | None = None
        self.closed = False

    async def connect(self, origin: str):
        self.origin = origin

    async def close(self):
        self.closed = True


class FakeLobby:
    def __init__(self):
        self.login_request: pb.ReqLogin | None = None
        self.record_request: pb.ReqGameRecord | None = None
        self.login_response = pb.ResLogin(access_token="access-token")
        self.record_response = pb.ResGameRecord()
        self.record_response.head.uuid = RECORD_ID
        self.record_response.data = b"game-details"

    async def login(self, request: pb.ReqLogin):
        self.login_request = request
        return self.login_response

    async def fetch_game_record(self, request: pb.ReqGameRecord):
        self.record_request = request
        return self.record_response


def build_client(
    *,
    http_client: object | None = None,
    lobby: FakeLobby | None = None,
    timeout_seconds: float = 1,
) -> tuple[MajsoulClient, list[FakeChannel], FakeLobby]:
    channels: list[FakeChannel] = []
    resolved_lobby = lobby or FakeLobby()

    def channel_factory(endpoint: str):
        channel = FakeChannel(endpoint)
        channels.append(channel)
        return channel

    client = MajsoulClient(
        host=HOST,
        timeout_seconds=timeout_seconds,
        http_client=http_client or FakeHttpClient(),
        channel_factory=channel_factory,
        lobby_factory=lambda _channel: resolved_lobby,
    )
    return client, channels, resolved_lobby


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('productVersion: "4.0.45"', "4.0.45"),
        ("Build/chs_t-WebGL-release-4.0.45(45).loader.js", "4.0.45"),
    ],
)
def test_extracts_current_unity_product_version(html: str, expected: str):
    assert extract_client_version(html) == expected


def test_rejects_homepage_without_client_version():
    with pytest.raises(MajsoulGatewayError):
        extract_client_version("<html></html>")


async def test_fetch_record_returns_wrapped_res_game_record_and_closes_channel():
    client, channels, lobby = build_client()

    payload = await client.fetch_record(RECORD_ID, "account", "plain-secret")

    wrapper = pb.Wrapper.FromString(payload)
    response = pb.ResGameRecord.FromString(wrapper.data)
    assert wrapper.name == ".lq.ResGameRecord"
    assert response.head.uuid == RECORD_ID
    assert response.data == b"game-details"
    assert channels[0].endpoint == "wss://route.example/gateway"
    assert channels[0].origin == HOST
    assert channels[0].closed is True
    assert lobby.record_request is not None
    assert lobby.record_request.game_uuid == RECORD_ID
    assert lobby.record_request.client_version_string == "web-4.0.45"


async def test_login_request_hashes_password_and_uses_current_web_metadata():
    client, _, lobby = build_client()

    await client.fetch_record(RECORD_ID, " account ", "plain-secret")

    request = lobby.login_request
    assert request is not None
    assert request.account == "account"
    assert request.password == hmac.new(b"lailai", b"plain-secret", hashlib.sha256).hexdigest()
    assert request.password != "plain-secret"
    assert request.device.is_browser is True
    assert request.device.platform == "pc"
    assert request.client_version.package == "4.0.45"
    assert request.client_version_string == "web-4.0.45"
    assert list(request.currency_platforms) == [2]
    assert "plain-secret" not in repr(client)


async def test_record_error_1203_is_account_specific_and_closes_channel():
    lobby = FakeLobby()
    lobby.record_response.error.code = 1203
    client, channels, _ = build_client(lobby=lobby)

    with pytest.raises(MajsoulRecordUnavailable):
        await client.fetch_record(RECORD_ID, "account", "plain-secret")

    assert channels[0].closed is True


async def test_login_rejection_is_account_specific_and_closes_channel():
    lobby = FakeLobby()
    lobby.login_response.error.code = 1002
    lobby.login_response.access_token = ""
    client, channels, _ = build_client(lobby=lobby)

    with pytest.raises(MajsoulLoginRejected):
        await client.fetch_record(RECORD_ID, "account", "plain-secret")

    assert channels[0].closed is True


async def test_http_timeout_is_reported_as_gateway_error():
    client, channels, _ = build_client(http_client=HangingHttpClient(), timeout_seconds=0.01)

    with pytest.raises(MajsoulGatewayError):
        await client.fetch_record(RECORD_ID, "account", "plain-secret")

    assert channels == []
