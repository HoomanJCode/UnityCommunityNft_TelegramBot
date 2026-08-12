import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Assignment,
  AssignmentStatus,
  BadgeType,
  BatchSummary,
  Event,
  authStatus,
  createAssignments,
  createBadgeType,
  createEvent,
  deleteBadgeType,
  deleteEvent,
  getToken,
  listAssignments,
  listBadgeTypes,
  listEvents,
  login,
  logout,
  setOnUnauthorized,
  setAssignmentStatus,
  updateBadgeType,
  updateEvent,
  uploadAssignmentsCsv,
  verifyCollection,
} from "./api";

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

type Tab = "badges" | "events" | "mint";

const STATUS_COLORS: Record<AssignmentStatus, string> = {
  pending: "#8b98a5",
  queued: "#2aabee",
  minting: "#f59e0b",
  minted: "#31c48d",
  failed: "#f87171",
  needs_wallet: "#c084fc",
};

function shortHash(hash: string | null): string {
  if (!hash) return "—";
  return `${hash.slice(0, 8)}…${hash.slice(-6)}`;
}

function shortAddress(addr: string | null): string {
  if (!addr) return "—";
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function StatusPill({ status }: { status: AssignmentStatus }) {
  return (
    <span className="pill" style={{ color: STATUS_COLORS[status] }}>
      <span className="pill-dot" style={{ background: STATUS_COLORS[status] }} />
      {status}
    </span>
  );
}

function IconBtn({
  label,
  onClick,
  danger,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      className={`icon-btn ${danger ? "danger" : ""}`}
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function Notice({ kind, text }: { kind: "error" | "ok" | "info"; text: string | null }) {
  if (!text) return null;
  return <p className={`notice-${kind}`}>{text}</p>;
}

// ---------------------------------------------------------------------------
// Login screen (shown when the backend requires admin auth)
// ---------------------------------------------------------------------------

function LoginScreen({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(password);
      onLoggedIn();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="header-logo">🛡️</span>
          <h1>UnityCommunity Admin</h1>
          <p className="muted">Sign in to manage badges, events and minting</p>
        </div>
        <label>
          Admin password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoFocus
            required
          />
        </label>
        <Notice kind="error" text={error} />
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Badge types tab
// ---------------------------------------------------------------------------

function BadgeTypeForm({
  badge,
  onSaved,
  onCancel,
}: {
  badge?: BadgeType;
  onSaved: (b: BadgeType) => void;
  onCancel?: () => void;
}) {
  const [name, setName] = useState(badge?.name ?? "");
  const [description, setDescription] = useState(badge?.description ?? "");
  const [imageUrl, setImageUrl] = useState(badge?.image_url ?? "");
  const [metadataUri, setMetadataUri] = useState(badge?.metadata_uri ?? "");
  const [isSoulbound, setIsSoulbound] = useState(badge?.is_soulbound ?? false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const input = {
        name,
        description: description || null,
        image_url: imageUrl || null,
        metadata_uri: metadataUri || null,
        is_soulbound: isSoulbound,
      };
      const saved = badge
        ? await updateBadgeType(badge.id, input)
        : await createBadgeType(input);
      onSaved(saved);
      if (!badge) {
        // Reset the form after a successful create.
        setName("");
        setDescription("");
        setImageUrl("");
        setMetadataUri("");
        setIsSoulbound(false);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="form-row">
        <label>
          Name *
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Community Member"
            required
          />
        </label>
        <label className="checkbox-label" title="Soulbound badges cannot be transferred (TEP-85)">
          <input
            type="checkbox"
            checked={isSoulbound}
            onChange={(e) => setIsSoulbound(e.target.checked)}
          />
          Soulbound
        </label>
      </div>
      <label>
        Description
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Awarded for joining the community"
        />
      </label>
      <div className="form-row">
        <label>
          Image URL
          <input
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            placeholder="https://…/badge.png"
          />
        </label>
        <label>
          Metadata URI
          <input
            value={metadataUri}
            onChange={(e) => setMetadataUri(e.target.value)}
            placeholder="ipfs://…/meta.json"
          />
        </label>
      </div>
      <Notice kind="error" text={error} />
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? "Saving…" : badge ? "Save changes" : "Create badge type"}
        </button>
        {onCancel && (
          <button type="button" className="btn ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

function BadgesTab() {
  const [badges, setBadges] = useState<BadgeType[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  // On-chain verification results keyed by badge type id.
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [verifyResults, setVerifyResults] = useState<Record<number, { ok: boolean; text: string }>>({});

  const load = useCallback(async () => {
    setError(null);
    try {
      setBadges(await listBadgeTypes());
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const remove = async (b: BadgeType) => {
    if (!confirm(`Delete badge type "${b.name}"? This cannot be undone.`)) return;
    try {
      await deleteBadgeType(b.id);
      setBadges((prev) => prev?.filter((x) => x.id !== b.id) ?? null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const verify = async (b: BadgeType) => {
    if (!b.collection_address) {
      setVerifyResults((prev) => ({
        ...prev,
        [b.id]: { ok: false, text: "no collection deployed yet" },
      }));
      return;
    }
    setVerifyingId(b.id);
    try {
      const info = await verifyCollection(b.collection_address);
      setVerifyResults((prev) => ({
        ...prev,
        [b.id]: {
          ok: true,
          text: `on-chain: ${info.name ?? "unnamed"} · next item #${info.next_item_index ?? "?"}`,
        },
      }));
    } catch (err) {
      setVerifyResults((prev) => ({
        ...prev,
        [b.id]: { ok: false, text: (err as Error).message },
      }));
    } finally {
      setVerifyingId(null);
    }
  };

  const counts = useMemo(() => {
    if (!badges) return { soulbound: 0, transferable: 0, deployed: 0 };
    return {
      soulbound: badges.filter((b) => b.is_soulbound).length,
      transferable: badges.filter((b) => !b.is_soulbound).length,
      deployed: badges.filter((b) => b.collection_address).length,
    };
  }, [badges]);

  return (
    <section>
      <div className="stats-row">
        <div className="stat"><strong>{badges?.length ?? "…"}</strong><span>Badge types</span></div>
        <div className="stat"><strong>{counts.transferable}</strong><span>Transferable</span></div>
        <div className="stat"><strong>{counts.soulbound}</strong><span>Soulbound</span></div>
        <div className="stat"><strong>{counts.deployed}</strong><span>Deployed</span></div>
      </div>

      <Notice kind="error" text={error} />

      {creating ? (
        <div className="card">
          <h3>New badge type</h3>
          <BadgeTypeForm
            onSaved={(b) => {
              setBadges((prev) => [...(prev ?? []), b]);
              setCreating(false);
            }}
            onCancel={() => setCreating(false)}
          />
        </div>
      ) : (
        <button className="btn primary add-btn" onClick={() => setCreating(true)}>
          + New badge type
        </button>
      )}

      <div className="card-grid">
        {badges?.map((b) => (
          <div className="badge-card" key={b.id}>
            <div className="badge-card-head">
              <div className="badge-icon" style={{ background: b.is_soulbound ? "#c084fc22" : "#2aabee22" }}>
                {b.image_url ? (
                  <img src={b.image_url} alt={b.name} onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
                ) : (
                  <span>{b.is_soulbound ? "🔒" : "🎖️"}</span>
                )}
              </div>
              <div className="badge-card-actions">
                <IconBtn label="Edit" onClick={() => setEditingId(editingId === b.id ? null : b.id)}>
                  ✏️
                </IconBtn>
                <IconBtn label="Delete" danger onClick={() => void remove(b)}>
                  🗑️
                </IconBtn>
              </div>
            </div>
            <h4>{b.name}</h4>
            {b.description && <p className="muted">{b.description}</p>}
            <div className="tag-row">
              <span className={`tag ${b.is_soulbound ? "tag-soul" : "tag-trans"}`}>
                {b.is_soulbound ? "soulbound" : "transferable"}
              </span>
              <span className="tag">supply {b.supply}</span>
            </div>
            <p className="mono addr">collection {shortAddress(b.collection_address)}</p>
            <div className="verify-row">
              <button
                className="btn ghost tiny"
                onClick={() => void verify(b)}
                disabled={verifyingId === b.id}
              >
                {verifyingId === b.id ? "Verifying…" : "🔎 Verify on-chain"}
              </button>
              {verifyResults[b.id] && (
                <span
                  className={`verify-result ${verifyResults[b.id].ok ? "ok" : "bad"}`}
                >
                  {verifyResults[b.id].text}
                </span>
              )}
            </div>
            {editingId === b.id && (
              <BadgeTypeForm
                badge={b}
                onSaved={(updated) => {
                  setBadges((prev) => prev?.map((x) => (x.id === updated.id ? updated : x)) ?? null);
                  setEditingId(null);
                }}
                onCancel={() => setEditingId(null)}
              />
            )}
          </div>
        ))}
        {badges && badges.length === 0 && (
          <div className="empty full">No badge types yet — create your first one above.</div>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Events tab
// ---------------------------------------------------------------------------

function EventsTab({ badgeTypes }: { badgeTypes: BadgeType[] }) {
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setEvents(await listEvents());
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const remove = async (ev: Event) => {
    if (!confirm(`Delete event "${ev.name}"?`)) return;
    try {
      await deleteEvent(ev.id);
      setEvents((prev) => prev?.filter((x) => x.id !== ev.id) ?? null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const badgeName = (id: number | null) =>
    badgeTypes.find((b) => b.id === id)?.name ?? "—";

  return (
    <section>
      <Notice kind="error" text={error} />

      {showForm ? (
        <div className="card">
          <h3>New event</h3>
          <EventForm
            badgeTypes={badgeTypes}
            onSaved={(ev) => {
              setEvents((prev) => [...(prev ?? []), ev]);
              setShowForm(false);
            }}
            onCancel={() => setShowForm(false)}
          />
        </div>
      ) : (
        <button className="btn primary add-btn" onClick={() => setShowForm(true)}>
          + New event
        </button>
      )}

      <div className="event-list">
        {events?.map((ev) => (
          <div className="card event-card" key={ev.id}>
            <div className="event-head">
              <div>
                <h4>{ev.name}</h4>
                {ev.description && <p className="muted">{ev.description}</p>}
              </div>
              <div className="badge-card-actions">
                <IconBtn label="Edit" onClick={() => setEditingId(editingId === ev.id ? null : ev.id)}>
                  ✏️
                </IconBtn>
                <IconBtn label="Delete" danger onClick={() => void remove(ev)}>
                  🗑️
                </IconBtn>
              </div>
            </div>
            <div className="tag-row">
              <span className="tag tag-trans">badge: {badgeName(ev.badge_type_id)}</span>
              {ev.starts_at && <span className="tag">{new Date(ev.starts_at).toLocaleString()}</span>}
            </div>
            {editingId === ev.id && (
              <EventForm
                badgeTypes={badgeTypes}
                event={ev}
                onSaved={(updated) => {
                  setEvents((prev) => prev?.map((x) => (x.id === updated.id ? updated : x)) ?? null);
                  setEditingId(null);
                }}
                onCancel={() => setEditingId(null)}
              />
            )}
          </div>
        ))}
        {events && events.length === 0 && (
          <div className="empty">No events yet.</div>
        )}
      </div>
    </section>
  );
}

function EventForm({
  badgeTypes,
  event,
  onSaved,
  onCancel,
}: {
  badgeTypes: BadgeType[];
  event?: Event;
  onSaved: (e: Event) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(event?.name ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [startsAt, setStartsAt] = useState(event?.starts_at ? event.starts_at.slice(0, 16) : "");
  const [badgeTypeId, setBadgeTypeId] = useState<number | "">(event?.badge_type_id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const input = {
        name,
        description: description || null,
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        badge_type_id: badgeTypeId === "" ? null : badgeTypeId,
      };
      const saved = event ? await updateEvent(event.id, input) : await createEvent(input);
      onSaved(saved);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <div className="form-row">
        <label>
          Name *
          <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Summer Meetup" />
        </label>
        <label>
          Starts at
          <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
        </label>
      </div>
      <label>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Event description" />
      </label>
      <label>
        Badge type
        <select value={badgeTypeId} onChange={(e) => setBadgeTypeId(e.target.value ? Number(e.target.value) : "")}>
          <option value="">— none —</option>
          {badgeTypes.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} ({b.is_soulbound ? "soulbound" : "transferable"})
            </option>
          ))}
        </select>
      </label>
      <Notice kind="error" text={error} />
      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? "Saving…" : event ? "Save changes" : "Create event"}
        </button>
        <button type="button" className="btn ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Batch mint tab
// ---------------------------------------------------------------------------

function BatchMintTab({ badgeTypes }: { badgeTypes: BadgeType[] }) {
  const [badgeTypeId, setBadgeTypeId] = useState<number | "">("");
  const [phonesText, setPhonesText] = useState("");
  const [summary, setSummary] = useState<BatchSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [statusFilter, setStatusFilter] = useState<AssignmentStatus | "">("");
  const [transitionError, setTransitionError] = useState<string | null>(null);

  const loadAssignments = useCallback(async () => {
    try {
      setAssignments(await listAssignments(statusFilter || undefined));
    } catch (err) {
      setError((err as Error).message);
    }
  }, [statusFilter]);

  useEffect(() => {
    void loadAssignments();
  }, [loadAssignments]);

  // Normalize "79991112233, 7999 111 22 33, +7(999)111-22-33" into digits.
  const phones = useMemo(
    () =>
      phonesText
        .split(/[\n,;]+/)
        .map((p) => p.replace(/\D/g, ""))
        .filter((p) => p.length >= 8),
    [phonesText]
  );

  const submitPhones = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!badgeTypeId) return setError("Pick a badge type first");
    if (!phones.length) return setError("Enter at least one valid phone number");
    setBusy(true);
    setError(null);
    setSummary(null);
    try {
      setSummary(await createAssignments(badgeTypeId, phones));
      setPhonesText("");
      void loadAssignments();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submitCsv = async (file: File) => {
    if (!badgeTypeId) return setError("Pick a badge type first");
    setBusy(true);
    setError(null);
    setSummary(null);
    try {
      setSummary(await uploadAssignmentsCsv(badgeTypeId, file));
      void loadAssignments();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const transition = async (a: Assignment, to: AssignmentStatus) => {
    setTransitionError(null);
    try {
      const updated = await setAssignmentStatus(a.id, to);
      setAssignments((prev) => prev?.map((x) => (x.id === updated.id ? updated : x)) ?? null);
    } catch (err) {
      setTransitionError((err as Error).message);
    }
  };

  // Mirrors the backend state machine (backend/services/assignment.py TRANSITIONS)
  // so the UI never offers a transition the API would reject with 409.
  const canTransition: Record<AssignmentStatus, AssignmentStatus[]> = {
    pending: ["queued", "failed"],
    queued: ["minting", "failed", "needs_wallet"],
    minting: ["minted", "failed"],
    failed: ["queued", "pending"],
    needs_wallet: ["pending"],
    minted: [],
  };

  const badgeName = (id: number) => badgeTypes.find((b) => b.id === id)?.name ?? `#${id}`;

  return (
    <section className="mint-grid">
      <div className="card">
        <h3>Batch mint</h3>
        <p className="muted">
          Hand out a badge to many users at once. Assignments are queued for the
          worker, which mints them on-chain and notifies each user.
        </p>
        <form className="form" onSubmit={submitPhones}>
          <label>
            Badge type *
            <select value={badgeTypeId} onChange={(e) => setBadgeTypeId(e.target.value ? Number(e.target.value) : "")} required>
              <option value="">— choose —</option>
              {badgeTypes.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.is_soulbound ? "soulbound" : "transferable"} · supply {b.supply})
                </option>
              ))}
            </select>
          </label>
          <label>
            Phone numbers (one per line)
            <textarea
              value={phonesText}
              onChange={(e) => setPhonesText(e.target.value)}
              placeholder={"79991112233\n79995556677"}
              rows={6}
            />
          </label>
          <p className="muted small">{phones.length} valid number(s) parsed</p>
          <button type="submit" className="btn primary" disabled={busy}>
            {busy ? "Queuing…" : "Queue batch mint"}
          </button>
        </form>

        <div className="csv-zone">
          <span className="muted small">…or upload a CSV:</span>
          <label className="btn ghost file-btn">
            {busy ? "Uploading…" : "Upload CSV"}
            <input
              type="file"
              accept=".csv,.txt"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void submitCsv(f);
                e.target.value = "";
              }}
            />
          </label>
        </div>

        <Notice kind="error" text={error} />
        {summary && (
          <div className="summary">
            <h4>Batch result</h4>
            <div className="stats-row compact">
              {Object.entries(summary).map(([k, v]) => (
                <div className="stat" key={k}>
                  <strong>{v ?? 0}</strong>
                  <span>{k.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="list-head">
          <h3>Assignments</h3>
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as AssignmentStatus | "")}
          >
            <option value="">all statuses</option>
            {(Object.keys(STATUS_COLORS) as AssignmentStatus[]).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <Notice kind="error" text={transitionError} />
        {assignments && assignments.length === 0 ? (
          <div className="empty">No assignments match this filter.</div>
        ) : (
          <div className="assign-list">
            {assignments?.map((a) => (
              <div className="assign-row" key={a.id}>
                <div className="assign-main">
                  <div className="assign-title">
                    <span className="mono">#{a.id}</span>
                    <strong>{badgeName(a.badge_type_id)}</strong>
                    <StatusPill status={a.status} />
                  </div>
                  <p className="muted small">
                    user {a.user_id} · tx {shortHash(a.tx_hash)}
                  </p>
                  {a.error && <p className="notice-error small">{a.error}</p>}
                </div>
                {canTransition[a.status].length > 0 && (
                  <div className="assign-actions">
                    {canTransition[a.status].map((to) => (
                      <button
                        key={to}
                        className="btn ghost tiny"
                        onClick={() => void transition(a, to)}
                      >
                        → {to}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Root app
// ---------------------------------------------------------------------------

export default function App() {
  const [tab, setTab] = useState<Tab>("badges");
  const [badgeTypes, setBadgeTypes] = useState<BadgeType[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  // auth: "unknown" while probing, "required" to show login, "ok" to show app.
  const [auth, setAuth] = useState<"unknown" | "required" | "ok">("unknown");

  const refreshBadgeTypes = useCallback(async () => {
    setLoadError(null);
    try {
      setBadgeTypes(await listBadgeTypes());
    } catch (err) {
      // The Events/Mint tabs depend on the badge-type list for their
      // dropdowns, so surface a fetch failure up here instead of silently
      // rendering empty selects.
      setLoadError((err as Error).message);
    }
  }, []);

  // Decide up front whether the backend requires a login.
  useEffect(() => {
    // Any 401 (e.g. an expired token mid-session) bounces back to login.
    setOnUnauthorized(() => setAuth("required"));
    void authStatus()
      .then(({ enabled }) => {
        if (enabled && !getToken()) {
          setAuth("required");
        } else {
          setAuth("ok");
        }
      })
      .catch(() => {
        // Backend down (or probing failed) — still show the app; individual
        // tabs surface their own errors.
        setAuth("ok");
      })
      .finally(() => setLoading(false));
    return () => setOnUnauthorized(null);
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <span className="header-logo">🛡️</span>
          <div>
            <h1>UnityCommunity Admin</h1>
            <p>Badge types, events & batch NFT minting</p>
          </div>
        </div>
      </header>

      <nav className="tabs">
        <button className={tab === "badges" ? "tab active" : "tab"} onClick={() => setTab("badges")}>
          Badges
        </button>
        <button className={tab === "events" ? "tab active" : "tab"} onClick={() => setTab("events")}>
          Events
        </button>
        <button className={tab === "mint" ? "tab active" : "tab"} onClick={() => setTab("mint")}>
          Batch mint
        </button>
      </nav>

      {auth === "required" ? (
        <LoginScreen
          onLoggedIn={() => {
            setAuth("ok");
            void refreshBadgeTypes();
          }}
        />
      ) : (
        <>
          <div className="header-actions">
            <button
              className="btn ghost"
              onClick={() => void refreshBadgeTypes()}
              title="Reload data"
            >
              ⟳ Refresh
            </button>
            {getToken() && (
              <button
                className="btn ghost"
                onClick={() => {
                  logout();
                  setAuth("required");
                }}
                title="Sign out"
              >
                Sign out
              </button>
            )}
          </div>

          {loadError && <Notice kind="error" text={`Backend unreachable: ${loadError}`} />}

          {loading ? (
            <div className="empty">Loading…</div>
          ) : (
            <>
              {tab === "badges" && <BadgesTab />}
              {tab === "events" && <EventsTab badgeTypes={badgeTypes} />}
              {tab === "mint" && <BatchMintTab badgeTypes={badgeTypes} />}
            </>
          )}
        </>
      )}

      <footer className="footer">
        <p>UnityCommunity NFT badges · admin dashboard</p>
      </footer>
    </div>
  );
}
