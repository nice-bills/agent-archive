from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_NAME = "manifest.json"

LOC_NEWSPAPERS = "https://www.loc.gov/newspapers/"
LOC_REFERER = "https://www.loc.gov/newspapers/"
DEFAULT_QUERIES = [
    "secret meeting",
    "missing person",
    "mysterious death",
    "arrested night",
    "anonymous letter",
    "strange discovery",
    "robbery warehouse",
    "escaped prisoner",
]

USER_AGENT = "ArchiveDetective/0.1 (HF hackathon; public-domain research)"


@dataclass
class RawSnippet:
    snippet_id: str
    citation_url: str
    date: str
    publication: str
    title: str
    raw_ocr: str
    image_path: str | None
    image_url: str | None
    alto_url: str | None
    query: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slug(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len] or "snippet"


def _publication_from_title(title: str) -> str:
    # "Image 3 of Evening star (Washington, D.C.), March 14, 1912"
    m = re.search(r"of\s+(.+?),\s*(?:January|February|March|April|May|June|July|August|September|October|November|December|\d{4})", title, re.I)
    if m:
        return m.group(1).strip()
    return title.split(",")[0].replace("Image 1 of ", "").strip()[:120]


def _snippet_id(url: str, date: str) -> str:
    path = urlparse(url).path.strip("/").replace("/", "_")
    return _slug(f"{date}_{path}", 64)


def _best_iiif_url(image_urls: list[str] | None) -> str | None:
    if not image_urls:
        return None
    for u in image_urls:
        if "image-services/iiif" in u and "pct:12.5" in u:
            return u.split("#")[0]
    for u in image_urls:
        if "image-services/iiif" in u:
            return u.split("#")[0]
    return None


def _alto_url(image_urls: list[str] | None) -> str | None:
    if not image_urls:
        return None
    for u in image_urls:
        if "word-coordinates" in u or "alto_xml" in u:
            return u
    return None


def _description_text(description: Any) -> str:
    if isinstance(description, list):
        return "\n".join(str(x) for x in description if x).strip()
    if description:
        return str(description).strip()
    return ""


