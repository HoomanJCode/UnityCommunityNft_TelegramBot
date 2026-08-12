/**
 * Typed client for the backend Admin API (backend/api/admin.py).
 *
 * Requests go to the same origin — in dev, Vite proxies /admin → :8000
 * (see vite.config.ts), so no CORS configuration is needed.
 */

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/admin";

// ---------------------------------------------------------------------------
// Admin auth token (localStorage-persisted bearer token)
// ---------------------------------------------------------------------------

const TOKEN_KEY = "admin_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

/** Exchange the shared admin password for a bearer token. */
export async function login(password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    let message = `login failed (${res.status})`;
    try {
      const body = await res.json();
      if (body && typeof body.error === "string") message = body.error;
    } catch {
      /* keep generic message */
    }
    throw new Error(message);
  }
  const body = (await res.json()) as { token: string };
  setToken(body.token);
}

export function logout(): void {
  setToken(null);
}

// When any request hits a 401 (missing/expired token), the app flips back to
// the login screen. Registered by App on mount.
let onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

// ---------------------------------------------------------------------------
// Types (mirror the JSON shapes returned by backend/api/admin.py)
// ---------------------------------------------------------------------------

export interface BadgeType {
  id: number;
  name: string;
  description: string | null;
  image_url: string | null;
  metadata_uri: string | null;
  is_soulbound: boolean;
  collection_address: string | null;
  supply: number;
  deployed_at: string | null;
  created_at: string | null;
}

export interface Event {
  id: number;
  name: string;
  description: string | null;
  starts_at: string | null;
  badge_type_id: number | null;
}

export type AssignmentStatus =
  | "pending"
  | "queued"
  | "minting"
  | "minted"
  | "failed"
  | "needs_wallet";

export interface Assignment {
  id: number;
  badge_type_id: number;
  user_id: number;
  status: AssignmentStatus;
  tx_hash: string | null;
  error: string | null;
  created_at: string | null;
  minted_at: string | null;
}

export interface BatchSummary {
  created?: number;
  needs_wallet?: number;
  skipped?: number;
  total?: number;
  [key: string]: number | undefined;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string>) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    // Token missing/expired — drop it and bounce to the login screen.
    setToken(null);
    onUnauthorized?.();
  }
  if (!res.ok) {
    // Surface the backend's {"error": "..."} message when present.
    let message = `request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body && typeof body.error === "string") message = body.error;
    } catch {
      /* non-JSON error body — keep the generic message */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// ---------------------------------------------------------------------------
// Badge types (CRUD)
// ---------------------------------------------------------------------------

/** True when the backend has admin auth enabled (ADMIN_PASSWORD set). */
export async function authStatus(): Promise<{ enabled: boolean }> {
  // Dedicated probe endpoint — it never touches the login rate limiter, so
  // probing the app doesn't throttle the operator's first real login.
  const res = await fetch(`${API_BASE}/auth/status`);
  if (res.ok) return res.json();
  throw new Error(`backend unreachable (${res.status})`);
}

// ---------------------------------------------------------------------------
// On-chain verification (TonAPI)
// ---------------------------------------------------------------------------

export interface CollectionInfo {
  address: string;
  name: string | null;
  description: string | null;
  image: string | null;
  owner: string | null;
  next_item_index: number | null;
  verified: boolean;
}

/** Verify a deployed collection on-chain (needs TON_API_KEY). */
export const verifyCollection = (address: string) =>
  request<CollectionInfo>(`/tonapi/collections/${encodeURIComponent(address)}`);

export const listBadgeTypes = () => request<BadgeType[]>("/badge-types");

export interface BadgeTypeInput {
  name: string;
  description?: string | null;
  image_url?: string | null;
  metadata_uri?: string | null;
  is_soulbound?: boolean;
}

export const createBadgeType = (input: BadgeTypeInput) =>
  request<BadgeType>("/badge-types", jsonInit("POST", input));

export const updateBadgeType = (id: number, input: Partial<BadgeTypeInput>) =>
  request<BadgeType>(`/badge-types/${id}`, jsonInit("PUT", input));

export const deleteBadgeType = (id: number) =>
  request<{ deleted: number }>(`/badge-types/${id}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Events (CRUD)
// ---------------------------------------------------------------------------

export const listEvents = () => request<Event[]>("/events");

export interface EventInput {
  name: string;
  description?: string | null;
  starts_at?: string | null;
  badge_type_id?: number | null;
}

export const createEvent = (input: EventInput) =>
  request<Event>("/events", jsonInit("POST", input));

export const updateEvent = (id: number, input: Partial<EventInput>) =>
  request<Event>(`/events/${id}`, jsonInit("PUT", input));

export const deleteEvent = (id: number) =>
  request<{ deleted: number }>(`/events/${id}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// Batch mint assignments
// ---------------------------------------------------------------------------

/** Create assignments from a list of phone numbers. */
export const createAssignments = (badgeTypeId: number, phones: string[]) =>
  request<BatchSummary>(
    "/assignments",
    jsonInit("POST", { badge_type_id: badgeTypeId, phones })
  );

/** Create assignments from an uploaded CSV (one phone number per line). */
export const uploadAssignmentsCsv = (badgeTypeId: number, file: File) => {
  const form = new FormData();
  form.append("badge_type_id", String(badgeTypeId));
  form.append("file", file);
  return request<BatchSummary>("/assignments/upload", { method: "POST", body: form });
};

export const listAssignments = (status?: AssignmentStatus) =>
  request<Assignment[]>(
    `/assignments${status ? `?status=${encodeURIComponent(status)}` : ""}`
  );

/** Transition an assignment to a new status (rejected if illegal). */
export const setAssignmentStatus = (id: number, status: AssignmentStatus) =>
  request<Assignment>(`/assignments/${id}/status`, jsonInit("POST", { status }));
