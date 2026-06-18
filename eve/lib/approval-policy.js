const GUARDED_ACTION_WORDS = ["submit", "publish", "send", "upload"];
const GUARDED_STATUSES = ["ready_to_submit", "submitted"];

export function requiresApproval(action, details = {}) {
  const normalizedAction = String(action ?? "").toLowerCase();
  const status = String(details.status ?? details.new_status ?? "").toLowerCase();
  if (GUARDED_STATUSES.includes(status)) return true;
  return GUARDED_ACTION_WORDS.some((word) => normalizedAction.includes(word));
}

export function assertApprovalAllowed(action, details = {}, approved = false) {
  if (requiresApproval(action, details) && !approved) {
    throw new Error(`Approval required before ${action}`);
  }
}
