import assert from "node:assert/strict";
import test from "node:test";

import { assertApprovalAllowed, requiresApproval } from "../lib/approval-policy.js";

test("approval policy gates external and ready-to-submit actions", () => {
  assert.equal(requiresApproval("submit_application"), true);
  assert.equal(requiresApproval("publish_linkedin_post"), true);
  assert.equal(requiresApproval("send_email"), true);
  assert.equal(requiresApproval("upload_cv"), true);
  assert.equal(requiresApproval("save_application", { status: "ready_to_submit" }), true);
});

test("approval policy allows scoring, rendering, and draft saves", () => {
  assert.equal(requiresApproval("score_job"), false);
  assert.equal(requiresApproval("render_cv"), false);
  assert.equal(requiresApproval("save_application", { status: "draft" }), false);
});

test("approval assertion throws when a guarded action is not approved", () => {
  assert.throws(() => assertApprovalAllowed("submit_application", {}, false), /Approval required/);
  assert.doesNotThrow(() => assertApprovalAllowed("submit_application", {}, true));
});
