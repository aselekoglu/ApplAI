import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import { apiClient } from "../../lib/api-client";
import type { AiTaskKind, AiTaskRecord } from "../../lib/types";
import { isAiTaskActive } from "./ai-task-labels";

const AI_TASK_QUEUE_MINIMIZED_STORAGE_KEY = "applai.aiTaskQueue.minimized";
const AI_TASK_QUEUE_POLL_INTERVAL_MS = 3000;

export interface SubmitAiTaskPayload {
  kind: AiTaskKind;
  title: string;
  related_label?: string;
  input: Record<string, unknown>;
}

export interface AiTaskQueueContextValue {
  tasks: AiTaskRecord[];
  visibleTasks: AiTaskRecord[];
  loading: boolean;
  error: string | null;
  isMinimized: boolean;
  hasActiveTask: boolean;
  refreshTasks: () => Promise<void>;
  submitTask: (payload: SubmitAiTaskPayload) => Promise<AiTaskRecord>;
  cancelTask: (taskId: string) => Promise<void>;
  hideTask: (taskId: string) => void;
  setIsMinimized: (value: boolean) => void;
}

const AiTaskQueueContext = createContext<AiTaskQueueContextValue | undefined>(undefined);

function readInitialMinimizedState(): boolean {
  try {
    return window.localStorage.getItem(AI_TASK_QUEUE_MINIMIZED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function persistMinimizedState(value: boolean): void {
  try {
    window.localStorage.setItem(AI_TASK_QUEUE_MINIMIZED_STORAGE_KEY, String(value));
  } catch {
    // localStorage can be unavailable in restricted browser contexts.
  }
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "AI task request failed.";
}

export function AiTaskQueueProvider({ children }: PropsWithChildren) {
  const [tasks, setTasks] = useState<AiTaskRecord[]>([]);
  const [hiddenTaskIds, setHiddenTaskIds] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMinimizedState, setIsMinimizedState] = useState(readInitialMinimizedState);
  const refreshInFlightRef = useRef<Promise<void> | null>(null);
  const mutationVersionRef = useRef(0);

  const loadTasks = useCallback((showLoading: boolean): Promise<void> => {
    if (refreshInFlightRef.current) {
      return refreshInFlightRef.current;
    }

    const mutationVersion = mutationVersionRef.current;
    if (showLoading) {
      setLoading(true);
    }

    const request = (async () => {
      try {
        const response = await apiClient.listAiTasks();
        if (mutationVersion === mutationVersionRef.current) {
          setTasks(response.tasks);
          setError(null);
        }
      } catch (err) {
        if (mutationVersion === mutationVersionRef.current) {
          setError(getErrorMessage(err));
        }
      } finally {
        refreshInFlightRef.current = null;
        if (showLoading) {
          setLoading(false);
        }
      }
    })();

    refreshInFlightRef.current = request;
    return request;
  }, []);

  const refreshTasks = useCallback(() => loadTasks(true), [loadTasks]);

  const refreshTasksAfterCurrentRequest = useCallback(() => {
    const currentRequest = refreshInFlightRef.current;
    void (currentRequest ?? Promise.resolve()).then(() => loadTasks(false));
  }, [loadTasks]);

  useEffect(() => {
    void refreshTasks();
  }, [refreshTasks]);

  const hasActiveTask = useMemo(() => tasks.some(isAiTaskActive), [tasks]);

  useEffect(() => {
    if (!hasActiveTask) return undefined;

    let timeoutId: number | undefined;
    let cancelled = false;

    const schedulePoll = () => {
      timeoutId = window.setTimeout(async () => {
        await loadTasks(false);
        if (!cancelled) {
          schedulePoll();
        }
      }, AI_TASK_QUEUE_POLL_INTERVAL_MS);
    };

    schedulePoll();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [hasActiveTask, loadTasks]);

  const setIsMinimized = useCallback((value: boolean) => {
    setIsMinimizedState(value);
    persistMinimizedState(value);
  }, []);

  const submitTask = useCallback(
    async (payload: SubmitAiTaskPayload) => {
      const task = await apiClient.createAiTask(payload);
      mutationVersionRef.current += 1;
      setTasks((currentTasks) => [
        task,
        ...currentTasks.filter((currentTask) => currentTask.task_id !== task.task_id),
      ]);
      setHiddenTaskIds((currentIds) => {
        if (!currentIds.has(task.task_id)) return currentIds;
        const nextIds = new Set(currentIds);
        nextIds.delete(task.task_id);
        return nextIds;
      });
      setError(null);
      setIsMinimized(false);
      return task;
    },
    [setIsMinimized]
  );

  const cancelTask = useCallback(async (taskId: string) => {
    let task: AiTaskRecord;
    try {
      task = await apiClient.cancelAiTask(taskId);
    } catch (err) {
      setError(getErrorMessage(err));
      throw err;
    }

    mutationVersionRef.current += 1;
    setTasks((currentTasks) =>
      currentTasks.map((currentTask) => (currentTask.task_id === task.task_id ? task : currentTask))
    );
    setError(null);
    refreshTasksAfterCurrentRequest();
  }, [refreshTasksAfterCurrentRequest]);

  const hideTask = useCallback((taskId: string) => {
    setHiddenTaskIds((currentIds) => {
      const nextIds = new Set(currentIds);
      nextIds.add(taskId);
      return nextIds;
    });
  }, []);

  const visibleTasks = useMemo(
    () => tasks.filter((task) => !hiddenTaskIds.has(task.task_id)),
    [hiddenTaskIds, tasks]
  );

  const value = useMemo<AiTaskQueueContextValue>(
    () => ({
      tasks,
      visibleTasks,
      loading,
      error,
      isMinimized: isMinimizedState,
      hasActiveTask,
      refreshTasks,
      submitTask,
      cancelTask,
      hideTask,
      setIsMinimized,
    }),
    [
      cancelTask,
      error,
      hasActiveTask,
      hideTask,
      isMinimizedState,
      loading,
      refreshTasks,
      setIsMinimized,
      submitTask,
      tasks,
      visibleTasks,
    ]
  );

  return <AiTaskQueueContext.Provider value={value}>{children}</AiTaskQueueContext.Provider>;
}

export function useAiTaskQueue(): AiTaskQueueContextValue {
  const context = useContext(AiTaskQueueContext);
  if (!context) {
    throw new Error("useAiTaskQueue must be used within an AiTaskQueueProvider.");
  }
  return context;
}
