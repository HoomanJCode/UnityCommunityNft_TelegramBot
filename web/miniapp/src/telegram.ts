/**
 * Telegram WebApp helpers.
 *
 * Inside Telegram, the official script (index.html) exposes
 * `window.Telegram.WebApp`. Outside Telegram (plain browser dev) we fall back
 * to an optional dev-only initData from VITE_DEV_INIT_DATA.
 */

interface TelegramWebApp {
  initData: string;
  ready(): void;
  expand(): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

/** Tell Telegram the app is ready and expand to full height. */
export function initTelegramWebApp(): void {
  const webApp = window.Telegram?.WebApp;
  if (webApp) {
    webApp.ready();
    webApp.expand();
  }
}

/**
 * The signed initData string used to authenticate Mini App API requests.
 * Empty string when running outside Telegram without a dev override.
 */
export function getInitData(): string {
  const devInitData = import.meta.env.VITE_DEV_INIT_DATA as string | undefined;
  if (devInitData) {
    return devInitData;
  }
  return window.Telegram?.WebApp?.initData ?? "";
}

/** True when running inside the Telegram client (or a dev override is set). */
export function hasTelegramAuth(): boolean {
  return getInitData().length > 0;
}
