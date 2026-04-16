/**
 * Keycloak OIDC client with PKCE flow for claude-simulator.
 *
 * Handles login redirect, token storage, silent refresh, and
 * Bearer header injection. Lightweight — no next-auth dependency.
 */

// --- Configuration ---

const KEYCLOAK_REALM = "claude-simulator";
const KEYCLOAK_CLIENT_ID = "claude-simulator-app";

function getKeycloakBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "http://localhost:8080"
  );
}

function getRedirectUri(): string {
  return (
    process.env.NEXT_PUBLIC_REDIRECT_URI ??
    (typeof window !== "undefined" ? window.location.origin : "http://localhost:3000")
  );
}

function keycloakUrl(path: string): string {
  return `${getKeycloakBaseUrl()}/realms/${KEYCLOAK_REALM}/protocol/openid-connect${path}`;
}

// --- PKCE helpers ---

function generateRandomString(length: number): string {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(plain: string): Promise<ArrayBuffer> {
  const encoder = new TextEncoder();
  return crypto.subtle.digest("SHA-256", encoder.encode(plain));
}

function base64UrlEncode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const b of bytes) {
    binary += String.fromCharCode(b);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function generatePKCE(): Promise<{
  codeVerifier: string;
  codeChallenge: string;
}> {
  const codeVerifier = generateRandomString(32);
  const hash = await sha256(codeVerifier);
  const codeChallenge = base64UrlEncode(hash);
  return { codeVerifier, codeChallenge };
}

// --- Token types ---

export interface TokenSet {
  access_token: string;
  refresh_token: string;
  expires_in: number; // seconds
  /** Absolute ms timestamp when the access token expires */
  expires_at: number;
}

// --- Token storage (sessionStorage for single-tab security) ---

const STORAGE_KEY = "claude_sim_tokens";
const VERIFIER_KEY = "claude_sim_pkce_verifier";

export function storeTokens(tokens: TokenSet): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
}

export function loadTokens(): TokenSet | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as TokenSet;
  } catch {
    return null;
  }
}

export function clearTokens(): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.removeItem(STORAGE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
}

// --- Auth status ---

export function isAuthenticated(): boolean {
  const tokens = loadTokens();
  if (!tokens) return false;
  // Consider authenticated if we have a refresh token (access may be expired but refreshable)
  return !!tokens.refresh_token;
}

export function getAccessToken(): string | null {
  const tokens = loadTokens();
  if (!tokens) return null;
  return tokens.access_token;
}

// --- Bearer header helper ---

export function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

// --- Login redirect ---

export async function redirectToLogin(): Promise<void> {
  const { codeVerifier, codeChallenge } = await generatePKCE();
  sessionStorage.setItem(VERIFIER_KEY, codeVerifier);

  const params = new URLSearchParams({
    client_id: KEYCLOAK_CLIENT_ID,
    response_type: "code",
    scope: "openid",
    redirect_uri: getRedirectUri(),
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });

  window.location.href = `${keycloakUrl("/auth")}?${params.toString()}`;
}

// --- Token exchange (authorization code → tokens) ---

export async function exchangeCodeForTokens(code: string): Promise<TokenSet> {
  const codeVerifier = sessionStorage.getItem(VERIFIER_KEY);
  if (!codeVerifier) {
    throw new Error("Missing PKCE code verifier");
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: KEYCLOAK_CLIENT_ID,
    code,
    redirect_uri: getRedirectUri(),
    code_verifier: codeVerifier,
  });

  const res = await fetch(keycloakUrl("/token"), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  if (!res.ok) {
    throw new Error(`Token exchange failed: ${res.status}`);
  }

  const data = await res.json();
  const tokens: TokenSet = {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_in: data.expires_in,
    expires_at: Date.now() + data.expires_in * 1000,
  };

  storeTokens(tokens);
  sessionStorage.removeItem(VERIFIER_KEY);
  return tokens;
}

// --- Silent refresh ---

export async function refreshAccessToken(): Promise<TokenSet> {
  const current = loadTokens();
  if (!current?.refresh_token) {
    throw new Error("No refresh token available");
  }

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: KEYCLOAK_CLIENT_ID,
    refresh_token: current.refresh_token,
  });

  const res = await fetch(keycloakUrl("/token"), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  if (!res.ok) {
    // Refresh token expired or revoked — force re-login
    clearTokens();
    throw new Error(`Token refresh failed: ${res.status}`);
  }

  const data = await res.json();
  const tokens: TokenSet = {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_in: data.expires_in,
    expires_at: Date.now() + data.expires_in * 1000,
  };

  storeTokens(tokens);
  return tokens;
}

// --- Ensure valid token (refresh if needed) ---

/** Refresh buffer: refresh 30 seconds before actual expiry */
const REFRESH_BUFFER_MS = 30_000;

export async function ensureValidToken(): Promise<string> {
  const tokens = loadTokens();
  if (!tokens) {
    throw new Error("Not authenticated");
  }

  if (Date.now() < tokens.expires_at - REFRESH_BUFFER_MS) {
    return tokens.access_token;
  }

  // Token expired or about to expire — refresh
  const refreshed = await refreshAccessToken();
  return refreshed.access_token;
}

// --- Silent refresh timer ---

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

export function startSilentRefresh(): void {
  stopSilentRefresh();

  const tokens = loadTokens();
  if (!tokens) return;

  // Schedule refresh 30s before expiry
  const msUntilRefresh = tokens.expires_at - Date.now() - REFRESH_BUFFER_MS;
  const delay = Math.max(msUntilRefresh, 0);

  refreshTimer = setTimeout(async () => {
    try {
      await refreshAccessToken();
      startSilentRefresh(); // reschedule after successful refresh
    } catch {
      // Refresh failed — user will be redirected on next API call
      clearTokens();
    }
  }, delay);
}

export function stopSilentRefresh(): void {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

// --- Handle callback (call on page load to process auth redirect) ---

export async function handleAuthCallback(): Promise<boolean> {
  if (typeof window === "undefined") return false;

  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");

  if (!code) return false;

  await exchangeCodeForTokens(code);

  // Clean up URL
  url.searchParams.delete("code");
  url.searchParams.delete("session_state");
  url.searchParams.delete("iss");
  window.history.replaceState({}, "", url.pathname);

  startSilentRefresh();
  return true;
}

// --- Logout ---

export function logout(): void {
  stopSilentRefresh();
  clearTokens();

  const params = new URLSearchParams({
    client_id: KEYCLOAK_CLIENT_ID,
    post_logout_redirect_uri: getRedirectUri(),
  });

  window.location.href = `${keycloakUrl("/logout")}?${params.toString()}`;
}
