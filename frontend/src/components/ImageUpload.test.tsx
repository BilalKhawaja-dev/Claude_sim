import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ImageUpload from "./ImageUpload";

const defaultProps = {
  onUpload: jest.fn(),
  maxSizeMB: 5,
  acceptedFormats: ["image/png", "image/jpeg", "image/gif", "image/webp"],
};

function createFile(name: string, size: number, type: string): File {
  const buffer = new ArrayBuffer(size);
  return new File([buffer], name, { type });
}

function selectFile(input: HTMLElement, file: File) {
  fireEvent.change(input, { target: { files: [file] } });
}

describe("ImageUpload", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders upload label and hidden file input", () => {
    render(<ImageUpload {...defaultProps} />);

    expect(screen.getByLabelText("Upload image")).toBeInTheDocument();
    expect(screen.getByTestId("image-upload-input")).toHaveStyle({ display: "none" });
  });

  it("calls onUpload with a valid PNG file", () => {
    const onUpload = jest.fn();
    render(<ImageUpload {...defaultProps} onUpload={onUpload} />);

    const file = createFile("photo.png", 1024, "image/png");
    selectFile(screen.getByTestId("image-upload-input"), file);

    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("calls onUpload with a valid JPEG file", () => {
    const onUpload = jest.fn();
    render(<ImageUpload {...defaultProps} onUpload={onUpload} />);

    const file = createFile("photo.jpg", 2048, "image/jpeg");
    selectFile(screen.getByTestId("image-upload-input"), file);

    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("shows file name after valid selection", () => {
    render(<ImageUpload {...defaultProps} />);

    const file = createFile("my-image.webp", 512, "image/webp");
    selectFile(screen.getByTestId("image-upload-input"), file);

    expect(screen.getByTestId("image-upload-filename")).toHaveTextContent("my-image.webp");
  });

  it("rejects files exceeding maxSizeMB with error message", () => {
    const onUpload = jest.fn();
    render(<ImageUpload {...defaultProps} onUpload={onUpload} />);

    const bigFile = createFile("huge.png", 6 * 1024 * 1024, "image/png");
    selectFile(screen.getByTestId("image-upload-input"), bigFile);

    expect(onUpload).not.toHaveBeenCalled();
    expect(screen.getByTestId("image-upload-error")).toHaveTextContent("File too large");
    expect(screen.queryByTestId("image-upload-filename")).not.toBeInTheDocument();
  });

  it("rejects unsupported file formats with error message", () => {
    const onUpload = jest.fn();
    render(<ImageUpload {...defaultProps} onUpload={onUpload} />);

    const bmpFile = createFile("image.bmp", 1024, "image/bmp");
    selectFile(screen.getByTestId("image-upload-input"), bmpFile);

    expect(onUpload).not.toHaveBeenCalled();
    expect(screen.getByTestId("image-upload-error")).toHaveTextContent("Unsupported format");
  });

  it("accepts a file exactly at the size limit", () => {
    const onUpload = jest.fn();
    render(<ImageUpload {...defaultProps} onUpload={onUpload} />);

    const exactFile = createFile("exact.gif", 5 * 1024 * 1024, "image/gif");
    selectFile(screen.getByTestId("image-upload-input"), exactFile);

    expect(onUpload).toHaveBeenCalledWith(exactFile);
  });

  it("clears error when a valid file is selected after an invalid one", () => {
    render(<ImageUpload {...defaultProps} />);
    const input = screen.getByTestId("image-upload-input");

    selectFile(input, createFile("bad.bmp", 1024, "image/bmp"));
    expect(screen.getByTestId("image-upload-error")).toBeInTheDocument();

    selectFile(input, createFile("good.png", 1024, "image/png"));
    expect(screen.queryByTestId("image-upload-error")).not.toBeInTheDocument();
  });

  it("error element has role=alert for accessibility", () => {
    render(<ImageUpload {...defaultProps} />);

    selectFile(
      screen.getByTestId("image-upload-input"),
      createFile("bad.svg", 1024, "image/svg+xml")
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("has accessible label on the file input", () => {
    render(<ImageUpload {...defaultProps} />);
    expect(screen.getByLabelText("Upload image")).toBeInTheDocument();
  });
});
