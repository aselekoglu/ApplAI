import { useNavigate } from "react-router-dom";
import type { AiTaskRecord, AiTaskStatus } from "../../lib/types";
import { AI_TASK_STATUS_LABELS, isAiTaskActive } from "./ai-task-labels";
import { canOpenAiTask } from "./ai-task-restore";
import { useAiTaskQueue } from "./AiTaskQueueContext";

const TERMINAL_STATUSES: AiTaskStatus[] = ["succeeded", "failed", "cancelled"];

function isTerminalTask(task: AiTaskRecord): boolean {
  return TERMINAL_STATUSES.includes(task.status);
}

function statusClassName(status: AiTaskStatus): string {
  return `aiTaskQueueStatus aiTaskQueueStatus--${status}`;
}

export function AiTaskQueuePanel() {
  const navigate = useNavigate();
  const {
    visibleTasks,
    loading,
    error,
    isMinimized,
    refreshTasks,
    cancelTask,
    hideTask,
    setIsMinimized,
  } = useAiTaskQueue();

  const activeCount = visibleTasks.filter(isAiTaskActive).length;
  const displayCount = activeCount || visibleTasks.length;
  const hasFinishedTask = visibleTasks.some(isTerminalTask);
  const statusCounts = visibleTasks.reduce<Record<AiTaskStatus, number>>(
    (counts, task) => {
      counts[task.status] += 1;
      return counts;
    },
    { queued: 0, running: 0, succeeded: 0, failed: 0, cancelled: 0 }
  );
  const liveStatusSummary = [
    `${activeCount} active AI tasks`,
    `${statusCounts.queued} queued`,
    `${statusCounts.running} running`,
    `${statusCounts.succeeded} succeeded`,
    `${statusCounts.failed} failed`,
    `${statusCounts.cancelled} cancelled`,
    error ? "AI queue request failed" : "",
  ]
    .filter(Boolean)
    .join(". ");

  if (visibleTasks.length === 0 && !error) return null;

  function clearFinishedTasks(): void {
    visibleTasks.filter(isTerminalTask).forEach((task) => hideTask(task.task_id));
  }

  function openTask(task: AiTaskRecord): void {
    if (!canOpenAiTask(task) || !task.restore) return;
    navigate(task.restore.path, { state: task.restore.state });
    hideTask(task.task_id);
  }

  if (isMinimized) {
    return (
      <aside className="aiTaskQueueDock" aria-label="AI task queue">
        <span className="visuallyHidden" aria-live="polite" aria-atomic="true">
          {liveStatusSummary}
        </span>
        <button
          type="button"
          className={`aiTaskQueuePill${error ? " aiTaskQueuePill--error" : ""}`}
          onClick={() => setIsMinimized(false)}
          aria-label={`Expand AI task queue. ${activeCount} active, ${visibleTasks.length} total.${
            error ? " AI queue request failed." : ""
          }`}
          title="Expand AI task queue"
        >
          <span className="aiTaskQueueMark" aria-hidden="true">AI</span>
          <span className="aiTaskQueueIdentity" aria-hidden="true">Q</span>
          <span className="aiTaskQueueCount" aria-hidden="true">{displayCount}</span>
          {error ? <span className="aiTaskQueueErrorMark" aria-hidden="true">!</span> : null}
          <span className="aiTaskQueueChevron" aria-hidden="true">⌄</span>
        </button>
      </aside>
    );
  }

  return (
    <aside className="aiTaskQueueDock" aria-label="AI task queue">
      <span className="visuallyHidden" aria-live="polite" aria-atomic="true">
        {liveStatusSummary}
      </span>
      <section className="aiTaskQueuePanel">
        <header className="aiTaskQueueHeader">
          <div className="aiTaskQueueHeading">
            <span className="aiTaskQueueMark" aria-hidden="true">AI</span>
            <strong className="aiTaskQueueIdentity">Q</strong>
            <span className="aiTaskQueueSummary">{activeCount} active</span>
          </div>
          <div className="aiTaskQueueControls">
            {hasFinishedTask ? (
              <button
                type="button"
                className="aiTaskQueueTextAction"
                onClick={clearFinishedTasks}
                title="Hide all finished tasks"
              >
                Clear finished
              </button>
            ) : null}
            <button
              type="button"
              className="aiTaskQueueIconButton"
              onClick={() => setIsMinimized(true)}
              aria-label="Minimize AI task queue"
              title="Minimize AI task queue"
            >
              <span aria-hidden="true">−</span>
            </button>
          </div>
        </header>

        {error ? (
          <div className="aiTaskQueueNotice" role="alert">
            <span>
              <strong>AI queue request failed.</strong>
              <span className="aiTaskQueueNoticeDetail">{error}</span>
            </span>
            <button
              type="button"
              className="aiTaskQueueTextAction"
              onClick={() => void refreshTasks()}
              disabled={loading}
            >
              Retry
            </button>
          </div>
        ) : null}

        <ul className="aiTaskQueueList">
          {visibleTasks.map((task) => {
            const active = isAiTaskActive(task);
            const openable = canOpenAiTask(task);
            const content = (
              <>
                <span className={statusClassName(task.status)} aria-hidden="true" />
                <span className="aiTaskQueueBody">
                  <span className="aiTaskQueueTitle" title={task.title}>{task.title}</span>
                  <span className="aiTaskQueueMeta">
                    {task.related_label ? (
                      <span className="aiTaskQueueRelated" title={task.related_label}>
                        {task.related_label}
                      </span>
                    ) : null}
                    <span className={`aiTaskQueueState aiTaskQueueState--${task.status}`}>
                      {AI_TASK_STATUS_LABELS[task.status]}
                    </span>
                  </span>
                  {task.error ? (
                    <span className="aiTaskQueueError" title={task.error}>{task.error}</span>
                  ) : null}
                  {active ? (
                    <span className="aiTaskQueueProgress" aria-hidden="true">
                      <span />
                    </span>
                  ) : null}
                </span>
                {openable ? <span className="aiTaskQueueOpen" aria-hidden="true">›</span> : null}
              </>
            );

            return (
              <li key={task.task_id} className={`aiTaskQueueItem aiTaskQueueItem--${task.status}`}>
                {openable ? (
                  <button
                    type="button"
                    className="aiTaskQueueRow aiTaskQueueRow--openable"
                    onClick={() => openTask(task)}
                    aria-label={`Open result for ${task.title}`}
                    title="Open completed result"
                  >
                    {content}
                  </button>
                ) : (
                  <div className="aiTaskQueueRow">{content}</div>
                )}

                {task.status === "queued" ? (
                  <button
                    type="button"
                    className="aiTaskQueueDismiss"
                    onClick={() => {
                      void cancelTask(task.task_id).catch(() => undefined);
                    }}
                    aria-label={`Cancel queued task ${task.title}`}
                    title="Cancel queued task"
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                ) : isTerminalTask(task) ? (
                  <button
                    type="button"
                    className="aiTaskQueueDismiss"
                    onClick={() => hideTask(task.task_id)}
                    aria-label={`Dismiss ${task.title}`}
                    title="Dismiss task"
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>
    </aside>
  );
}
