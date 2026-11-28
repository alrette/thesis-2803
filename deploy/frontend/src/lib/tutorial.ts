const KEY = "tutorial:v1";

// Fallback when localStorage is blocked: the tour then shows once per page session.
let seenThisSession = false;

export function tutorialSeen(): boolean {
  if (seenThisSession) return true;
  try {
    return localStorage.getItem(KEY) === "seen";
  } catch {
    return false;
  }
}

export function markTutorialSeen(): void {
  seenThisSession = true;
  try {
    localStorage.setItem(KEY, "seen");
  } catch {
    // Private mode or blocked storage: the in-memory flag above still covers this session.
  }
}
