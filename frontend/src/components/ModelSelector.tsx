/**
 * ModelSelector — toggle between Claude Sonnet 4 (default) and Claude Opus.
 *
 * Displays the currently selected model and calls onChange when the user
 * picks a different model.
 *
 * Validates: Requirements 2.1, 2.2, 2.4, 2.5
 */

import React from "react";

export interface ModelSelectorProps {
  currentModel: "sonnet" | "opus";
  onChange: (model: "sonnet" | "opus") => void;
}

const MODEL_LABELS: Record<"sonnet" | "opus", string> = {
  sonnet: "Claude Sonnet 4",
  opus: "Claude Opus",
};

const MODELS: Array<"sonnet" | "opus"> = ["sonnet", "opus"];

const styles = {
  container: {
    display: "flex",
    gap: 4,
    padding: "4px",
    borderRadius: 8,
    backgroundColor: "#f3f4f6",
  } as React.CSSProperties,
  button: (active: boolean): React.CSSProperties => ({
    padding: "6px 14px",
    borderRadius: 6,
    border: "none",
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
    backgroundColor: active ? "#ffffff" : "transparent",
    color: active ? "#111827" : "#6b7280",
    boxShadow: active ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
    transition: "all 0.15s ease",
  }),
};

export default function ModelSelector({ currentModel, onChange }: ModelSelectorProps) {
  return (
    <div
      data-testid="model-selector"
      style={styles.container}
      role="radiogroup"
      aria-label="Model selection"
    >
      {MODELS.map((model) => (
        <button
          key={model}
          data-testid={`model-option-${model}`}
          style={styles.button(currentModel === model)}
          role="radio"
          aria-checked={currentModel === model}
          aria-label={MODEL_LABELS[model]}
          onClick={() => onChange(model)}
        >
          {MODEL_LABELS[model]}
        </button>
      ))}
    </div>
  );
}
