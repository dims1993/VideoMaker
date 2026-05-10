export type PipelineStepState = {
  id: string;
  title: string;
  state: "idle" | "running" | "done" | "error";
  detail?: string;
  updated_at?: string;
};

export type PipelineState = {
  state: "idle" | "running" | "done" | "error";
  current_step?: string | null;
  steps: PipelineStepState[];
  last_error?: string | null;
};
