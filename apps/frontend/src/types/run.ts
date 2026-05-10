/** Async UI tasks with global busy/error handling (see App `run()`). */
export type RunFn = (label: string, fn: () => Promise<void>) => Promise<void>;
