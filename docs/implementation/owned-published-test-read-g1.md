# G1 — bounded published Skill/Employee test READ

Base 8c plus frozen 82-file integration patch. No actual activation or policy changes.

Add explicit v2 policy subclass; v1 schema/dump/digest and static historical targets remain unchanged. Empty v2 selectors have no effect. Installation configuration selects only the two approved logical IDs and an explicitly pinned published anchor revision/digest; no catalog/prefix wildcard. No MANAGE/CREATE/USE/START is emitted.

Reuse original issuer, subject list, tenant/domain, expiry, <=8h TTL, requestability, generation lock, snapshot checks, durable grant decisions and published:<selectionDigest>:nonce keys. One shared-lock publication snapshot determines current published revision (never draft head). Current static-grant tombstones for credentials and local-account credential/source IDs of the same subject/scope, and denied/revoked READ anywhere in the same logical lineage blocks successor issuance. UNKNOWN keeps its original key and does not create a successor automatically.

Semantics: administrator-curated test READ, not inferred creator ownership. Employee CREATE does not persist actor; no creator field, fabricated ownership or new migration is introduced. Each configured logical ID pins an actually published anchor revision/digest. Verify the current published revision is the anchor or a valid immutable predecessor descendant, with same scope/logical ID, canonical digest and actual PUBLISH facts. Drafts and unrelated/forked lineage are unavailable. Skill uses original revision content digest; Employee uses original repository reconstruction. The first configured anchors are exactly approved Skill6905/f606 and EmployeeCD2/df628; configuration does not automatically adopt other IDs.

Employee publication uses original repository _read with shared definition lock and its lifecycle interpretation. Both resource kinds contribute exact reference/content/state to the same dynamic selection digest as ontology. Changed publication conflicts with old selection/key. Shared locks persist through the original READ preparation commit, excluding head-change races.

No new persistent infrastructure. Production configs default unchanged/off. Remaining resource kinds deliberately not covered. PG validation must distinguish actual owner-created facts from fixture-only setup and prove wrong anchor/unpublished/cross-scope/lineage revoke/selection mismatch/replay boundaries.

## Configuration delta (offline; no activation)

Keep the existing subjects, issuer/credentialPath, TTL, deadline, all static targets and publishedOntologyIds. Use a new policyVersion with schemaVersion `test-resource-read-policy.v2` and the following `publishedResources`. These are curated logical resources, not permission to manage them or claims that all resources are open:

```json
[
  {"kind":"skill","logicalId":"skill-definition:6905a0a3-a2b2-4b99-a8b4-c63986be10ff","anchorRevision":"skill-revision:f6064c42-1ee1-4dd8-8c12-577be278ba0a","anchorDigest":"87ac1987decd1935ebcdca2a4b6067545ecd4a03509de2f4330bc3c728296b8f","purpose":"RESOURCE_PREPARATION"},
  {"kind":"employee","logicalId":"employee-definition:cd2db4fc-47a9-4420-8953-9ce67fcedb62","anchorRevision":"employee-revision:df62814e-2066-4b97-956d-aa3969cbc1fd","anchorDigest":"50ad0438e904883e2963870c2292ad688c1baafb05ee906ff505a011dd4934dc","purpose":"RESOURCE_PREPARATION"}
]
```

## Browser continuation

A validated Skill publication, Employee publication, or selected resource-upgrade receipt emits a read-refresh notification. TestResourceAccess rereads current status and uses the original owner coordinator, waiting for any existing request first. This event is not authority: only the backend policy and current exact READ owner issue access. A prior UNKNOWN with a different selection remains unresolved and requires existing explicit "读取新版资料" action; it is not silently retargeted. Reload retains selection-specific keys. A successful terminal old selection allows automatic READ-only preparation of a newly published one, without changing any old execution binding.

Browser notifications are per current tab. A different tab's publication is observed on its next existing status/prepare entry (reload or conversation read preparation); no background poll or new execution is introduced.


## Retained static tombstone identity (independent-review correction)

Current identity mapping includes generation.credentials plus local_accounts. Both local account credential_id and grant_source_id count, exactly as the existing authority reader does. A known mapping to a different subject/scope is not treated as the current user's revocation and supplies no authority. A relevant exact lineage static tombstone whose ID no longer has a trustworthy current mapping causes TEST_READ_LINEAGE_IDENTITY_UNVERIFIED: abort the entire READ preparation before submitting requests/decisions. Do not label that orphan REVOKED for the current user, infer historical ownership or manufacture a mapping. No new history table is introduced. Existing approved historical grants are not rewritten.
