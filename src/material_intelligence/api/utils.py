import json
import base64
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from material_intelligence.config import QUESTIONNAIRE_DIR


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data):
        if not self._ignored and data.strip():
            self.parts.append(data.strip())


def fetch_product_link(url: str) -> tuple[str, str | None]:
    """Fetch readable product-page text and return an explicit failure if unavailable."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return "", "No valid HTTP(S) specification link was supplied."
    try:
        request = Request(url, headers={"User-Agent": "MaterialIntelligence/1.0"})
        with urlopen(request, timeout=15) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "text/plain"}:
                return "", f"The link returned unsupported content type: {content_type}."
            raw = response.read(2_000_000)
            encoding = response.headers.get_content_charset() or "utf-8"
        if content_type == "text/plain":
            text = raw.decode(encoding, errors="replace")
        else:
            parser = _TextExtractor()
            parser.feed(raw.decode(encoding, errors="replace"))
            text = "\n".join(parser.parts)
        return text[:100_000], None
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return "", f"Could not read the specification link: {exc}"


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
