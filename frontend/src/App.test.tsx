import { render, screen } from "@testing-library/react";

import { MessageBubble } from "./components/MessageBubble";

describe("MessageBubble", () => {
  it("muestra la respuesta en Markdown, la fuente y el enlace al PDF en la página citada", () => {
    render(
      <MessageBubble
        message={{
          id: "1",
          role: "assistant",
          content: "Los requisitos son:\n- **Título** de diversificado",
          status: "answered",
          confidence: "high",
          sources: [
            {
              document_name: "a.pdf",
              document_title: "Proceso de Admisión",
              section: "Requisitos",
              page_number: 2,
              document_url: "/documents/abc/file",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("Título")).toBeInTheDocument();
    expect(screen.getByText("Proceso de Admisión")).toBeInTheDocument();
    expect(screen.getByText("Requisitos · pág. 2")).toBeInTheDocument();
    expect(screen.getByText("Confianza alta")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Ver documento: Proceso de Admisión/ });
    expect(link).toHaveAttribute("href", "http://localhost:8010/documents/abc/file#page=2");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("sin página conocida enlaza el documento sin inventar una ubicación", () => {
    render(
      <MessageBubble
        message={{
          id: "3", role: "assistant", content: "x", status: "answered",
          sources: [{ document_name: "b.pdf", document_title: "Folleto", page_number: null, document_url: "/documents/b/file" }],
        }}
      />,
    );
    expect(screen.getByRole("link")).toHaveAttribute("href", "http://localhost:8010/documents/b/file");
    expect(screen.queryByText(/pág\./)).not.toBeInTheDocument();
  });

  it("señala una abstención sin fuentes", () => {
    render(<MessageBubble message={{ id: "2", role: "assistant", content: "No encontré información.", status: "abstained", sources: [] }} />);
    expect(screen.getByText("Sin evidencia suficiente en los documentos")).toBeInTheDocument();
    expect(screen.queryByLabelText("Fuentes consultadas")).not.toBeInTheDocument();
  });

  it("identifica claramente una respuesta simulada", () => {
    render(<MessageBubble message={{ id: "4", role: "assistant", content: "x", status: "answered", simulated: true }} />);
    expect(screen.getByText(/no generada por Claude/)).toBeInTheDocument();
  });

  it("muestra el indicador de carga mientras espera", () => {
    render(<MessageBubble message={{ id: "5", role: "assistant", content: "", pending: true }} />);
    expect(screen.getByText(/Buscando en los documentos oficiales/)).toBeInTheDocument();
  });
});
