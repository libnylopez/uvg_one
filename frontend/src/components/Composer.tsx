import { type FormEvent, type KeyboardEvent, useState } from "react";

interface ComposerProps {
  disabled: boolean;
  onSend: (question: string) => void;
}

const MAX_LENGTH = 2000;

export function Composer({ disabled, onSend }: ComposerProps) {
  const [value, setValue] = useState("");
  const trimmed = value.trim();

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter envía; Shift+Enter hace un salto de línea.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question" className="sr-only">
        Escribe tu pregunta
      </label>
      <textarea
        id="question"
        rows={1}
        value={value}
        maxLength={MAX_LENGTH}
        placeholder="Pregunta sobre carreras, admisión, calendario, reglamentos…"
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <button type="submit" disabled={disabled || !trimmed}>
        {disabled ? "Enviando…" : "Enviar"}
      </button>
    </form>
  );
}
