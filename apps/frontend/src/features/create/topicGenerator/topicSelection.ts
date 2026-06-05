import type { TopicIdea } from "./types";

function norm(s: string): string {
  return s.trim().toLowerCase();
}

/** Índice del tema que coincide con keywords/ángulo de sesión. */
export function findTopicIndexForSession(
  topics: TopicIdea[],
  keywords: string,
  context: string,
): number | null {
  const kw = keywords.trim();
  const ctx = context.trim();
  if (!kw && !ctx) return null;
  if (kw) {
    const want = norm(kw);
    for (let i = 0; i < topics.length; i++) {
      if (norm(topics[i].title) === want) return i;
    }
  }
  if (ctx) {
    const want = norm(ctx);
    for (let i = 0; i < topics.length; i++) {
      if (norm(topics[i].angle) === want) return i;
    }
  }
  return null;
}

export function isTopicSelectedForPrompt(
  selectedIndex: number | null,
  topics: TopicIdea[],
  keywords: string,
  context: string,
): boolean {
  if (topics.length === 0) return true;
  if (selectedIndex != null && selectedIndex >= 0) return true;
  return findTopicIndexForSession(topics, keywords, context) != null;
}
