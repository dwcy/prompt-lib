import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { useNewsFeed, useNewsItemState, useNewsSourceState, useRefreshNews } from "@/api/news";
import type { NewsItem } from "@/api/schemas";
import "./NewsModule.css";

export const NEWS_CATEGORIES = ["all", "ai-company", "repository", "research", "community", "security", "package", "breach", "cloud"] as const;

function readStoredIds(key: string): Set<string> {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "[]");
    return new Set(Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []);
  } catch {
    return new Set();
  }
}

function NewsCard({ item, read, saved, onRead, onSave }: { item: NewsItem; read: boolean; saved: boolean; onRead: () => void; onSave: () => void }) {
  return <article className={`news-card${read ? " is-read" : ""}`}>
    <div className="news-card__meta"><span>{item.source_name}</span><span>{item.category}</span>{item.published_at && <time dateTime={item.published_at}>{new Date(item.published_at).toLocaleString()}</time>}</div>
    <h3><a href={item.canonical_url} target="_blank" rel="noreferrer" onClick={onRead}>{item.title}</a></h3>
    {item.summary && <p>{item.summary}</p>}
    <footer><button type="button" onClick={onRead}>{read ? "Mark unread" : "Mark read"}</button><button type="button" onClick={onSave}>{saved ? "Unsave" : "Save"}</button>{item.security && <strong>Security advisory</strong>}{item.service && <strong>Service incident</strong>}</footer>
  </article>;
}

export function NewsModule() {
  const query = useNewsFeed();
  const refresh = useRefreshNews();
  const itemState = useNewsItemState();
  const sourceState = useNewsSourceState();
  const [category, setCategory] = useState("all");
  const [source, setSource] = useState("all");
  const [savedOnly, setSavedOnly] = useState(false);
  const [read, setRead] = useState<Set<string>>(() => readStoredIds("cabal-news-read"));
  const [saved, setSaved] = useState<Set<string>>(() => readStoredIds("cabal-news-saved"));
  useEffect(() => localStorage.setItem("cabal-news-read", JSON.stringify([...read])), [read]);
  useEffect(() => localStorage.setItem("cabal-news-saved", JSON.stringify([...saved])), [saved]);
  const payload = query.data;
  const items = useMemo(() => (payload?.items ?? []).filter((item) => (category === "all" || item.category === category) && (source === "all" || item.source_id === source) && (!savedOnly || saved.has(item.id))), [payload, category, source, savedOnly, saved]);
  const toggle = (set: Set<string>, id: string, update: (value: Set<string>) => void, field: "read" | "saved") => { const next = new Set(set); const value = !next.has(id); value ? next.add(id) : next.delete(id); update(next); itemState.mutate({ id, [field]: value }); };

  if (query.isLoading) return <div className="news-module"><p>Loading technology news…</p></div>;
  if (query.isError) return <div className="news-module"><EmptyState title="News feed unavailable" body="The local news service could not be reached." /></div>;
  return <div className="news-module">
    <header className="news-header"><div><span className="news-eyebrow">Signal desk</span><h2>AI technology news</h2><p>Curated releases, research, security advisories, breaches, Azure incidents, and Hacker News.</p></div><button type="button" onClick={() => refresh.mutate()} disabled={refresh.isPending}>{refresh.isPending ? "Refreshing…" : "Refresh"}</button></header>
    <div className="news-toolbar"><label>Category <select value={category} onChange={(e) => setCategory(e.target.value)}>{NEWS_CATEGORIES.map((value) => <option key={value} value={value}>{value === "all" ? "All categories" : value}</option>)}</select></label><label>Source <select value={source} onChange={(e) => setSource(e.target.value)}><option value="all">All sources</option>{payload?.sources.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label><label className="news-check"><input type="checkbox" checked={savedOnly} onChange={(e) => setSavedOnly(e.target.checked)} /> Saved only</label><span className="news-count">{items.length} items</span></div>
    <div className="news-health" aria-label="Source health">{payload?.sources.map((item) => <button type="button" key={item.id} className={`health-${item.health}${item.enabled === false ? " is-disabled" : ""}`} title={item.error_hint ?? item.name} onClick={() => sourceState.mutate({ id: item.id, enabled: item.enabled === false })}>{item.name}</button>)}</div>
    {items.length === 0 ? <EmptyState title="No matching stories" body="Try another category or source." /> : <div className="news-list">{items.map((item) => <NewsCard key={item.id} item={item} read={read.has(item.id)} saved={saved.has(item.id)} onRead={() => toggle(read, item.id, setRead, "read")} onSave={() => toggle(saved, item.id, setSaved, "saved")} />)}</div>}
  </div>;
}
