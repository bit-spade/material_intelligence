import json
import base64
import ipaddress
import socket
from html.parser import HTMLParser
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from material_intelligence.config import QUESTIONNAIRE_DIR


def pdf_text(data: bytes) -> str:
    parts = []
    length = 0
    for page in PdfReader(BytesIO(data)).pages:
        text = page.extract_text() or ""
        parts.append(text)
        length += len(text)
        if length >= 100_000:
            break
    return "\n".join(parts)[:100_000]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.pdf_links = []
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1
        if tag == "a" and not self._ignored:
            link = dict(attrs).get("href")
            if link and link.split("?", 1)[0].split("#", 1)[0].lower().endswith(".pdf"):
                self.pdf_links.append(link)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data):
        if not self._ignored and data.strip():
            self.parts.append(data.strip())


def _require_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
        raise ValueError("Use a public HTTP(S) product link.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in {80, 443}:
        raise ValueError("Use a standard HTTP(S) product link.")
    addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    if any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("Use a public HTTP(S) product link.")


class _PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_specification(url: str) -> tuple[str, list[str]]:
    _require_public_url(url)
    request = Request(url, headers={"User-Agent": "MaterialIntelligence/1.0"})
    with build_opener(_PublicRedirectHandler()).open(request, timeout=10) as response:
        content_type = response.headers.get_content_type()
        limit = 12_000_000 if content_type == "application/pdf" else 2_000_000
        raw = response.read(limit + 1)
        encoding = response.headers.get_content_charset() or "utf-8"
        base_url = response.geturl()
    if content_type == "application/pdf":
        if len(raw) > limit:
            raise ValueError("The linked PDF is too large. Upload an excerpt instead.")
        return pdf_text(raw), []
    if content_type not in {"text/html", "text/plain"}:
        raise ValueError("The link must point to an HTML page, plain text, or a PDF.")
    text = raw[:limit].decode(encoding, errors="replace")
    if content_type == "text/plain":
        return text[:100_000], []
    parser = _TextExtractor()
    parser.feed(text)
    links = list(dict.fromkeys(urljoin(base_url, link) for link in parser.pdf_links))
    return "\n".join(parser.parts)[:100_000], links


def fetch_product_link(url: str, *, include_linked_pdfs: bool = False) -> tuple[str, str | None]:
    """Read product evidence from a public specification link."""
    try:
        text, links = _read_specification(url)
    except HTTPError as exc:
        return "", f"The product link returned HTTP {exc.code}."
    except (URLError, OSError, LookupError, ValueError, PyPdfError):
        return "", "Could not read the specification link."
    linked_text = []
    if include_linked_pdfs:
        for link in links[:2]:
            document, _ = fetch_product_link(link)
            if document.strip():
                linked_text.append(f"Linked PDF ({link})\n{document[:20_000]}")
    evidence = "\n\n".join([text, *linked_text]).strip()
    return evidence, None if evidence else "The product link had no readable text."


def load_questionnaire(category: str):
    file_path = QUESTIONNAIRE_DIR / f"{category}.json"
    if not file_path.exists():
        from pathlib import Path
        alt_path = Path(__file__).resolve().parents[3] / "data" / f"{category}.json"
        if alt_path.exists():
            file_path = alt_path
    questionnaire = json.loads(file_path.read_text(encoding="utf-8"))
    return questionnaire

def attach(file):
    return {
        "type": "media",
        "mime_type": file.type,  
        "data": base64.b64encode(file.getvalue()).decode(),
    }