def _alto_to_text(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    ns = {"alto": "http://www.loc.gov/standards/alto/ns-v4#"}
    strings: list[str] = []
    for el in root.findall(".//alto:String", ns):
        content = el.attrib.get("CONTENT") or el.attrib.get("content")
        if content:
            strings.append(content)
    if strings:
        return " ".join(strings)
    for el in root.iter():
        if el.tag.endswith("String"):
            content = el.attrib.get("CONTENT") or el.attrib.get("content")
            if content:
                strings.append(content)
    return " ".join(strings)


def _fetch_alto_text(client: httpx.Client, alto_url: str) -> str:
    try:
        r = client.get(alto_url, timeout=45.0)
        r.raise_for_status()
        return _alto_to_text(r.content)
    except (httpx.HTTPError, OSError):
        return ""


def _download_image(client: httpx.Client, iiif_url: str, dest: Path) -> bool:
    try:
        r = client.get(iiif_url, timeout=60.0, follow_redirects=True)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except (httpx.HTTPError, OSError):
        return False


def resolve_snippet_image(row: dict[str, Any], raw_dir: Path) -> Path | None:
    """Return a local image path for a snippet, downloading from image_url if needed."""
    rel = row.get("image_path")
    if rel:
        for base in (raw_dir, raw_dir.parent.parent):
            candidate = base / rel
            if candidate.is_file():
                return candidate
    url = row.get("image_url")
    sid = row.get("snippet_id") or "snippet"
    if not url:
        return None
    dest = raw_dir / "images" / f"{sid}.jpg"
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    headers = {"User-Agent": USER_AGENT, "Referer": LOC_REFERER}
    with httpx.Client(headers=headers, timeout=httpx.Timeout(90.0, connect=20.0)) as client:
        if _download_image(client, url, dest):
            return dest
    return None


def _search_page(
    client: httpx.Client,
    query: str,
    *,
    count: int = 10,
    page: int = 1,
) -> list[dict[str, Any]]:
    params = {"fo": "json", "q": query, "c": count, "sp": page}
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            r = client.get(LOC_NEWSPAPERS, params=params)
            r.raise_for_status()
            data = r.json()
            return list(data.get("results") or [])
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_err = exc
            time.sleep(0.8 * (attempt + 1))
    if last_err:
        raise last_err
    return []


def _result_to_snippet(
    client: httpx.Client,
    item: dict[str, Any],
    query: str,
    images_dir: Path,
    raw_dir: Path,
    *,
    download_images: bool,
) -> RawSnippet | None:
    url = item.get("url") or ""
    if not url or "/resource/" not in url:
        return None
    date = str(item.get("date") or "unknown")
    title = str(item.get("title") or "Untitled")
    desc = _description_text(item.get("description"))
    image_urls = item.get("image_url")
    if not isinstance(image_urls, list):
        image_urls = [image_urls] if image_urls else []

    alto_url = _alto_url(image_urls)
    raw_ocr = desc
    if alto_url and len(raw_ocr) < 80:
        alto_text = _fetch_alto_text(client, alto_url)
        if len(alto_text) > len(raw_ocr):
            raw_ocr = alto_text

    raw_ocr = re.sub(r"\s+", " ", raw_ocr).strip()
    if len(raw_ocr) < 40:
        return None

    sid = _snippet_id(url, date)
    rel_image: str | None = None
    iiif = _best_iiif_url(image_urls)
    if download_images and iiif:
        ext = ".jpg"
        dest = images_dir / f"{sid}{ext}"
        if _download_image(client, iiif, dest):
            rel_image = str(dest.relative_to(raw_dir))

    return RawSnippet(
        snippet_id=sid,
        citation_url=url,
        date=date,
        publication=_publication_from_title(title),
        title=title,
        raw_ocr=raw_ocr[:8000],
        image_path=rel_image,
        image_url=iiif,
        alto_url=alto_url,
        query=query,
    )


def discover_snippets_on_disk(raw_dir: Path) -> list[dict[str, Any]]:
    """Load all snippet JSON files under raw_dir/snippets (ignores manifest)."""
    json_dir = raw_dir / "snippets"
    if not json_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(json_dir.glob("*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return rows


def rebuild_manifest_from_disk(raw_dir: Path) -> dict[str, Any]:
    """Rebuild manifest.json from snippet files on disk."""
    rows = discover_snippets_on_disk(raw_dir)
    ids = [r["snippet_id"] for r in rows if r.get("snippet_id")]
    manifest = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(ids),
        "snippets": ids,
        "rebuilt_from_disk": True,
    }
    (raw_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def fetch_snippets(
    *,
    queries: list[str] | None = None,
    target: int = 15,
    per_query: int = 5,
    out_dir: Path | None = None,
    download_images: bool = True,
    delay_s: float = 0.35,
) -> list[RawSnippet]:
    """Pull newspaper page snippets from LOC Chronicling America search."""
    out = out_dir or RAW_DIR
    json_dir = out / "snippets"
    images_dir = out / "images"
    json_dir.mkdir(parents=True, exist_ok=True)
    if download_images:
        images_dir.mkdir(parents=True, exist_ok=True)

    existing = load_raw_manifest(out)
    seen_urls: set[str] = {s.get("citation_url", "") for s in existing}
    collected: list[RawSnippet] = []
    search_queries = queries or DEFAULT_QUERIES
    errors: list[str] = []
    rejected_short = 0
    results_seen = 0

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": LOC_REFERER,
    }
    with httpx.Client(headers=headers, timeout=httpx.Timeout(90.0, connect=20.0)) as client:
        for query in search_queries:
            if len(collected) >= target:
                break
            try:
                results = _search_page(client, query, count=per_query)
                results_seen += len(results)
            except httpx.HTTPError as exc:
                errors.append(f"{query}: {exc}")
                time.sleep(1.0)
                continue
            for item in results:
                url = item.get("url") or ""
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                snippet = _result_to_snippet(
                    client,
                    item,
                    query,
                    images_dir,
                    out,
                    download_images=download_images,
                )
                if snippet is None:
                    rejected_short += 1
                    continue
                path = json_dir / f"{snippet.snippet_id}.json"
                path.write_text(
                    json.dumps(snippet.to_dict(), indent=2) + "\n",
                    encoding="utf-8",
                )
                collected.append(snippet)
                if len(collected) >= target:
                    break
                time.sleep(delay_s)

    if collected:
        all_ids = list({s["snippet_id"] for s in existing} | {s.snippet_id for s in collected})
        manifest = {
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "count": len(all_ids),
            "snippets": all_ids,
            "fetch_errors": errors[:10],
        }
        (out / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    elif errors:
        manifest_path = out / MANIFEST_NAME
        payload: dict[str, Any] = {"fetch_errors": errors[:10]}
        if manifest_path.is_file():
            payload = {**json.loads(manifest_path.read_text(encoding="utf-8")), **payload}
        else:
            payload["count"] = 0
            payload["snippets"] = []
        (out / MANIFEST_NAME).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    elif not collected and discover_snippets_on_disk(out):
        rebuild_manifest_from_disk(out)

    return collected


def load_raw_manifest(raw_dir: Path | None = None) -> list[dict[str, Any]]:
    base = raw_dir or RAW_DIR
    manifest_path = base / MANIFEST_NAME
    manifest_ids: list[str] = []
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_ids = list(manifest.get("snippets") or [])
        except json.JSONDecodeError:
            manifest_ids = []

    snippets: list[dict[str, Any]] = []
    for sid in manifest_ids:
        p = base / "snippets" / f"{sid}.json"
        if p.is_file():
            snippets.append(json.loads(p.read_text(encoding="utf-8")))

    disk = discover_snippets_on_disk(base)
    if not snippets and disk:
        rebuild_manifest_from_disk(base)
        snippets = disk
    return snippets
