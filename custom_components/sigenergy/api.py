"""Sigenergy Cloud API client."""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    AUTH_URL_KEY,
    AUTH_URL_PASSWORD,
    DEVICE_LIST_URL,
    DEVICE_REALTIME_URL,
    ENERGY_FLOW_URL,
    ONBOARD_URL,
    OFFBOARD_URL,
    QUERY_MODE_URL,
    REALTIME_SUMMARY_URL,
    SWITCH_MODE_URL,
    SYSTEM_LIST_URL,
    SYSTEM_LIST_PAGE_URL,
    TOKEN_EXPIRY_BUFFER,
)

_LOGGER = logging.getLogger(__name__)


class SigenergyApiError(Exception):
    """Base exception for Sigenergy API errors."""

    def __init__(self, message: str = "", *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class SigenergyAuthError(SigenergyApiError):
    """Authentication error."""


class SigenergyRateLimitError(SigenergyApiError):
    """Rate limit exceeded."""


class SigenergyApi:
    """Client for the Sigenergy Cloud OpenAPI."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth_method: str,
        username: str | None = None,
        password: str | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
        base_url: str = API_BASE_URL,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._auth_method = auth_method
        self._username = username
        self._password = password
        self._app_key = app_key
        self._app_secret = app_secret
        self._base_url = base_url
        self._access_token: str | None = None
        self._token_expiry: float = 0

    @property
    def is_token_valid(self) -> bool:
        """Check if the current token is still valid."""
        return (
            self._access_token is not None
            and time.time() < self._token_expiry - TOKEN_EXPIRY_BUFFER
        )

    async def authenticate(self) -> None:
        """Authenticate and obtain an access token."""
        if self._auth_method == "password":
            await self._auth_password()
        else:
            await self._auth_key()

    async def _auth_password(self) -> None:
        """Authenticate using username and password."""
        url = f"{self._base_url}{AUTH_URL_PASSWORD}"
        payload = {
            "username": self._username,
            "password": self._password,
        }
        data = await self._raw_post(url, payload, authenticated=False)
        self._parse_token_response(data)

    async def _auth_key(self) -> None:
        """Authenticate using AppKey and AppSecret."""
        url = f"{self._base_url}{AUTH_URL_KEY}"
        key_string = f"{self._app_key}:{self._app_secret}"
        encoded_key = base64.b64encode(key_string.encode()).decode()
        payload = {"key": encoded_key}
        data = await self._raw_post(url, payload, authenticated=False)
        self._parse_token_response(data)

    def _parse_token_response(self, data: dict[str, Any]) -> None:
        """Parse the token from an auth response."""
        code = data.get("code", -1)
        if code != 0:
            msg = data.get("msg", "unknown error")
            if code in (11002, 11003):
                raise SigenergyAuthError(msg, code=code)
            raise SigenergyApiError(f"{msg} (code {code})", code=code)

        token_data = data.get("data")
        if isinstance(token_data, str):
            token_data = json.loads(token_data)

        self._access_token = token_data["accessToken"]
        expires_in = token_data.get("expiresIn", 43199)
        self._token_expiry = time.time() + expires_in
        _LOGGER.debug("Authentication successful, token expires in %s seconds", expires_in)

    async def _ensure_token(self) -> None:
        """Ensure we have a valid token."""
        if not self.is_token_valid:
            await self.authenticate()

    async def _raw_post(
        self,
        url: str,
        payload: dict[str, Any],
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Make a raw POST request."""
        headers = {"Content-Type": "application/json"}
        if authenticated:
            await self._ensure_token()
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with self._session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientResponseError as err:
            if err.status == 429:
                raise SigenergyRateLimitError("Rate limit exceeded") from err
            raise SigenergyApiError(f"API request failed: {err}") from err
        except aiohttp.ClientError as err:
            raise SigenergyApiError(f"Connection error: {err}") from err

    async def _raw_get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated GET request."""
        await self._ensure_token()
        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            async with self._session.get(
                url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientResponseError as err:
            if err.status == 429:
                raise SigenergyRateLimitError("Rate limit exceeded") from err
            raise SigenergyApiError(f"API request failed: {err}") from err
        except aiohttp.ClientError as err:
            raise SigenergyApiError(f"Connection error: {err}") from err

    def _check_response(self, data: dict[str, Any], url: str) -> dict[str, Any]:
        """Check API response for errors."""
        code = data.get("code", -1)
        if code == 1110:
            raise SigenergyRateLimitError("Interface is rate-limited")
        if code == 1201:
            raise SigenergyRateLimitError("Access restriction")
        if code in (11002, 11003):
            raise SigenergyAuthError(data.get("msg", "Auth error"))
        if code != 0:
            _LOGGER.warning("API error %s: %s (url=%s)", code, data.get("msg"), url)
        return data

    async def _api_get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated API GET request with error handling."""
        full_url = f"{self._base_url}{url}"
        data = await self._raw_get(full_url, params)
        return self._check_response(data, url)

    async def _api_post(
        self, url: str, payload: dict[str, Any] | list[str] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated API POST request with error handling."""
        if payload is None:
            payload = {}
        full_url = f"{self._base_url}{url}"
        data = await self._raw_post(full_url, payload)
        return self._check_response(data, url)

    @staticmethod
    def _parse_data(value: Any) -> Any:
        """Parse a value that may be a JSON-encoded string."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        if isinstance(value, list):
            return [SigenergyApi._parse_data(item) for item in value]
        return value

    # ── Inventory ──────────────────────────────────────────────

    async def get_system_list(self) -> list[dict[str, Any]]:
        """Get list of all authorized systems."""
        data = await self._api_get(SYSTEM_LIST_URL)
        result = self._parse_data(data.get("data", []))
        return result if isinstance(result, list) else []

    async def get_device_list(self, system_id: str) -> list[dict[str, Any]]:
        """Get list of devices for a system."""
        url = DEVICE_LIST_URL.format(system_id=system_id)
        data = await self._api_get(url, {"systemId": system_id})
        result = self._parse_data(data.get("data", []))
        # Also parse nested attrMap strings
        for device in result if isinstance(result, list) else []:
            if isinstance(device.get("attrMap"), str):
                device["attrMap"] = self._parse_data(device["attrMap"])
        return result if isinstance(result, list) else []

    # ── Realtime Data ──────────────────────────────────────────

    async def get_realtime_summary(self, system_id: str) -> dict[str, Any]:
        """Get realtime summary data for a system."""
        url = REALTIME_SUMMARY_URL.format(system_id=system_id)
        data = await self._api_get(url, {"systemId": system_id})
        return self._parse_data(data.get("data", {})) or {}

    async def get_energy_flow(self, system_id: str) -> dict[str, Any]:
        """Get realtime energy flow data for a system."""
        url = ENERGY_FLOW_URL.format(system_id=system_id)
        data = await self._api_get(url, {"systemId": system_id})
        return self._parse_data(data.get("data", {})) or {}

    async def get_device_realtime(
        self, system_id: str, serial_number: str
    ) -> dict[str, Any]:
        """Get realtime data for a specific device."""
        url = DEVICE_REALTIME_URL.format(
            system_id=system_id, serial_number=serial_number
        )
        data = await self._api_get(
            url, {"systemId": system_id, "serialNumber": serial_number}
        )
        return self._parse_data(data.get("data", {})) or {}

    # ── Instructions ───────────────────────────────────────────

    async def get_operating_mode(self, system_id: str) -> int | None:
        """Query current operating mode of a system."""
        url = QUERY_MODE_URL.format(system_id=system_id)
        data = await self._api_get(url, {"systemId": system_id})
        result = self._parse_data(data.get("data", {}))
        if isinstance(result, dict):
            return result.get("energyStorageOperationMode")
        return None

    async def set_operating_mode(
        self, system_id: str, mode: int
    ) -> dict[str, Any]:
        """Switch operating mode of a system."""
        url = SWITCH_MODE_URL.format(system_id=system_id)
        return await self._api_post(
            url,
            {"systemId": system_id, "energyStorageOperationMode": mode},
        )

    # ── Boarding ───────────────────────────────────────────────

    async def onboard(self, system_ids: list[str]) -> dict[str, Any]:
        """Onboard systems."""
        return await self._api_post(ONBOARD_URL, system_ids)

    async def offboard(self, system_ids: list[str]) -> dict[str, Any]:
        """Offboard systems."""
        return await self._api_post(OFFBOARD_URL, system_ids)

    # ── Validate credentials ───────────────────────────────────

    async def validate_credentials(self) -> None:
        """Test that credentials are valid by authenticating.

        Raises SigenergyAuthError / SigenergyApiError so callers can
        surface the server-provided message.
        """
        await self.authenticate()
