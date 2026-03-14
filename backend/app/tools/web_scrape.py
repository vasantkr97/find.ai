from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from app.core.config import get_settings
from app.core.errors import ToolValidationError
from app.core.utils import truncate
from app.schemas.types import ParameterDef, ToolResult
from app.tools.base import BaseTool, ToolDefinition

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "::1"}


def _safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname or ""
        if host in BLOCKED_HOSTS:
            return False
        if host.endswith(".internal") or host.endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass
        return True
    except Exception:  # noqa: BLE001
        return False


class WebScrapeArgs(BaseModel):
    url: HttpUrl
    maxLength: int | None = Field(default=None, ge=100, le=50_000)


class WebScrapeTool(BaseTool):
    definition = ToolDefinition(
        name="web_scrape",
        description="Fetch and extract text content from a specific webpage URL.",
        parameters={
            "url": ParameterDef(type="string", description="The URL to scrape", required=True),
            "maxLength": ParameterDef(
                type="number", description="Max characters of content to return (default: 8000)"
            ),
        },
    )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            parsed = WebScrapeArgs.model_validate(args)
        except ValidationError as err:
            raise ToolValidationError("web_scrape", str(err)) from err

        url = str(parsed.url)
        if not _safe_url(url):
            return ToolResult(
                success=False,
                error="URL is not allowed (blocked host or protocol)",
            )

        cfg = get_settings()
        max_len = parsed.maxLength or cfg.WEB_SCRAPE_MAX_LENGTH
        timeout = cfg.WEB_SCRAPE_TIMEOUT_MS / 1000

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, trust_env=False) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; ArchonBot/1.0; +https://archon.dev)",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
            if response.status_code >= 400:
                return ToolResult(success=False, error=f"HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return ToolResult(
                    success=False,
                    error=f"Unsupported content type: {content_type}",
                )
            html = response.text
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "svg"]):
                tag.decompose()

            title = soup.title.get_text(strip=True) if soup.title else ""
            meta_desc = ""
            desc_node = soup.select_one('meta[name="description"]')
            if desc_node:
                desc_value = desc_node.get("content")
                if isinstance(desc_value, str):
                    meta_desc = desc_value

            content = ""
            for selector in ["article", "main", '[role="main"]', ".content", "#content"]:
                node = soup.select_one(selector)
                if node:
                    content = node.get_text(" ", strip=True)
                    break
            if not content and soup.body:
                content = soup.body.get_text(" ", strip=True)

            cleaned = " ".join(content.split())
            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "title": title,
                    "description": meta_desc,
                    "content": truncate(cleaned, max_len),
                    "contentLength": len(cleaned),
                },
            )
        except Exception as err:  # noqa: BLE001
            return ToolResult(success=False, error=f"Scrape failed: {err}")


web_scrape_tool = WebScrapeTool()
