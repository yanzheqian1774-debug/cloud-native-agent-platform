"""Internal single-statement task facts, not an authorized browser response.

Call only within the existing owner transaction. The caller must filter exact
permissions before exposing any row or count. Do not return this raw snapshot:
preparation/resource bindings and conversation identities have separate policies.
"""

from .workbench_owner_authorization import WorkbenchOwnerError

# Bounded admission fails the entire read rather than presenting a partial total.
MAX_SNAPSHOT_RUNS = 10000

SNAPSHOT_SQL = """
WITH runs AS MATERIALIZED (
 SELECT p.*, g.version AS progress_version, g.record AS progress,
        g.updated_at AS progress_updated_at
 FROM execution_authority.run_preparations p
 LEFT JOIN execution_authority.prepared_run_progress g
   USING(namespace,security_domain,workflow_run_id)
 WHERE p.namespace=%s AND p.security_domain=%s
 ORDER BY p.created_at DESC,p.workflow_run_id DESC
 LIMIT %s
)
SELECT p.namespace,p.security_domain,p.workflow_run_id,p.digest,p.record preparation,
 p.created_at,p.progress_version,p.progress,p.progress_updated_at,
 statement_timestamp() read_at,
 r.business_problem_id,r.revision_id problem_revision_id,r.digest problem_digest,
 r.title,
 (SELECT coalesce(jsonb_agg(DISTINCT s.actor_id),'[]'::jsonb)
  FROM execution_authority.prepared_start_commands s
  WHERE (s.namespace,s.security_domain,s.workflow_run_id)=
        (p.namespace,p.security_domain,p.workflow_run_id)) initiators,
 (SELECT coalesce(jsonb_agg(jsonb_build_object(
    'contextId',o.context_id,'subjectId',q.subject_id,
    'recordSubjectId',q.record->>'subject_id',
    'recordContextId',q.record->>'context_id',
    'conversationId',q.record->>'conversation_id',
    'conversationOwnerId',c.owner_id,'conversationSchema',c.schema_version,
    'messageAuthorId',m.author_id,'messageSchema',m.schema_version,
    'messagePredatesRun',m.created_at<=p.created_at,
    'messageIsUser',m.message_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM private_conversation.message_facts f
      WHERE (f.tenant_id,f.security_domain,f.conversation_id,f.message_id)=
            (m.tenant_id,m.security_domain,m.conversation_id,m.message_id)),
    'invocation',jsonb_build_object(
      'contextId',v.record->>'contextId','state',v.record->>'state',
      'resultKind',v.record->>'resultKind',
      'initiatingPrincipalId',v.record->>'initiatingPrincipalId',
      'problemId',v.record->>'problemId',
      'problemRevisionId',v.record->>'problemRevisionId',
      'problemDigest',v.record->>'problemDigest'))),'[]'::jsonb)
  FROM authorization_admin.context_call_objects o
  LEFT JOIN authorization_admin.context_call_requests q
    ON (q.tenant_id,q.security_domain,q.context_id)=
       (o.tenant_id,o.security_domain,o.context_id)
  LEFT JOIN private_conversation.conversations c
    ON (c.tenant_id,c.security_domain,c.conversation_id)=
       (o.tenant_id,o.security_domain,q.record->>'conversation_id')
  LEFT JOIN private_conversation.messages m
    ON (m.tenant_id,m.security_domain,m.conversation_id,m.message_id)=
       (c.tenant_id,c.security_domain,c.conversation_id,
        q.record->>'first_user_message_id')
  LEFT JOIN LATERAL (
    SELECT record FROM draft_assistance.invocation_versions v
    WHERE (v.namespace,v.security_domain,v.invocation_id)=
          (o.tenant_id,o.security_domain,o.invocation_id)
    ORDER BY aggregate_version DESC LIMIT 1
  ) v ON true
  WHERE o.tenant_id=p.namespace AND o.security_domain=p.security_domain
    AND o.owner='BUSINESS_PROBLEM' AND o.resource_id=r.business_problem_id
 ) attribution_sources,
 (SELECT count(*) FROM execution_authority.run_artifacts a
  WHERE (a.namespace,a.security_domain,a.workflow_run_id)=
        (p.namespace,p.security_domain,p.workflow_run_id)) artifact_count,
 h.version outcome_version,o.resolution business_resolution,
 (SELECT coalesce(jsonb_agg(jsonb_build_object(
    'invocationId',q.skill_invocation_id,'questionKey',q.result->>'questionKey',
    'questionDigest',q.request_digest,'expiresAt',q.result->>'expiresAt',
    'answered',a.result IS NOT NULL,
    'answerDigest',CASE WHEN a.result IS NOT NULL THEN a.request_digest END)
    ORDER BY q.skill_invocation_id,q.record_key),'[]'::jsonb)
  FROM skill_invocation.invocations i
  JOIN skill_invocation.native_loop_records q
    USING(namespace,security_domain,skill_invocation_id)
  LEFT JOIN skill_invocation.native_loop_records a
    ON (a.namespace,a.security_domain,a.skill_invocation_id)=
       (q.namespace,q.security_domain,q.skill_invocation_id)
    AND a.record_key=(q.result->>'questionKey')||':answer'
  WHERE (i.namespace,i.security_domain,i.workflow_run_id)=
        (p.namespace,p.security_domain,p.workflow_run_id)
    AND q.result->>'kind'='NATIVE_QUESTION') questions,
 (SELECT coalesce(jsonb_agg(jsonb_build_object(
    'conversationId',l.conversation_id,'ownerId',c.owner_id,
    'schemaVersion',c.schema_version,
    'journeyMatches',coalesce(j.state->>'execution'=p.digest,false))
    ORDER BY l.created_at,l.conversation_id,l.link_id),'[]'::jsonb)
  FROM private_conversation.links l
  JOIN private_conversation.conversations c
    USING(tenant_id,security_domain,conversation_id)
  LEFT JOIN private_conversation.journeys j
    USING(tenant_id,security_domain,conversation_id)
  WHERE l.tenant_id=p.namespace AND l.security_domain=p.security_domain
    AND l.target->>'problemId'=r.business_problem_id
    AND (l.target->>'executionDigest'=p.digest OR (
      l.target->>'executionDigest' IS NULL
      AND j.state->>'execution'=p.digest
      AND j.state#>>'{problem,business_problem_id}'=r.business_problem_id))) origins
FROM runs p
LEFT JOIN business_problem_authority.problem_revisions r
 ON r.namespace=p.namespace AND r.security_domain=p.security_domain
 AND r.business_problem_id=p.record#>>'{semantics,target,problem,resource_id}'
 AND r.revision_id=p.record#>>'{semantics,target,problem,revision_id}'
 AND r.digest=p.record#>>'{semantics,target,problem,digest}'
LEFT JOIN product_outcome.heads h
 ON (h.namespace,h.security_domain,h.workflow_run_id)=
    (p.namespace,p.security_domain,p.workflow_run_id)
LEFT JOIN product_outcome.outcomes o
 ON (o.namespace,o.security_domain,o.outcome_id)=
    (h.namespace,h.security_domain,h.outcome_id)
ORDER BY p.created_at DESC,p.workflow_run_id DESC
"""


def read_current_work_snapshot(connection, *, namespace: str, security_domain: str):
    rows = connection.execute(
        SNAPSHOT_SQL, (namespace, security_domain, MAX_SNAPSHOT_RUNS + 1)
    ).fetchall()
    if len(rows) > MAX_SNAPSHOT_RUNS:
        raise WorkbenchOwnerError("CURRENT_WORK_SNAPSHOT_CAPACITY", 503)
    return rows
