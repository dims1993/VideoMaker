import type { PipelineState } from "../types/pipeline";
import type { Session } from "../types/session";

const IDLE_MS = 10_000;
const ACTIVE_MS = 3500;

export type WorkSnapshot = {
  session: Session | null;
  pipeline: PipelineState | null;
};

function isBusy(st: PipelineState | null, session: Session | null): boolean {
  if (session?.status?.state === "running") return true;
  return !!st?.steps?.some((s) => s.state === "running");
}

async function fetchSession(work: string): Promise<Session | null> {
  try {
    const r = await fetch(`/api/session?work=${encodeURIComponent(work)}`);
    if (!r.ok) return null;
    return (await r.json()) as Session;
  } catch {
    return null;
  }
}

async function fetchPipeline(work: string): Promise<PipelineState | null> {
  try {
    const r = await fetch(`/api/pipeline/state?work=${encodeURIComponent(work)}`);
    if (!r.ok) return null;
    return (await r.json()) as PipelineState;
  } catch {
    return null;
  }
}

class WorkSessionPoller {
  private subscribers = new Set<(snap: WorkSnapshot) => void>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private idleStopTimer: ReturnType<typeof setTimeout> | null = null;
  private inFlight = false;
  private last: WorkSnapshot = { session: null, pipeline: null };
  private lastFetchAt = 0;

  constructor(private readonly work: string) {}

  get snapshot(): WorkSnapshot {
    return this.last;
  }

  subscribe(cb: (snap: WorkSnapshot) => void): () => void {
    if (this.idleStopTimer) {
      clearTimeout(this.idleStopTimer);
      this.idleStopTimer = null;
    }
    this.subscribers.add(cb);
    cb(this.last);
    const stale = Date.now() - this.lastFetchAt > IDLE_MS;
    if (this.subscribers.size === 1 && (stale || !this.timer)) {
      void this.tick(true);
    }
    return () => {
      this.subscribers.delete(cb);
      if (this.subscribers.size === 0) {
        this.idleStopTimer = setTimeout(() => this.stop(), 60_000);
      }
    };
  }

  private stop() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.inFlight = false;
  }

  private schedule(delayMs: number) {
    if (this.subscribers.size === 0) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.tick(false), delayMs);
  }

  private emit() {
    for (const cb of this.subscribers) {
      cb(this.last);
    }
  }

  async tick(force = false): Promise<void> {
    if (this.subscribers.size === 0) return;
    if (!force && (this.inFlight || document.visibilityState === "hidden")) {
      this.schedule(isBusy(this.last.pipeline, this.last.session) ? ACTIVE_MS : IDLE_MS);
      return;
    }
    if (this.inFlight) return;
    this.inFlight = true;
    try {
      const [session, pipeline] = await Promise.all([
        fetchSession(this.work),
        fetchPipeline(this.work),
      ]);
      this.last = {
        session: session ?? this.last.session,
        pipeline: pipeline ?? this.last.pipeline,
      };
      this.lastFetchAt = Date.now();
      this.emit();
    } finally {
      this.inFlight = false;
      const delay = isBusy(this.last.pipeline, this.last.session) ? ACTIVE_MS : IDLE_MS;
      this.schedule(delay);
    }
  }
}

const pollers = new Map<string, WorkSessionPoller>();

function pollerFor(work: string): WorkSessionPoller {
  let p = pollers.get(work);
  if (!p) {
    p = new WorkSessionPoller(work);
    pollers.set(work, p);
  }
  return p;
}

export function subscribeWorkSessionPoll(
  work: string,
  cb: (snap: WorkSnapshot) => void,
): () => void {
  return pollerFor(work).subscribe(cb);
}

export async function refreshWorkSessionPoll(work: string): Promise<WorkSnapshot> {
  const p = pollerFor(work);
  await p.tick(true);
  return p.snapshot;
}
