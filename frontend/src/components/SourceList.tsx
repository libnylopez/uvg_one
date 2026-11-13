import { documentLink } from "../api";
import type { SourceReference } from "../types";

function pages(source: SourceReference): string | null {
  if (source.page_number == null) return null;
  return source.page_end != null && source.page_end !== source.page_number
    ? `págs. ${source.page_number}–${source.page_end}`
    : `pág. ${source.page_number}`;
}

/** Documentos oficiales en que se apoya la respuesta, con enlace al PDF original. */
export function SourceList({ sources }: { sources: SourceReference[] }) {
  if (!sources.length) return null;
  return (
    <section className="sources" aria-label="Fuentes consultadas">
      <h3>{sources.length === 1 ? "Fuente" : `Fuentes (${sources.length})`}</h3>
      <ul>
        {sources.map((source, index) => {
          const pageLabel = pages(source);
          const title = source.document_title || source.document_name;
          return (
            <li key={`${source.document_name}-${source.section ?? ""}-${source.page_number ?? index}`}>
              <div className="source-text">
                <span className="source-title">{title}</span>
                {(source.section || pageLabel) && (
                  <span className="source-where">{[source.section, pageLabel].filter(Boolean).join(" · ")}</span>
                )}
              </div>
              {source.document_url && (
                <a
                  className="source-link"
                  href={documentLink(source.document_url, source.page_number)}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`Ver documento: ${title}${pageLabel ? `, ${pageLabel}` : ""}`}
                >
                  Ver documento{source.page_number ? ` · pág. ${source.page_number}` : ""} ↗
                </a>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
