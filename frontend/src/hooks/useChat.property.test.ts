/**
 * Property-based tests for useChat SSE chunk assembly.
 *
 * **Validates: Requirements 1.3**
 *
 * Property 2: Chunk assembly produces correct message
 * For any sequence of SSE text chunks received by the frontend,
 * concatenating them in order SHALL produce the complete assistant
 * response text identical to what Bedrock generated.
 */

import fc from "fast-check";
import { parseSSEData } from "./useChat";

/**
 * Split a string into random non-empty chunks.
 * Returns an array whose concatenation equals the original string.
 */
function splitIntoChunks(str: string, splitPoints: number[]): string[] {
  if (str.length === 0) return [""];
  const points = [...new Set(splitPoints.map((p) => Math.abs(p % str.length)))]
    .filter((p) => p > 0 && p < str.length)
    .sort((a, b) => a - b);

  const chunks: string[] = [];
  let prev = 0;
  for (const p of points) {
    chunks.push(str.slice(prev, p));
    prev = p;
  }
  chunks.push(str.slice(prev));
  return chunks;
}

describe("Property 2: Chunk assembly produces correct message", () => {
  it("concatenating parsed SSE chunks reproduces the original message", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 0, maxLength: 500 }),
        fc.array(fc.integer(), { minLength: 0, maxLength: 20 }),
        (completeMessage, splitPoints) => {
          // 1. Split the complete message into random chunks
          const chunks = splitIntoChunks(completeMessage, splitPoints);

          // 2. Format each chunk as an SSE data line
          const sseLines = chunks.map(
            (chunk) =>
              `data: ${JSON.stringify({ text: chunk })}`
          );

          // 3. Parse each SSE line with parseSSEData
          const parsedChunks = sseLines.map((line) => parseSSEData(line));

          // 4. All parsed chunks should be non-null strings
          for (const parsed of parsedChunks) {
            expect(parsed).not.toBeNull();
          }

          // 5. Concatenate and assert equality with original
          const reassembled = parsedChunks.join("");
          expect(reassembled).toBe(completeMessage);
        }
      ),
      { numRuns: 200 }
    );
  });
});
