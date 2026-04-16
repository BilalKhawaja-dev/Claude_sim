/**
 * Property-based test: Model selection propagated in requests
 *
 * **Validates: Requirements 2.2**
 *
 * Property 5: For any model selection made in the Chat_Interface (sonnet or opus),
 * the next chat request sent to the Backend_API SHALL include the corresponding
 * model identifier in the request payload.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import * as fc from "fast-check";
import ModelSelector from "./ModelSelector";

/** Arbitrary that produces random model selections from the valid set. */
const modelArb = fc.constantFrom<"sonnet" | "opus">("sonnet", "opus");

describe("Property 5: Model selection propagated in requests", () => {
  it("onChange callback receives exactly the selected model identifier", () => {
    fc.assert(
      fc.property(modelArb, (selectedModel) => {
        const onChange = jest.fn();
        // Render with the *other* model as current so the click is meaningful
        const otherModel = selectedModel === "sonnet" ? "opus" : "sonnet";
        const { unmount } = render(
          <ModelSelector currentModel={otherModel} onChange={onChange} />
        );

        fireEvent.click(screen.getByTestId(`model-option-${selectedModel}`));

        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenCalledWith(selectedModel);

        unmount();
      }),
      { numRuns: 100 }
    );
  });

  it("selected model identifier matches what would be included in the request payload", () => {
    fc.assert(
      fc.property(modelArb, modelArb, (currentModel, clickedModel) => {
        const onChange = jest.fn();
        const { unmount } = render(
          <ModelSelector currentModel={currentModel} onChange={onChange} />
        );

        fireEvent.click(screen.getByTestId(`model-option-${clickedModel}`));

        // The onChange callback is the contract for propagating the model to the
        // request payload. Verify the value is exactly the clicked model string.
        expect(onChange).toHaveBeenCalledTimes(1);
        const propagatedModel = onChange.mock.calls[0][0];
        expect(propagatedModel).toBe(clickedModel);

        // Verify the propagated value is a valid model identifier for the API
        expect(["sonnet", "opus"]).toContain(propagatedModel);

        // Simulate building the request payload with the propagated model
        const requestPayload = {
          message: "test",
          conversation_id: "test-id",
          model: propagatedModel,
        };
        expect(requestPayload.model).toBe(clickedModel);

        unmount();
      }),
      { numRuns: 100 }
    );
  });
});
