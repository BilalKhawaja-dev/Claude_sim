/**
 * Tests for frontend/src/lib/auth.ts — Keycloak OIDC PKCE auth module.
 *
 * Validates: Requirements 10.1, 10.2, 10.3, 10.6
 */

import {
  generatePKCE,
  storeTokens,
  loadTokens,
  clearTokens,
  isAuthenticated,
  getAccessToken,
  authHeaders,
  exchangeCodeForTokens,
  refreshAccessToken,
  ensureValidToken,
  handleAuthCallback,
  startSilentRefresh,
  stopSilentRefresh,
  logout,
  TokenSet,
} from "./auth";

// --- Polyfills for jsdom ---

import { TextEncoder as NodeTextEncoder } from "util";
if (typeof globalThis.TextEncoder === "undefined") {
  (globalThis as any).TextEncoder = NodeTextEncoder;
}

// --- Mocks ---

const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock crypto.subtle and crypto.getRandomValues for PKCE
const mockGetRandomValues = jest.fn((arr: Uint8Array) => {
  for (let i = 0; i < arr.length; i++) arr[i] = i % 256;
  return arr;
});

const mockDigest = jest.fn(async (_algo: string, data: ArrayBuffer) => {
  // Return a deterministic 32-byte hash for testing
  return new Uint8Array(32).fill(42).buffer;
});

Object.defineProperty(global, "crypto", {
  value: {
    getRandomValues: mockGetRandomValues,
    subtle: { digest: mockDigest },
  },
});

// Mock sessionStorage
const store: Record<string, string> = {};
const mockSessionStorage = {
  getItem: jest.fn((key: string) => store[key] ?? null),
  setItem: jest.fn((key: string, value: string) => {
    store[key] = value;
  }),
  removeItem: jest.fn((key: string) => {
    delete store[key];
  }),
};
Object.defineProperty(global, "sessionStorage", { value: mockSessionStorage });

// Helper to create a valid token set
function makeTokenSet(overrides: Partial<TokenSet> = {}): TokenSet {
  return {
    access_token: "test-access-token",
    refresh_token: "test-refresh-token",
    expires_in: 300,
    expires_at: Date.now() + 300_000,
    ...overrides,
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
  // Clear storage
  for (const key of Object.keys(store)) delete store[key];
});

afterEach(() => {
  stopSilentRefresh();
  jest.useRealTimers();
});

// --- PKCE ---

describe("generatePKCE", () => {
  it("returns a code verifier and code challenge", async () => {
    const { codeVerifier, codeChallenge } = await generatePKCE();
    expect(codeVerifier).toBeTruthy();
    expect(codeChallenge).toBeTruthy();
    expect(typeof codeVerifier).toBe("string");
    expect(typeof codeChallenge).toBe("string");
    // Challenge should be base64url (no +, /, =)
    expect(codeChallenge).not.toMatch(/[+/=]/);
  });
});

// --- Token storage ---

describe("token storage", () => {
  it("stores and loads tokens", () => {
    const tokens = makeTokenSet();
    storeTokens(tokens);
    const loaded = loadTokens();
    expect(loaded).toEqual(tokens);
  });

  it("returns null when no tokens stored", () => {
    expect(loadTokens()).toBeNull();
  });

  it("clears tokens", () => {
    storeTokens(makeTokenSet());
    clearTokens();
    expect(loadTokens()).toBeNull();
  });
});

// --- Auth status ---

describe("isAuthenticated", () => {
  it("returns false when no tokens", () => {
    expect(isAuthenticated()).toBe(false);
  });

  it("returns true when tokens with refresh_token exist", () => {
    storeTokens(makeTokenSet());
    expect(isAuthenticated()).toBe(true);
  });

  it("returns false when refresh_token is empty", () => {
    storeTokens(makeTokenSet({ refresh_token: "" }));
    expect(isAuthenticated()).toBe(false);
  });
});

// --- getAccessToken ---

describe("getAccessToken", () => {
  it("returns null when no tokens", () => {
    expect(getAccessToken()).toBeNull();
  });

  it("returns the access token", () => {
    storeTokens(makeTokenSet({ access_token: "my-token" }));
    expect(getAccessToken()).toBe("my-token");
  });
});

// --- authHeaders (Requirement 10.3: Bearer header injection) ---

describe("authHeaders", () => {
  it("returns empty object when not authenticated", () => {
    expect(authHeaders()).toEqual({});
  });

  it("returns Authorization Bearer header with access token", () => {
    storeTokens(makeTokenSet({ access_token: "abc123" }));
    expect(authHeaders()).toEqual({ Authorization: "Bearer abc123" });
  });
});

