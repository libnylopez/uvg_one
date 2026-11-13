import type { SourceReference } from "../types";

function location(source: SourceReference): string | null {
  const parts: string[] = [];
  if (source.section) parts.push(source.section);
  if (source.page_number != null) {
    parts.push(
      source.page_end != null && source.page_end !== source.page_number
        ? `págs. ${source.page_number}–${source.page_end}`
        : `pág. ${source.page_number}`,
    );
  }
  return parts.length ? parts.join(" · ") : null;
}

/** Documentos oficiales en que se apoya la respuesta. */
export function SourceList({ sources }: { sources: SourceReference[] }) {
  if (!sources.length) return null;
  return (
    <section className="sources" aria-label="Fuentes consultadas">
      <h3>{sources.length === 1 ? "Fuente" : `Fuentes (${sources.length})`}</h3>
      <ul>
        {sources.map((source, index) => {
          const where = location(source);
          return (
            <li key={`${source.document_name}-${source.section ?? ""}-${source.page_number ?? index}`}>
              <span className="source-title">{source.document_title || source.document_name}</span>
              {where && <span className="source-where">{where}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
