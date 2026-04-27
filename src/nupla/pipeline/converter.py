"""DocConverter client — uploads PDFs and streams conversion progress."""

import json
import os
from typing import Any, Callable, Awaitable

import httpx

def _base_url() -> str:
    raw = os.environ.get("DOCCONVERTER_URL", "")
    return raw.rstrip("/").removesuffix("/api")


def _auth() -> httpx.BasicAuth | None:
    user = os.environ.get("DOCCONVERTER_USER", "")
    passwd = os.environ.get("DOCCONVERTER_PASS", "")
    if user and passwd:
        return httpx.BasicAuth(user, passwd)
    return None


async def download_pdf(url: str, timeout: float = 60) -> bytes:
    """Download a PDF from a URL, return raw bytes."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def _parse_sse_stream(response: httpx.Response):
    """Yield (event_type, data) tuples from an SSE response stream.

    Tolerates Content-Type: text/plain (DocConverter quirk).
    """
    event_type = ""
    data_lines: list[str] = []

    async for line in response.aiter_lines():
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
        elif line == "":
            # Empty line = end of event
            if event_type or data_lines:
                yield event_type or "message", "\n".join(data_lines)
                event_type = ""
                data_lines = []

    # Flush any trailing event without a final blank line
    if event_type or data_lines:
        yield event_type or "message", "\n".join(data_lines)


async def convert_pdf_stream(
    pdf_bytes: bytes,
    filename: str,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Upload a PDF to DocConverter's streaming endpoint.

    Calls *on_progress* for each SSE ``progress`` event.
    Returns the final ``ConversionResult`` dict.
    """
    base = _base_url()
    if not base:
        raise RuntimeError("DOCCONVERTER_URL is not configured")

    url = f"{base}/api/convert/stream"

    # SSE stream: no read timeout (result assembly for large PDFs can take many minutes)
    async with httpx.AsyncClient(auth=_auth(), timeout=httpx.Timeout(None, connect=30)) as client:
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        async with client.stream("POST", url, files=files) as response:
            response.raise_for_status()
            result: dict[str, Any] | None = None

            async for event_type, data in _parse_sse_stream(response):
                if event_type == "progress" and on_progress:
                    try:
                        parsed = json.loads(data)
                    except json.JSONDecodeError:
                        parsed = {"raw": data}
                    await on_progress(parsed)
                elif event_type == "result":
                    result = json.loads(data)

            if result is None:
                raise RuntimeError("DocConverter stream ended without a result event")
            return result


async def compare_documents(
    left_bytes: bytes,
    left_filename: str,
    right_bytes: bytes,
    right_filename: str,
) -> dict[str, Any]:
    """Upload two documents to DocConverter's compare endpoint, return CompareResult."""
    base = _base_url()
    if not base:
        raise RuntimeError("DOCCONVERTER_URL is not configured")

    url = f"{base}/api/compare"

    async with httpx.AsyncClient(auth=_auth(), timeout=httpx.Timeout(None, connect=30)) as client:
        files = {
            "left_file": (left_filename, left_bytes, "text/markdown"),
            "right_file": (right_filename, right_bytes, "text/markdown"),
        }
        resp = await client.post(url, files=files)
        resp.raise_for_status()
        return resp.json()


async def convert_pdf_sync(pdf_bytes: bytes, filename: str) -> dict[str, Any]:
    """Upload a PDF to DocConverter's synchronous endpoint."""
    base = _base_url()
    if not base:
        raise RuntimeError("DOCCONVERTER_URL is not configured")

    url = f"{base}/api/convert"

    async with httpx.AsyncClient(auth=_auth(), timeout=httpx.Timeout(300, connect=30)) as client:
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        resp = await client.post(url, files=files)
        resp.raise_for_status()
        return resp.json()
