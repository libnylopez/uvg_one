import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "./api";
import { Composer } from "./components/Composer";
import { MessageBubble } from "./components/MessageBubble";
import type { ChatMessage, Conversation, Health } from "./types";

// Preguntas que los documentos indexados sí responden.
const SUGGESTIONS = [
  "¿Qué carreras ofrece la UVG Altiplano?",
  "¿Cuáles son los pasos para inscribirme como estudiante de primer ingreso?",
  "¿Cuánto cuesta cada nivel del programa de inglés?",
  "¿Qué tipos de ayuda financiera existen?",
  "¿Cuándo es la Feria de becas II?",
  "¿Cómo armo un club en la universidad?",
];

let localId = 0;
const nextId = () => `local-${++localId}`;

function fromHistory(conversation: Conversation | undefined): ChatMessage[] {
  if (!conversation) return [];
  return conversation.messages.map((message) => ({
    id: message.id,
    role: message.role === "student" ? "user" : "assistant",
    content: message.content,
    confidence: message.confidence,
    sources: message.sources,
    status:
      message.role === "student"
        ? undefined
        : (message.status ??
          (message.is_grounded === true ? "answered" : message.is_grounded === false ? "abstained" : "smalltalk")),
  }));
}

export function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setConnectionError(null);
    } catch (error) {
      setHealth(null);
      setConnectionError(error instanceof ApiError ? error.message : "No hay conexión con el servidor.");
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    // Restaura la conversación de esta sesión de invitado al recargar la página.
    api
      .history()
      .then((conversations) => setMessages(fromHistory(conversations[0])))
      .catch(() => undefined);
  }, [refreshHealth]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function send(question: string) {
    const pendingId = nextId();
    setMessages((current) => [
      ...current,
      { id: nextId(), role: "user", content: question },
      { id: pendingId, role: "assistant", content: "", pending: true },
    ]);
    setSending(true);
    try {
      const answer = await api.ask(question);
      setMessages((current) =>
        current.map((message) =>
          message.id === pendingId
            ? {
                id: answer.message_id,
                role: "assistant",
                content: answer.answer_text,
                status: answer.status,
                confidence: answer.confidence,
                sources: answer.sources,
                simulated: answer.usage?.simulated ?? false,
              }
            : message,
        ),
      );
    } catch (error) {
      const text = error instanceof ApiError ? error.message : "Ocurrió un error inesperado. Inténtalo de nuevo.";
      setMessages((current) =>
        current.map((message) =>
          message.id === pendingId ? { id: pendingId, role: "assistant", content: text, status: "error" } : message,
        ),
      );
      void refreshHealth();
    } finally {
      setSending(false);
    }
  }

  async function newConversation() {
    try {
      await api.newConversation();
      setMessages([]);
    } catch (error) {
      setConnectionError(error instanceof ApiError ? error.message : "No se pudo iniciar una conversación nueva.");
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <img src="/logo-uvg-altiplano.png" alt="" className="logo" />
          <div>
            <h1>UVG ONE</h1>
            <p>Asistente universitario inteligente · Campus Altiplano</p>
          </div>
        </div>
        <button type="button" className="secondary" onClick={newConversation} disabled={sending}>
          Nueva conversación
        </button>
      </header>

      {health?.llm_mode === "simulado" && (
        <div className="banner banner-simulation" role="status">
          <strong>MODO SIMULACIÓN.</strong> Las respuestas se arman localmente con el texto recuperado de los
          documentos; no las genera Claude. Solo para pruebas o demostración sin conexión.
        </div>
      )}
      {connectionError && <div className="banner banner-error">{connectionError}</div>}
      {health && !health.llm_configured && (
        <div className="banner banner-warning">
          Falta configurar la API key de Anthropic en el archivo <code>.env</code>: el asistente puede buscar en los
          documentos, pero no redactar respuestas.
        </div>
      )}
      {health && health.indexed_chunks === 0 && (
        <div className="banner banner-warning">
          Todavía no hay documentos indexados. Agrega PDF a <code>documentos_uvg/</code>.
        </div>
      )}

      <main className="thread">
        {messages.length === 0 ? (
          <div className="welcome">
            <h2>¡Hola! Soy UVG ONE</h2>
            <p>
              Pregúntame sobre carreras, admisión, calendario académico, ayudas financieras o grupos estudiantiles de la
              UVG Campus Altiplano. Respondo solo con sus documentos oficiales y puedes abrir cada fuente para
              verificarla.
            </p>
            <p className="welcome-hint">Prueba con una de estas preguntas:</p>
            <div className="suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => send(suggestion)} disabled={sending}>
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => <MessageBubble key={message.id} message={message} />)
        )}
        <div ref={endRef} />
      </main>

      <footer className="footer">
        <Composer disabled={sending} onSend={send} />
        <p className="disclaimer">
          Prototipo académico del curso de Inteligencia Artificial · No es un servicio oficial de la UVG ·{" "}
          {health
            ? `${health.indexed_chunks} fragmentos indexados · ${health.llm_mode === "simulado" ? "simulación" : health.llm_model}`
            : "Conectando con el servidor…"}
        </p>
      </footer>
    </div>
  );
}
