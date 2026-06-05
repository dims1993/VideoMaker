import { useCallback, useEffect, useState } from "react";
import type { PipelineState } from "../types/pipeline";
import type { Session } from "../types/session";
import {
  refreshWorkSessionPoll,
  subscribeWorkSessionPoll,
  type WorkSnapshot,
} from "../lib/workSessionPollStore";

/**
 * Una sola cadencia de poll por carpeta `work` (sobrevive HMR sin duplicar timers).
 */
export function useWorkSessionPoll(workApplied: string) {
  const [session, setSession] = useState<Session | null>(null);
  const [pipelineState, setPipelineState] = useState<PipelineState | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    const apply = (snap: WorkSnapshot) => {
      if (snap.session) setSession(snap.session);
      if (snap.pipeline) setPipelineState(snap.pipeline);
    };
    return subscribeWorkSessionPoll(workApplied, apply);
  }, [workApplied]);

  const refreshSession = useCallback(
    async (opts?: { showErrors?: boolean }) => {
      const showErrors = opts?.showErrors ?? true;
      if (showErrors) setFetchError(null);
      try {
        const r = await fetch(`/api/session?work=${encodeURIComponent(workApplied)}`);
        if (!r.ok) {
          const msg = await r.text();
          if (showErrors) {
            setFetchError(msg || "No se pudo cargar la sesión.");
            setSession(null);
          }
          return false;
        }
        const data = (await r.json()) as Session;
        setSession(data);
        return true;
      } catch (e) {
        if (showErrors) {
          setFetchError(e instanceof Error ? e.message : String(e));
          setSession(null);
        }
        return false;
      }
    },
    [workApplied],
  );

  const refreshPipeline = useCallback(async () => {
    const snap = await refreshWorkSessionPoll(workApplied);
    if (snap.pipeline) setPipelineState(snap.pipeline);
    if (snap.session) setSession(snap.session);
  }, [workApplied]);

  const refreshAll = useCallback(
    async (opts?: { showErrors?: boolean }) => {
      const ok = await refreshSession(opts);
      const snap = await refreshWorkSessionPoll(workApplied);
      if (snap.pipeline) setPipelineState(snap.pipeline);
      if (snap.session) setSession(snap.session);
      return ok;
    },
    [workApplied, refreshSession],
  );

  return {
    session,
    pipelineState,
    fetchError,
    setFetchError: setFetchError,
    refreshSession,
    refreshPipeline,
    refreshAll,
  };
}
