"""Thin httpx wrapper for the Shopify Admin REST API.

Authenticates every request with X-Shopify-Access-Token. Maps HTTP
error codes to typed RuntimeExceptions so tool handlers can catch
specific failure modes.

Usage::

    async with ShopifyClient.from_env() as client:
        data = await client.get("/admin/api/2024-10/orders.json", {"name": "#1001"})
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class ShopifyAuthError(RuntimeError):
    """HTTP 401 / 403 from the Shopify API."""


class ShopifyNotFoundError(RuntimeError):
    """HTTP 404 from the Shopify API."""


class ShopifyClient:
    """Async REST client for the Shopify Admin API (2024-10 stable).

    Lifecycle: use as an async context manager::

        async with ShopifyClient("shop.myshopify.com", token) as client:
            ...

    Or manage it manually::

        client = ShopifyClient("shop.myshopify.com", token)
        await client.__aenter__()
        ...
        await client.__aexit__(None, None, None)
    """

    _BASE = "https://{domain}"
    _API_VERSION = "2024-10"

    def __init__(
        self, shop_domain: str, admin_token: str, timeout: float = 10.0
    ) -> None:
        if not shop_domain:
            raise ValueError("SHOPIFY_SHOP_DOMAIN is required")
        if not admin_token:
            raise ValueError("SHOPIFY_ADMIN_TOKEN is required")
        self._shop_domain = shop_domain.rstrip("/")
        self._admin_token = admin_token
        self._timeout = timeout
        self._http: httpx.AsyncClient | None = None

    @classmethod
    def from_env(cls) -> ShopifyClient:
        """Build from SHOPIFY_SHOP_DOMAIN and SHOPIFY_ADMIN_TOKEN env vars."""
        return cls(
            shop_domain=os.environ.get("SHOPIFY_SHOP_DOMAIN", ""),
            admin_token=os.environ.get("SHOPIFY_ADMIN_TOKEN", ""),
        )

    async def __aenter__(self) -> ShopifyClient:
        base_url = self._BASE.format(domain=self._shop_domain)
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "X-Shopify-Access-Token": self._admin_token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET *path* (relative to shop domain), returning decoded JSON."""
        if self._http is None:
            raise RuntimeError("ShopifyClient must be used as an async context manager")

        response = await self._http.get(path, params=params or {})
        return self._raise_for_status(response)

    def _raise_for_status(self, response: httpx.Response) -> Any:
        status = response.status_code
        if 200 <= status < 300:
            return response.json()
        body_preview = response.text[:200]
        msg = (
            f"Shopify API {response.request.method} {response.request.url}"
            f" → {status}: {body_preview}"
        )
        if status in (401, 403):
            raise ShopifyAuthError(msg)
        if status == 404:
            raise ShopifyNotFoundError(msg)
        raise RuntimeError(msg)
