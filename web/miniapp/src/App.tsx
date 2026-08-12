import { useCallback, useEffect, useState } from "react";
import { TonConnectButton, useTonAddress } from "@tonconnect/ui-react";
import { Badge, fetchBadges, linkWallet } from "./api";
import { getInitData, hasTelegramAuth } from "./telegram";

function shortAddress(address: string): string {
  if (address.length <= 12) return address;
  return `${address.slice(0, 4)}…${address.slice(-4)}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function App() {
  const initData = getInitData();
  const authenticated = hasTelegramAuth();

  const walletAddress = useTonAddress(); // "" when not connected
  const connected = walletAddress.length > 0;

  const [linking, setLinking] = useState(false);
  const [linkedWallet, setLinkedWallet] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null);

  const [badges, setBadges] = useState<Badge[] | null>(null);
  const [badgesError, setBadgesError] = useState<string | null>(null);

  // Link the wallet to the backend once a wallet is connected.
  useEffect(() => {
    if (!authenticated || !connected || linking || linkedWallet === walletAddress) {
      return;
    }
    let cancelled = false;
    setLinking(true);
    setLinkError(null);
    linkWallet(initData, walletAddress)
      .then(() => {
        if (cancelled) return;
        setLinkedWallet(walletAddress);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setLinkError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLinking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authenticated, connected, initData, linking, linkedWallet, walletAddress]);

  // Load the badge gallery whenever we have a valid Telegram identity.
  const loadBadges = useCallback(async () => {
    if (!authenticated) return;
    setBadgesError(null);
    try {
      setBadges(await fetchBadges(initData));
    } catch (err) {
      setBadgesError((err as Error).message);
    }
  }, [authenticated, initData]);

  useEffect(() => {
    void loadBadges();
  }, [loadBadges, linkedWallet]);

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <span className="header-logo">🛡️</span>
          <div>
            <h1>UnityCommunity Badges</h1>
            <p>Your NFT badges from the community</p>
          </div>
        </div>
        <TonConnectButton />
      </header>

      {!authenticated ? (
        <section className="card notice">
          <h2>Open this Mini App from Telegram</h2>
          <p>
            This app authenticates you through Telegram. Open it via the bot
            (tap <code>Connect TON Wallet</code>) to link your wallet and see
            your badges.
          </p>
        </section>
      ) : (
        <>
          <section className="card wallet-card">
            <div className="wallet-status">
              {connected ? (
                <>
                  <span className="dot dot-ok" />
                  <div>
                    <strong>Wallet connected</strong>
                    <span className="mono">{shortAddress(walletAddress)}</span>
                  </div>
                </>
              ) : (
                <>
                  <span className="dot" />
                  <div>
                    <strong>Wallet not connected</strong>
                    <span>Connect your Telegram Wallet to receive badges</span>
                  </div>
                </>
              )}
            </div>

            {linking && <p className="hint">Linking wallet…</p>}
            {linkError && <p className="error">Wallet link failed: {linkError}</p>}
            {connected && linkedWallet === walletAddress && !linkError && (
              <p className="hint">✅ Wallet linked — you're ready to receive badges</p>
            )}
          </section>

          <section className="gallery">
            <div className="gallery-head">
              <h2>Your badges</h2>
              <button className="ghost-btn" onClick={() => void loadBadges()}>
                Refresh
              </button>
            </div>

            {badgesError && <p className="error">Couldn't load badges: {badgesError}</p>}

            {badges === null && !badgesError ? (
              <div className="empty">Loading…</div>
            ) : badges && badges.length > 0 ? (
              <div className="badge-grid">
                {badges.map((b) => (
                  <article key={b.assignment_id} className="badge-card">
                    {b.image_url ? (
                      <img className="badge-img" src={b.image_url} alt={b.badge_name} />
                    ) : (
                      <div className="badge-img placeholder">🎖️</div>
                    )}
                    <div className="badge-body">
                      <h3>{b.badge_name}</h3>
                      {b.description && <p>{b.description}</p>}
                      <div className="badge-meta">
                        {b.tx_hash && <span className="mono">{shortAddress(b.tx_hash)}</span>}
                        {b.minted_at && <span>{formatDate(b.minted_at)}</span>}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty">
                <p>No badges yet.</p>
                <p className="hint">
                  Join an event and an admin will mint a badge to your wallet.
                </p>
              </div>
            )}
          </section>
        </>
      )}

      <footer className="footer">
        <p>Demo project — testnet only. Not for production use.</p>
      </footer>
    </div>
  );
}
