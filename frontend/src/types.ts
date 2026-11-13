// Contrato HTTP con el backend (esquemas Pydantic de backend/src/app/infrastructure/entrypoints/api).

export type AnswerStatus = "answered" | "abstained" | "smalltalk" | "no_documents" | "error";
export type Confidence = "high" | "medium" | "low";

export interface SourceReference {
  document_name: string;
  page_number: number | null;
  document_title?: string | null;
  section?: string | null;
  page_end?: number | null;
  document_id?: string | null;
  /** Ruta del backend que sirve el PDF original (p. ej. /documents/<id>/file). */
  document_url?: string | null;
}

export interface Usage {
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  model: string | null;
  simulated: boolean;
}

export interface AnswerResponse {
  message_id: string;
  conversation_id: string;
  answer_text: string;
  status: AnswerStatus;
  is_grounded: boolean | null;
  confidence: Confidence | null;
  created_at: string;
  sources: SourceReference[];
  search_query: string | null;
  intent: string;
  usage: Usage;
}

export interface HistoryMessage {
  id: string;
  role: "student" | "assistant";
  content: string;
  created_at: string;
  is_grounded: boolean | null;
  confidence: Confidence | null;
  sources: SourceReference[];
  status?: AnswerStatus | null;
}

export interface Conversation {
  id: string;
  created_at: string;
  messages: HistoryMessage[];
}

export interface GuestSession {
  user_id: string;
  session_token: string;
}

export interface Health {
  status: string;
  indexed_chunks: number;
  llm_configured: boolean;
  llm_model: string;
  llm_mode?: "real" | "simulado";
}

/** Un turno tal como lo muestra la interfaz. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: AnswerStatus;
  confidence?: Confidence | null;
  sources?: SourceReference[];
  pending?: boolean;
  simulated?: boolean;
}