// --- Token exchange (Requirement 10.2: PKCE flow) ---

describe("exchangeCodeForTokens", () => {
  it("exchanges authorization code for tokens", async () => {
    // Store the PKCE verifier (simulating what redirectToLogin does)
    store["claude_sim_pkce_verifier"] = "test-verifier";

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: "new-access",
        refresh_token: "new-refresh",
        expires_in: 300,
      }),
    });

    const tokens = await exchangeCodeForTokens("auth-code-123");

    expect(tokens.access_token).toBe("new-access");
    expect(tokens.refresh_token).toBe("new-refresh");
    expect(tokens.expires_in).toBe(300);
    expect(tokens.expires_at).toBeGreaterThan(Date.now());

    // Verify fetch was called with correct params
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/token");
    expect(opts.method).toBe("POST");
    expect(opts.body).toContain("grant_type=authorization_code");
    expect(opts.body).toContain("code=auth-code-123");
    expect(opts.body).toContain("code_verifier=test-verifier");

    // Tokens should be stored
    expect(loadTokens()?.access_token).toBe("new-access");

    // Verifier should be cleaned up
    expect(store["claude_sim_pkce_verifier"]).toBeUndefined();
  });

  it("throws when PKCE verifier is missing", async () => {
    await expect(exchangeCodeForTokens("code")).rejects.toThrow(
      "Missing PKCE code verifier"
    );
  });

  it("throws on failed token exchange", async () => {
    store["claude_sim_pkce_verifier"] = "verifier";
    mockFetch.mockResolvedValueOnce({ ok: false, status: 400 });

    await expect(exchangeCodeForTokens("bad-code")).rejects.toThrow(
      "Token exchange failed: 400"
    );
  });
});

// --- Silent refresh (Requirement 10.6) ---

describe("refreshAccessToken", () => {
  it("refreshes the access token using refresh_token", async () => {
    storeTokens(makeTokenSet());

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: "refreshed-access",
        refresh_token: "refreshed-refresh",
        expires_in: 300,
      }),
    });

    const tokens = await refreshAccessToken();
    expect(tokens.access_token).toBe("refreshed-access");

    // Verify grant_type=refresh_token was sent
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.body).toContain("grant_type=refresh_token");
  });

  it("clears tokens and throws on refresh failure", async () => {
    storeTokens(makeTokenSet());
    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });

    await expect(refreshAccessToken()).rejects.toThrow("Token refresh failed: 401");
    expect(loadTokens()).toBeNull();
  });

  it("throws when no refresh token available", async () => {
    await expect(refreshAccessToken()).rejects.toThrow(
      "No refresh token available"
    );
  });
});

// --- ensureValidToken ---

describe("ensureValidToken", () => {
  it("returns current token when not expired", async () => {
    storeTokens(makeTokenSet({ access_token: "valid", expires_at: Date.now() + 60_000 }));
    const token = await ensureValidToken();
    expect(token).toBe("valid");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("refreshes when token is about to expire", async () => {
    // Token expires in 10 seconds (within 30s buffer)
    storeTokens(makeTokenSet({ expires_at: Date.now() + 10_000 }));

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: "fresh",
        refresh_token: "fresh-refresh",
        expires_in: 300,
      }),
    });

    const token = await ensureValidToken();
    expect(token).toBe("fresh");
  });

  it("throws when not authenticated", async () => {
    await expect(ensureValidToken()).rejects.toThrow("Not authenticated");
  });
});

// --- handleAuthCallback ---

describe("handleAuthCallback", () => {
  const originalLocation = window.location;
  const originalHistory = window.history;

  beforeEach(() => {
    Object.defineProperty(window, "history", {
      value: { replaceState: jest.fn() },
      writable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
    Object.defineProperty(window, "history", {
      value: originalHistory,
      writable: true,
    });
  });

  it("returns false when no code in URL", async () => {
    Object.defineProperty(window, "location", {
      value: { href: "http://localhost:3000/" },
      writable: true,
    });
    const result = await handleAuthCallback();
    expect(result).toBe(false);
  });

  it("exchanges code and cleans URL when code is present", async () => {
    store["claude_sim_pkce_verifier"] = "verifier";
    Object.defineProperty(window, "location", {
      value: { href: "http://localhost:3000/?code=abc&session_state=xyz", origin: "http://localhost:3000" },
      writable: true,
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: "at",
        refresh_token: "rt",
        expires_in: 300,
      }),
    });

    const result = await handleAuthCallback();
    expect(result).toBe(true);
    expect(loadTokens()?.access_token).toBe("at");
    expect(window.history.replaceState).toHaveBeenCalled();
  });
});
