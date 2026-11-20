# DRAFT intent canonical bridge G1

The persisted IntentCommand canonical payload includes conversationRouting=false and expectedParentVersion=0. The original authenticated draft route removes false routing before the bridge, so strict claim rejected otherwise identical requests. This is a production canonicalization mismatch, not a fixture defect.

Only original_action with conversation intent headers and DRAFT revalidates/dumps the same BeginDraftAssistance model before claim. Existing immutable intent payloads/digests are not changed. True routing and every other content/source/parent/version field remain part of strict equality. Claimed UNKNOWN cannot invoke again. Headerless invocation and original invoke_owner are unchanged. No model policy/profile/adapter or pinned draft_assistance_api changes; no permission, schema or lifecycle expansion. This is internal G1 compatibility, not a new action or accepted contract.

Verification uses the original 13 actions cases plus precise canonical/persisted old-intent regressions on dedicated 64335, original random database fixture, no actual model/runtime.
