import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ModelSelector from "./ModelSelector";

describe("ModelSelector", () => {
  it("renders both model options", () => {
    render(<ModelSelector currentModel="sonnet" onChange={jest.fn()} />);

    expect(screen.getByText("Claude Sonnet 4")).toBeInTheDocument();
    expect(screen.getByText("Claude Opus")).toBeInTheDocument();
  });

  it("marks sonnet as selected when currentModel is sonnet", () => {
    render(<ModelSelector currentModel="sonnet" onChange={jest.fn()} />);

    expect(screen.getByTestId("model-option-sonnet")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("model-option-opus")).toHaveAttribute("aria-checked", "false");
  });

  it("marks opus as selected when currentModel is opus", () => {
    render(<ModelSelector currentModel="opus" onChange={jest.fn()} />);

    expect(screen.getByTestId("model-option-sonnet")).toHaveAttribute("aria-checked", "false");
    expect(screen.getByTestId("model-option-opus")).toHaveAttribute("aria-checked", "true");
  });

  it("calls onChange with 'opus' when opus button is clicked", () => {
    const onChange = jest.fn();
    render(<ModelSelector currentModel="sonnet" onChange={onChange} />);

    fireEvent.click(screen.getByTestId("model-option-opus"));

    expect(onChange).toHaveBeenCalledWith("opus");
  });

  it("calls onChange with 'sonnet' when sonnet button is clicked", () => {
    const onChange = jest.fn();
    render(<ModelSelector currentModel="opus" onChange={onChange} />);

    fireEvent.click(screen.getByTestId("model-option-sonnet"));

    expect(onChange).toHaveBeenCalledWith("sonnet");
  });

  it("has accessible radiogroup role and label", () => {
    render(<ModelSelector currentModel="sonnet" onChange={jest.fn()} />);

    const group = screen.getByRole("radiogroup", { name: "Model selection" });
    expect(group).toBeInTheDocument();
  });

  it("has accessible labels on each option", () => {
    render(<ModelSelector currentModel="sonnet" onChange={jest.fn()} />);

    expect(screen.getByRole("radio", { name: "Claude Sonnet 4" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Claude Opus" })).toBeInTheDocument();
  });
});
