import type { AnswerResponse, Conversation, GuestSession, Health } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8010";
const TOKEN_KEY = "uvg-one.session";
// Una respuesta pasa por recuperación + hasta dos llamadas a Claude: se da margen.
const CHAT_TIMEOUT_MS = 90_000;
const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function humanMessage(status: number, detail: string | null): string {
  if (status === 0) return "No hay conexión con el servidor de UVG ONE. Verifica que el backend esté en ejecución.";
  if (status === 401) return "Tu sesión expiró. Inténtalo de nuevo.";
  if (status === 422) return detail ?? "La pregunta no es válida.";
  if (status === 429) return "Demasiadas solicitudes seguidas. Espera un momento.";
  if (status >= 500) return "El servidor tuvo un problema. Inténtalo de nuevo en unos segundos.";
  return detail ?? "No se pudo completar la solicitud.";
}

async function request<T>(path: string, init: RequestInit & { token?: string; timeoutMs?: number } = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init.token) headers.Authorization = `Bearer ${init.token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "La respuesta tardó demasiado. Inténtalo de nuevo.");
    }
    throw new ApiError(0, humanMessage(0, null));
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail: string | null = null;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : null;
    } catch {
      // cuerpo no JSON
    }
    throw new ApiError(response.status, humanMessage(response.status, detail));
  }
  return (await response.json()) as T;
}

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function storeToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // almacenamiento no disponible: la sesión dura lo que dure la pestaña
  }
}

let memoryToken: string | null = null;

/** Modo invitado: reutiliza la sesión guardada o abre una nueva sin registro. */
export async function ensureSession(forceNew = false): Promise<string> {
  if (!forceNew) {
    const existing = memoryToken ?? readToken();
    if (existing) return (memoryToken = existing);
  }
  const session = await request<GuestSession>("/auth/guest", { method: "POST" });
  memoryToken = session.session_token;
  storeToken(memoryToken);
  return memoryToken;
}

/** Ejecuta una llamada autenticada; si la sesión caducó, abre otra y reintenta una vez. */
async function withSession<T>(call: (token: string) => Promise<T>): Promise<T> {
  try {
    return await call(await ensureSession());
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return call(await ensureSession(true));
    }
    throw error;
  }
}

export const api = {
  health: () => request<Health>("/health"),
  ask: (question: string) =>
    withSession((token) =>
      request<AnswerResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({ question }),
        token,
        timeoutMs: CHAT_TIMEOUT_MS,
      }),
    ),
  history: () => withSession((token) => request<Conversation[]>("/chat/history", { token })),
  newConversation: () => ensureSession(true),
};
