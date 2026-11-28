export type TutorialPart = "intro" | "answer";

// "answer" keeps the key of the first release so people who already finished it aren't shown it again.
const KEYS: Record<TutorialPart, string> = { intro: "tutorial:intro:v1", answer: "tutorial:v1" };

// Fallback when localStorage is blocked: each part then shows once per page session.
const seenThisSession = new Set<TutorialPart>();

export function tutorialSeen(part: TutorialPart): boolean {
  if (seenThisSession.has(part)) return true;
  try {
    return localStorage.getItem(KEYS[part]) === "seen";
  } catch {
    return false;
  }
}

export function markTutorialSeen(part: TutorialPart): void {
  seenThisSession.add(part);
  try {
    localStorage.setItem(KEYS[part], "seen");
  } catch {
    // Private mode or blocked storage: the in-memory set above still covers this session.
  }
}
