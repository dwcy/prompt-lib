"""AI technology news feed routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from cabal.news_feed_service import refresh_sources
from cabal.webapi import security
from cabal.webapi.envelope import envelope_response, utc_now_iso

router = APIRouter(dependencies=[Depends(security.require_bearer_token)])


class SourceState(BaseModel):
    enabled: bool


class ItemState(BaseModel):
    read: bool | None = None
    saved: bool | None = None


def _items(request: Request) -> tuple[list[dict], list[dict]]:
    cached = getattr(request.app.state, "news_items", None)
    health = getattr(request.app.state, "news_health", None)
    if cached is not None and health is not None:
        return cached, health
    all_items, statuses = refresh_sources(request.app.state.storage.list_news_source_preferences())
    request.app.state.news_items = all_items
    request.app.state.news_health = statuses
    return all_items, statuses


@router.get("/api/news/sources")
def sources(request: Request):
    _, statuses = _items(request)
    return envelope_response(data={"sources": statuses}, source="news")


@router.get("/api/news/items")
def items(request: Request, source: str | None = None, category: str | None = None):
    values, statuses = _items(request)
    filtered = [item for item in values if (not source or item["source_id"] == source) and (not category or item["category"] == category)]
    states = request.app.state.storage.list_news_item_states()
    for item in filtered:
        state = states.get(item["id"], {})
        item["read"] = state.get("read", False)
        item["saved"] = state.get("saved", False)
    return envelope_response(data={"items": filtered, "sources": statuses}, source="news")


@router.post("/api/news/refresh")
def refresh(request: Request):
    request.app.state.news_items = None
    request.app.state.news_health = None
    values, statuses = _items(request)
    return envelope_response(data={"items": values, "sources": statuses, "refreshed": True}, source="news")


@router.post("/api/news/sources/{source_id}/state")
def source_state(source_id: str, payload: SourceState, request: Request):
    request.app.state.storage.set_news_source_enabled(source_id, payload.enabled, utc_now_iso())
    request.app.state.news_items = None
    request.app.state.news_health = None
    _, statuses = _items(request)
    return envelope_response(data={"sources": statuses}, source="news")


@router.post("/api/news/items/{item_id}/state")
def item_state(item_id: str, payload: ItemState, request: Request):
    request.app.state.storage.set_news_item_state(item_id, read=payload.read, saved=payload.saved, updated_at=utc_now_iso())
    state = request.app.state.storage.list_news_item_states().get(item_id, {"read": False, "saved": False})
    return envelope_response(data=state, source="news")
