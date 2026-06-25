import { useCallback, useMemo } from "react";
import type { AiTaskRecord, TailorRunOptions } from "../../lib/types";
import { apiClient } from "../../lib/api-client";
import { isAiTaskActive } from "./ai-task-labels";
import {
  useAiTaskQueue,
  type SubmitAiTaskPayload,
} from "./AiTaskQueueContext";

type TailoringTaskInput = {
  master_id: string;
  job_description?: string;
  job_id?: string;
  options: TailorRunOptions;
};

export type AiTaskSubmitResult = {
  task: AiTaskRecord;
  created: boolean;
};

const inFlightSubmissions = new Map<string, Promise<AiTaskSubmitResult>>();

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(stableValue);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nestedValue]) => [key, stableValue(nestedValue)])
    );
  }
  return value;
}

function stableStringify(value: unknown): string {
  return JSON.stringify(stableValue(value));
}

function operationKey(kind: AiTaskRecord["kind"], input: Record<string, unknown>): string {
  if (kind === "render_cv" || kind === "rerun_tailoring") {
    return stableStringify({ kind, run_id: input.run_id });
  }

  return stableStringify({
    kind,
    master_id: input.master_id,
    job_id: input.job_id ?? null,
    job_description: input.job_description ?? null,
    options: input.options,
  });
}

function findMatchingActiveTask(
  tasks: AiTaskRecord[],
  key: string
): AiTaskRecord | undefined {
  return tasks.find(
    (task) => isAiTaskActive(task) && operationKey(task.kind, task.input) === key
  );
}

function submitUniqueTask(
  payload: SubmitAiTaskPayload,
  tasks: AiTaskRecord[],
  submitTask: (payload: SubmitAiTaskPayload) => Promise<AiTaskRecord>,
  refreshTasks: () => Promise<void>
): Promise<AiTaskSubmitResult> {
  const key = operationKey(payload.kind, payload.input);
  const existingRequest = inFlightSubmissions.get(key);
  if (existingRequest) {
    return existingRequest.then(({ task }) => ({ task, created: false }));
  }

  const contextTask = findMatchingActiveTask(tasks, key);
  if (contextTask) {
    return Promise.resolve({ task: contextTask, created: false });
  }

  const request = (async () => {
    try {
      const response = await apiClient.listAiTasks();
      const serverTask = findMatchingActiveTask(response.tasks, key);
      if (serverTask) {
        await refreshTasks();
        return { task: serverTask, created: false };
      }

      const task = await submitTask(payload);
      return { task, created: true };
    } finally {
      inFlightSubmissions.delete(key);
    }
  })();
  inFlightSubmissions.set(key, request);
  return request;
}

export function useAiTaskSubmit() {
  const { submitTask, refreshTasks, tasks } = useAiTaskQueue();

  const queueTailoring = useCallback(
    (input: TailoringTaskInput) => {
      const taskInput = input as unknown as Record<string, unknown>;
      const relatedLabel = [input.options.company_name, input.options.job_title]
        .filter(Boolean)
        .join(" - ");

      return submitUniqueTask(
        {
          kind: "tailor_cv",
          title: "Tailor CV",
          related_label: relatedLabel || input.master_id,
          input: taskInput,
        },
        tasks,
        submitTask,
        refreshTasks
      );
    },
    [refreshTasks, submitTask, tasks]
  );

  const queueRender = useCallback(
    (run_id: string, related_label = "") => {
      const input = { run_id };
      return submitUniqueTask(
        {
          kind: "render_cv",
          title: "Render CV",
          related_label,
          input,
        },
        tasks,
        submitTask,
        refreshTasks
      );
    },
    [refreshTasks, submitTask, tasks]
  );

  const queueRerun = useCallback(
    (run_id: string, related_label = "") => {
      const input = { run_id };
      return submitUniqueTask(
        {
          kind: "rerun_tailoring",
          title: "Rerun tailoring",
          related_label,
          input,
        },
        tasks,
        submitTask,
        refreshTasks
      );
    },
    [refreshTasks, submitTask, tasks]
  );

  return useMemo(
    () => ({ queueTailoring, queueRender, queueRerun }),
    [queueRender, queueRerun, queueTailoring]
  );
}
