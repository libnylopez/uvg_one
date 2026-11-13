import { api, ApiError } from "./api";

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("cliente de la API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("traduce un error del servidor a un mensaje para el usuario", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(500, { detail: "boom" })));
    await expect(api.health()).rejects.toMatchObject({ status: 500, message: expect.stringMatching(/servidor/) });
  });

  it("sin conexión informa que el backend no responde", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await api.health().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toMatch(/No hay conexión/);
  });

  it("si la sesión de invitado venció, abre otra y reintenta una sola vez", async () => {
    localStorage.setItem("uvg-one.session", "vencido");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { detail: "Sesión inválida" }))
      .mockResolvedValueOnce(json(201, { user_id: "u", session_token: "nuevo" }))
      .mockResolvedValueOnce(json(200, { answer_text: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    const answer = await api.ask("hola");

    expect(answer).toEqual({ answer_text: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe("Bearer nuevo");
  });

  it("una respuesta que tarda demasiado se corta con un mensaje claro", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url, init: RequestInit) =>
        new Promise((_resolve, reject) =>
          init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))),
        ),
      ),
    );
    const pending = api.health().catch((e) => e);
    await vi.advanceTimersByTimeAsync(16_000);
    const error = await pending;
    expect(error.message).toMatch(/tardó demasiado/);
    vi.useRealTimers();
  });
});
