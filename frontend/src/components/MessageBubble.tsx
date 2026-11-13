import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { normalizeMarkdown } from "../lib/normalize-markdown";
import type { ChatMessage } from "../types";
import { SourceList } from "./SourceList";

const STATUS_NOTE: Partial<Record<NonNullable<ChatMessage["status"]>, string>> = {
  abstained: "Sin evidencia suficiente en los documentos",
  error: "No se pudo completar la respuesta",
  no_documents: "Base de conocimiento vacía",
};

const CONFIDENCE_LABEL = { high: "Confianza alta", medium: "Confianza media", low: "Confianza baja" } as const;

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="message message-user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }

  if (message.pending) {
    return (
      <div className="message message-assistant" aria-live="polite">
        <div className="bubble bubble-pending">
          <span className="dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          Buscando en los documentos oficiales…
        </div>
      </div>
    );
  }

  const note = message.status ? STATUS_NOTE[message.status] : undefined;
  return (
    <div className={`message message-assistant status-${message.status ?? "answered"}`}>
      <div className="bubble">
        {message.simulated && (
          <div className="simulated-note">Simulación · respuesta armada localmente, no generada por Claude</div>
        )}
        {note && <div className="status-note">{note}</div>}
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeMarkdown(message.content)}</ReactMarkdown>
        </div>
        {message.status === "answered" && message.confidence && (
          <div className={`confidence confidence-${message.confidence}`}>{CONFIDENCE_LABEL[message.confidence]}</div>
        )}
        <SourceList sources={message.sources ?? []} />
      </div>
    </div>
  );
}
