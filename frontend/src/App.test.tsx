import { render, screen } from "@testing-library/react";

import { MessageBubble } from "./components/MessageBubble";

describe("MessageBubble", () => {
  it("muestra la respuesta en Markdown y sus fuentes", () => {
    render(
      <MessageBubble
        message={{
          id: "1",
          role: "assistant",
          content: "Los requisitos son:\n- **Título** de diversificado",
          status: "answered",
          confidence: "high",
          sources: [{ document_name: "a.pdf", document_title: "Proceso de Admisión", section: "Requisitos", page_number: 2 }],
        }}
      />,
    );
    expect(screen.getByText("Título")).toBeInTheDocument();
    expect(screen.getByText("Proceso de Admisión")).toBeInTheDocument();
    expect(screen.getByText("Requisitos · pág. 2")).toBeInTheDocument();
    expect(screen.getByText("Confianza alta")).toBeInTheDocument();
  });

  it("señala una abstención sin fuentes", () => {
    render(<MessageBubble message={{ id: "2", role: "assistant", content: "No encontré información.", status: "abstained", sources: [] }} />);
    expect(screen.getByText("Sin evidencia suficiente en los documentos")).toBeInTheDocument();
    expect(screen.queryByLabelText("Fuentes consultadas")).not.toBeInTheDocument();
  });
});
