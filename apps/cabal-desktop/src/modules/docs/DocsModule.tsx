// Docs reference module: README summary + docs/ markdown listing, console two-column layout.
import { useState } from "react";
import { useDocContent, useDocs } from "@/api/docs";
import { EmptyState } from "@/components/EmptyState";
import "./DocsModule.css";

export function DocsModule() {
  const docs = useDocs();
  const [openPath, setOpenPath] = useState<string | null>(null);
  const content = useDocContent(openPath);

  if (docs.isPending) {
    return <EmptyState title="Loading docs…" />;
  }
  if (docs.isError) {
    return <EmptyState title="Could not load docs" body={docs.error.message} />;
  }

  const { readme, documents } = docs.data;
  const viewing = openPath !== null ? documents.find((doc) => doc.path === openPath) : undefined;

  return (
    <div className="docs-module">
      <section className="docs-card docs-card--readme">
        {viewing ? (
          <>
            <header className="docs-card__header">
              <h2>{viewing.name}</h2>
              <button type="button" className="docs-back" onClick={() => setOpenPath(null)}>
                ← Back to README
              </button>
            </header>
            {content.isPending ? (
              <EmptyState title="Loading document…" />
            ) : content.isError ? (
              <EmptyState title="Could not load document" body={content.error.message} />
            ) : (
              <pre className="docs-content">{content.data.content}</pre>
            )}
          </>
        ) : readme ? (
          <>
            <header className="docs-card__header">
              <h2>{readme.title}</h2>
              <span className="docs-meta">
                {readme.path} · {readme.line_count} lines
              </span>
            </header>
            <pre className="docs-content">{readme.content}</pre>
          </>
        ) : (
          <EmptyState title="No README found in this project" />
        )}
      </section>

      <aside className="docs-card docs-card--list">
        <header className="docs-card__header">
          <h2>docs/</h2>
          <span className="docs-meta">{documents.length} documents</span>
        </header>
        {documents.length === 0 ? (
          <EmptyState title="No docs/ markdown files in this project" />
        ) : (
          <ul className="docs-list">
            {documents.map((doc) => (
              <li key={doc.path}>
                <button
                  type="button"
                  className={`docs-list__item${doc.path === openPath ? " is-active" : ""}`}
                  onClick={() => setOpenPath(doc.path)}
                >
                  <span className="docs-list__name">{doc.name}</span>
                  <span className="docs-list__desc">{doc.description}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
