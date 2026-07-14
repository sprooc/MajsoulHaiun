from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from ms import protocol_pb2 as pb
from ms.base import MSRPCChannel
from ms.rpc import Lobby


_PRODUCT_VERSION_PATTERNS = (
    re.compile(r'productVersion\s*:\s*["\']([^"\']+)["\']'),
    re.compile(r'WebGL-[^-"\']+-(\d+(?:\.\d+)+)\('),
)


class MajsoulClientError(Exception):
    pass


class MajsoulLoginRejected(MajsoulClientError):
    pass


class MajsoulRecordUnavailable(MajsoulClientError):
    pass


class MajsoulGatewayError(MajsoulClientError):
    pass


class MajsoulProtocolError(MajsoulClientError):
    pass


def extract_client_version(index_html: str) -> str:
    for pattern in _PRODUCT_VERSION_PATTERNS:
        match = pattern.search(index_html)
        if match is not None:
            return match.group(1)
    raise MajsoulGatewayError("Mahjong Soul client version could not be discovered.")


def _websocket_endpoint(route: dict[str, Any]) -> str:
    domain = route.get("domain")
    if not isinstance(domain, str) or not domain:
        raise MajsoulGatewayError("Mahjong Soul gateway response was invalid.")
    scheme = "wss" if route.get("ssl", True) else "ws"
    return f"{scheme}://{domain.rstrip('/')}/gateway"


class MajsoulClient:
    def __init__(
        self,
        *,
        host: str,
        timeout_seconds: float,
        http_client: httpx.AsyncClient,
        channel_factory: Callable[[str], Any] = MSRPCChannel,
        lobby_factory: Callable[[Any], Any] = Lobby,
    ):
        self.host = host.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client
        self.channel_factory = channel_factory
        self.lobby_factory = lobby_factory
        self.channel: Any | None = None
        self.lobby: Any | None = None
        self.client_version = ""
        self.resource_version = ""

    async def fetch_record(self, record_id: str, username: str, password: str) -> bytes:
        try:
            await self._connect()
            await self._login(username.strip(), password)
            return await self._download(record_id)
        finally:
            await self._close_safely()

    async def _wait(self, awaitable: Any) -> Any:
        try:
            return await asyncio.wait_for(awaitable, timeout=self.timeout_seconds)
        except TimeoutError as exc:
            raise MajsoulGatewayError("Mahjong Soul request timed out.") from exc

    async def _get(self, url: str, *, params: dict[str, str] | None = None) -> httpx.Response:
        try:
            response = await self._wait(self.http_client.get(url, params=params))
            response.raise_for_status()
            return response
        except MajsoulClientError:
            raise
        except (httpx.HTTPError, AttributeError, TypeError) as exc:
            raise MajsoulGatewayError("Mahjong Soul gateway request failed.") from exc

    async def _connect(self) -> None:
        try:
            homepage = await self._get(f"{self.host}/1/")
            self.client_version = extract_client_version(homepage.text)

            version_response = await self._get(f"{self.host}/1/version.json")
            self.resource_version = str(version_response.json()["version"])
            config_response = await self._get(f"{self.host}/1/v{self.resource_version}/config.json")
            config = config_response.json()
            endpoint = await self._discover_endpoint(config)
        except MajsoulClientError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise MajsoulGatewayError("Mahjong Soul gateway configuration was invalid.") from exc

        self.channel = self.channel_factory(endpoint)
        self.lobby = self.lobby_factory(self.channel)
        try:
            await self._wait(self.channel.connect(self.host))
        except MajsoulClientError:
            raise
        except Exception as exc:
            raise MajsoulGatewayError("Mahjong Soul WebSocket connection failed.") from exc

    async def _discover_endpoint(self, config: dict[str, Any]) -> str:
        ip_entries = config.get("ip") or []
        if not isinstance(ip_entries, list) or not ip_entries or not isinstance(ip_entries[0], dict):
            raise MajsoulGatewayError("Mahjong Soul gateway configuration was invalid.")
        ip_info = ip_entries[0]
        gateways = [
            item["url"].rstrip("/")
            for item in ip_info.get("gateways", [])
            if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"]
        ]
        legacy_regions = [
            item["url"].rstrip("/")
            for item in ip_info.get("region_urls", [])
            if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"]
        ]

        for gateway_url in gateways:
            try:
                response = await self._get(
                    f"{gateway_url}/api/clientgate/routes",
                    params={"platform": "Web", "version": self.client_version, "lang": "chs_t"},
                )
                routes = response.json().get("data", {}).get("routes", [])
                usable = [route for route in routes if isinstance(route, dict) and route.get("state") != "busy"]
                candidates = usable or [route for route in routes if isinstance(route, dict)]
                if candidates:
                    best_level = min(int(route.get("level", 0)) for route in candidates)
                    best = next(route for route in candidates if int(route.get("level", 0)) == best_level)
                    return _websocket_endpoint(best)
            except (MajsoulGatewayError, AttributeError, TypeError, ValueError):
                continue

        if gateways:
            parsed = urlparse(gateways[0])
            if parsed.netloc:
                return f"wss://{parsed.netloc}/gateway"

        for region_url in legacy_regions:
            try:
                response = await self._get(
                    region_url,
                    params={"service": "ws-gateway", "protocol": "ws", "ssl": "true"},
                )
                servers = response.json().get("servers", [])
                if isinstance(servers, list) and servers:
                    return f"wss://{servers[0]}/gateway"
            except (MajsoulGatewayError, AttributeError, TypeError):
                continue

        raise MajsoulGatewayError("Mahjong Soul gateway could not be discovered.")

    async def _login(self, username: str, password: str) -> None:
        if self.lobby is None:
            raise MajsoulProtocolError("Mahjong Soul client is not connected.")
        request = pb.ReqLogin()
        request.account = username
        request.password = hmac.new(b"lailai", password.encode(), hashlib.sha256).hexdigest()
        request.device.is_browser = True
        request.device.platform = "pc"
        request.device.hardware = "pc"
        request.device.software = "web"
        request.random_key = str(uuid.uuid1())
        request.gen_access_token = True
        request.client_version_string = f"web-{self.client_version}"
        request.client_version.package = self.client_version
        request.client_version.resource = self.resource_version
        request.currency_platforms.append(2)
        try:
            response = await self._wait(self.lobby.login(request))
        except MajsoulClientError:
            raise
        except Exception as exc:
            raise MajsoulGatewayError("Mahjong Soul login request failed.") from exc
        if response.error.code or not response.access_token:
            raise MajsoulLoginRejected("Mahjong Soul account login was rejected.")

    async def _download(self, record_id: str) -> bytes:
        if self.lobby is None:
            raise MajsoulProtocolError("Mahjong Soul client is not connected.")
        request = pb.ReqGameRecord(
            game_uuid=record_id,
            client_version_string=f"web-{self.client_version}",
        )
        try:
            response = await self._wait(self.lobby.fetch_game_record(request))
        except MajsoulClientError:
            raise
        except Exception as exc:
            raise MajsoulGatewayError("Mahjong Soul replay request failed.") from exc
        if response.error.code == 1203:
            raise MajsoulRecordUnavailable("Mahjong Soul replay is unavailable to this account.")
        if response.error.code:
            raise MajsoulProtocolError(f"Mahjong Soul replay request failed with code {response.error.code}.")
        wrapper = pb.Wrapper(name=".lq.ResGameRecord", data=response.SerializeToString())
        return wrapper.SerializeToString()

    async def _close_safely(self) -> None:
        if self.channel is None:
            return
        try:
            await self.channel.close()
        except Exception:
            pass
