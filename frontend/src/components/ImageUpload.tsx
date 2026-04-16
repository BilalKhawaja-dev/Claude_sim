/**
 * ImageUpload — file picker for uploading images to chat.
 *
 * Accepts PNG, JPEG, GIF, WebP up to 5MB with client-side validation.
 *
 * Validates: Requirements 8.1, 8.4, 8.5
 */

import React, { useState, useCallback, useRef } from "react";

export interface ImageUploadProps {
  onUpload: (file: File) => void;
  maxSizeMB: number; // 5
  acceptedFormats: string[]; // ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
}

const styles = {
  container: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  } as React.CSSProperties,
  button: {
    padding: "6px 12px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    backgroundColor: "#f9fafb",
    fontSize: 13,
    cursor: "pointer",
  } as React.CSSProperties,
  fileName: {
    fontSize: 13,
    color: "#374151",
    maxWidth: 180,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  } as React.CSSProperties,
  error: {
    fontSize: 13,
    color: "#dc2626",
  } as React.CSSProperties,
};

export default function ImageUpload({
  onUpload,
  maxSizeMB,
  acceptedFormats,
}: ImageUploadProps) {
  const [error, setError] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const maxSizeBytes = maxSizeMB * 1024 * 1024;

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setError(null);
      setSelectedName(null);

      const file = e.target.files?.[0];
      if (!file) return;

      if (!acceptedFormats.includes(file.type)) {
        setError(
          `Unsupported format. Accepted: ${acceptedFormats.map((f) => f.split("/")[1]).join(", ")}`
        );
        // Reset input so the same file can be re-selected
        if (inputRef.current) inputRef.current.value = "";
        return;
      }

      if (file.size > maxSizeBytes) {
        setError(`File too large. Maximum size is ${maxSizeMB}MB.`);
        if (inputRef.current) inputRef.current.value = "";
        return;
      }

      setSelectedName(file.name);
      onUpload(file);
    },
    [acceptedFormats, maxSizeBytes, maxSizeMB, onUpload]
  );

  return (
    <div data-testid="image-upload" style={styles.container}>
      <label htmlFor="image-upload-input" style={styles.button}>
        Upload image
      </label>
      <input
        id="image-upload-input"
        ref={inputRef}
        data-testid="image-upload-input"
        type="file"
        accept={acceptedFormats.join(",")}
        onChange={handleChange}
        style={{ display: "none" }}
        aria-label="Upload image"
      />
      {selectedName && (
        <span data-testid="image-upload-filename" style={styles.fileName}>
          {selectedName}
        </span>
      )}
      {error && (
        <span data-testid="image-upload-error" role="alert" style={styles.error}>
          {error}
        </span>
      )}
    </div>
  );
}
