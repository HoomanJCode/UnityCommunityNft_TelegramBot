/**
 * Thin client for the backend Mini App API (backend/api/mini_app.py).
 *
 * Requests go to the same origin — in dev, Vite proxies /miniapp → :8000.
 */

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/miniapp";

export interface WalletLinkResult {
  telegram_id: number;
  wallet_address: string;
  wallet_connected_at: string | null;
}

export interface Badge {
  assignment_id: number;
  badge_name: string;
  description: string | null;
  image_url: string | null;
  tx_hash: string | null;
  minted_at: string | null;
}

/** Link the connected TON wallet to the user's record. */
export async function linkWallet(
  initData: string,
  walletAddress: string
): Promise<WalletLinkResult> {
  const res = await fetch(`${API_BASE}/wallet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData, wallet_address: walletAddress }),
  });
  if (!res.ok) {
    throw new Error(`wallet link failed (${res.status})`);
  }
  return res.json();
}

/** Fetch the badges owned by the authenticated user. */
export async function fetchBadges(initData: string): Promise<Badge[]> {
  const res = await fetch(`${API_BASE}/badges`, {
    headers: { "X-Telegram-Init-Data": initData },
  });
  if (!res.ok) {
    throw new Error(`badges request failed (${res.status})`);
  }
  return res.json();
}
