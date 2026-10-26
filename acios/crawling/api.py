"""Authenticated API routes for ACIOS's optional crawling toolkit."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from .catalog import integration_status
from .engine import CrawlExecutionError, CrawlSafetyError, ToolUnavailable, convert_document, crawl_url

router = APIRouter(tags=["crawling-toolkit"])
Strategy = Literal["auto", "firecrawl", "crawl4ai", "browser_use", "crawlee", "scrapy", "scrapling", "curl_impersonate", "autoscraper", "httpx"]


class CrawlWebRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: AnyHttpUrl
    strategy: Strategy = "auto"
    max_chars: int = Field(default=20_000, ge=500, le=50_000)
    wanted_list: list[str] | None = Field(default=None, max_length=10)
    browser_instruction: str | None = Field(default=None, max_length=500)


@router.get("/api/v1/tools/crawl-capabilities")
def list_crawling_integrations():
    """Report readiness for all ten tools without returning secret values."""
    return {"tools": integration_status()}


@router.post("/api/v1/tools/crawl-web")
async def crawl_web_page(request: CrawlWebRequest):
    """Extract one public page and return normalized content plus provider provenance."""
    try:
        result = await crawl_url(
            url=str(request.url),
            strategy=request.strategy,
            max_chars=request.max_chars,
            wanted_list=request.wanted_list,
            browser_instruction=request.browser_instruction,
        )
    except CrawlSafetyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ToolUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CrawlExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Crawling request failed safely.") from exc
    return {"status": "success", "result": result}


@router.post("/api/v1/tools/convert-document")
async def convert_document_endpoint(file: UploadFile = File(...)):
    """Convert a bounded uploaded document for the authenticated web cockpit."""
    filename = file.filename or "upload.bin"
    try:
        data = await file.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Document exceeds the 4 MB limit.")
        result = await asyncio.to_thread(convert_document, data, filename)
    except CrawlSafetyError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ToolUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CrawlExecutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
    return {"status": "success", "result": result}
