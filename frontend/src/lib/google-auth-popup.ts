"use client";

export const GOOGLE_AUTH_COMPLETE_MESSAGE = "archon:google-auth-complete";

const POPUP_WIDTH = 600;
const POPUP_HEIGHT = 700;

export function openGoogleAuthPopup(name: string): Window | null {
  const left = window.screenX + Math.max(0, (window.outerWidth - POPUP_WIDTH) / 2);
  const top = window.screenY + Math.max(0, (window.outerHeight - POPUP_HEIGHT) / 2);

  const popup = window.open(
    "",
    name,
    `popup=yes,width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${Math.round(left)},top=${Math.round(top)}`
  );

  if (!popup) {
    return null;
  }

  try {
    popup.document.title = "Connecting to Google";
    popup.document.body.innerHTML =
      "<div style=\"margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#09090b;color:#f4f4f5;font:16px system-ui,sans-serif;\">Connecting to Google...</div>";
  } catch {
    /* popup contents are best-effort only */
  }

  return popup;
}

export function isGoogleAuthCompleteMessage(event: MessageEvent): boolean {
  return (
    event.origin === window.location.origin &&
    typeof event.data === "object" &&
    event.data !== null &&
    "type" in event.data &&
    event.data.type === GOOGLE_AUTH_COMPLETE_MESSAGE
  );
}

export function notifyGoogleAuthComplete(): void {
  window.opener?.postMessage({ type: GOOGLE_AUTH_COMPLETE_MESSAGE }, window.location.origin);
}
