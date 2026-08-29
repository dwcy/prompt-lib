"""Curated external news sources and safe, dependency-free feed normalization."""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class FeedSource:
    id: str
    name: str
    category: str
    endpoint: str
    format: str = "rss"
    capabilities: tuple[str, ...] = ("articles",)


@dataclass
class FeedItem:
    id: str
    source_id: str
    source_name: str
    category: str
    title: str
    canonical_url: str
    summary: str = ""
    published_at: str | None = None
    tags: list[str] = field(default_factory=list)
    security: dict[str, Any] | None = None
    service: dict[str, Any] | None = None


def _source(id: str, name: str, category: str, endpoint: str, *, fmt: str = "rss", capabilities: tuple[str, ...] = ("articles",)) -> FeedSource:
    return FeedSource(id, name, category, endpoint, fmt, capabilities)


CURATED_SOURCES: tuple[FeedSource, ...] = (
    _source("openai", "OpenAI", "ai-company", "https://openai.com/news/rss.xml"),
    _source("anthropic", "Anthropic", "ai-company", "https://www.anthropic.com/news/rss.xml"),
    _source("google-deepmind", "Google DeepMind", "ai-company", "https://deepmind.google/blog/rss.xml"),
    _source("microsoft-ai", "Microsoft AI", "ai-company", "https://blogs.microsoft.com/ai/feed/"),
    _source("nvidia", "NVIDIA AI", "ai-company", "https://blogs.nvidia.com/blog/category/ai/feed/"),
    _source("deepseek", "DeepSeek", "ai-company", "https://api.github.com/orgs/deepseek-ai/repos", fmt="json", capabilities=("releases",)),
    _source("huggingface", "Hugging Face", "ai-company", "https://huggingface.co/blog/feed.xml"),
    _source("mistral", "Mistral AI", "ai-company", "https://mistral.ai/news/rss.xml"),
    _source("meta-ai", "Meta AI", "ai-company", "https://engineering.fb.com/feed/"),
    _source("aws-ai", "AWS Machine Learning", "ai-company", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    _source("arxiv-ai", "arXiv AI", "research", "https://rss.arxiv.org/rss/cs.AI"),
    _source("hacker-news", "Hacker News", "community", "https://news.ycombinator.com/rss"),
    _source("cisa-kev", "CISA Known Exploited Vulnerabilities", "security", "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", fmt="json", capabilities=("advisories",)),
    _source("nvd", "NVD Vulnerabilities", "security", "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml"),
    _source("github-advisories", "GitHub Security Advisories", "security", "https://github.com/security-advisories.atom", fmt="atom", capabilities=("advisories", "packages")),
    _source("osv", "OSV.dev", "package", "https://osv.dev/blog.rss", capabilities=("advisories", "packages")),
    _source("krebsonsecurity", "Krebs on Security", "breach", "https://krebsonsecurity.com/feed/", capabilities=("breaches",)),
    _source("bleepingcomputer", "BleepingComputer", "breach", "https://www.bleepingcomputer.com/feed/", capabilities=("breaches",)),
    _source("azure-status", "Azure Status", "cloud", "https://azure.status.microsoft/en-us/status/feed/", capabilities=("incidents",)),
    _source("kubernetes", "Kubernetes Releases", "repository", "https://github.com/kubernetes/kubernetes/releases.atom", fmt="atom", capabilities=("releases",)),
    _source("ollama", "Ollama Releases", "repository", "https://github.com/ollama/ollama/releases.atom", fmt="atom", capabilities=("releases",)),
)


def source_payload(source: FeedSource, *, health: str = "ready", error_hint: str | None = None) -> dict[str, Any]:
    return {**asdict(source), "capabilities": list(source.capabilities), "health": health, "error_hint": error_hint}


def _clean_text(value: str | None, limit: int = 700) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.astimezone(timezone.utc).isoformat()


def _child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(node):
        if child.tag.rsplit("}", 1)[-1] in names and child.text:
            return child.text
    return ""


def normalize_xml(source: FeedSource, body: bytes) -> list[FeedItem]:
    root = ET.fromstring(body)
    items: list[FeedItem] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
            continue
        title = _clean_text(_child_text(node, ("title",)))
        url = _child_text(node, ("link", "id")).strip()
        if not url:
            for child in list(node):
                if child.tag.rsplit("}", 1)[-1] == "link" and child.attrib.get("href"):
                    url = child.attrib["href"]
                    break
        if not title or not url or not url.startswith(("http://", "https://")):
            continue
        item_id = sha256(f"{source.id}:{url}".encode()).hexdigest()[:20]
        items.append(FeedItem(item_id, source.id, source.name, source.category, title, url, _clean_text(_child_text(node, ("description", "summary", "content"))), _date(_child_text(node, ("pubDate", "published", "updated"))), list(source.capabilities)))
    return items


def normalize_json(source: FeedSource, body: bytes) -> list[FeedItem]:
    payload = json.loads(body)
    rows = payload.get("vulnerabilities", []) if isinstance(payload, dict) else payload
    items: list[FeedItem] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        identifier = row.get("cveID") or row.get("id") or row.get("name")
        if not identifier:
            continue
        url = row.get("url") or f"https://nvd.nist.gov/vuln/detail/{identifier}"
        title = row.get("shortDescription") or row.get("description") or f"{source.name}: {identifier}"
        item_id = sha256(f"{source.id}:{url}".encode()).hexdigest()[:20]
        items.append(FeedItem(item_id, source.id, source.name, source.category, _clean_text(title), url, _clean_text(row.get("description") or row.get("shortDescription")), _date(row.get("dateAdded") or row.get("published")), list(source.capabilities), security={"identifier": identifier, "package": row.get("product"), "severity": row.get("severity")}))
    return items


def fetch_source(source: FeedSource, timeout: float = 5.0) -> tuple[list[FeedItem], str | None]:
    request = urllib.request.Request(source.endpoint, headers={"User-Agent": "Cabal-AI-News/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(1_500_000)
        if source.format in {"rss", "atom"}:
            return normalize_xml(source, body), None
        return normalize_json(source, body), None
    except (OSError, ET.ParseError, ValueError) as exc:
        return [], f"Source unavailable: {type(exc).__name__}"
