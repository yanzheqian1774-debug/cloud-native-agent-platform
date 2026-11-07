import type {ResourceKind, SkillMcpResource} from '../api/skillMcpResources';

export type ManagementCommandIntent = {
  version: 1;
  commandKey: string;
  action: string;
  kind: ResourceKind;
  principal: string;
  identity?: string;
  expectedVersion?: number;
  viewResource: string | null;
};
export type ManagementReceipt = {
  schemaVersion: 'resource-management-receipt.v1';
  identity: string;
  kind: ResourceKind;
  action: string;
  commandKey: string;
  aggregateVersion: number;
  resource: SkillMcpResource;
  executionStarted: false;
  modelCalls: 0;
  credentialMaterial: 'NOT_INCLUDED';
  publicationVerification?: {ready: boolean};
};
const identity = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 200;
const actions = new Set(['create','import','edit','successor','validate','test','publish','publish-tested','health','discover','select-tools','disable','enable','deprecate','access']);

export function decodeManagementIntent(raw: string | null, key: string, kind: ResourceKind, principal: string): ManagementCommandIntent {
  if (!raw || raw.length > 5000) throw Error('RESOURCE_COMMAND_INTENT_MISSING');
  const intent = JSON.parse(raw) as ManagementCommandIntent;
  if (intent.version !== 1 || intent.commandKey !== key || intent.kind !== kind || intent.principal !== principal || !actions.has(intent.action)
    || !identity(key) || (intent.viewResource !== null && !identity(intent.viewResource))
    || (intent.identity !== undefined && !identity(intent.identity))
    || (intent.expectedVersion !== undefined && (!Number.isInteger(intent.expectedVersion) || intent.expectedVersion < 1))
    || (!['create','import'].includes(intent.action) && !intent.identity)) throw Error('RESOURCE_COMMAND_INTENT_INVALID');
  return intent;
}

export function verifyManagedResource(value: unknown): asserts value is SkillMcpResource {
  const r = value as SkillMcpResource | null;
  if (!r || !identity(r.resourceId) || !['skill','mcp'].includes(r.kind) || typeof r.name !== 'string'
    || !Number.isInteger(r.aggregateVersion) || r.aggregateVersion < 1 || !Array.isArray(r.revisions) || !r.revisions.length
    || r.revisions.some(x => !identity(x.revisionId) || typeof x.digest !== 'string' || !/^(sha256:)?[a-f0-9]{64}$/.test(x.digest) || !x.content || typeof x.content !== 'object')
    || (r.currentDraftRevisionId !== null && !r.revisions.some(x => x.revisionId === r.currentDraftRevisionId))
    || (r.publishedRevisionId !== null && !r.revisions.some(x => x.revisionId === r.publishedRevisionId))) throw Error('RESOURCE_COMMAND_RECEIPT_MISMATCH');
}

export function verifyManagementReceipt(value: unknown, intent: ManagementCommandIntent): ManagementReceipt {
  const r = value as ManagementReceipt | null;
  if (!r || r.schemaVersion !== 'resource-management-receipt.v1' || r.kind !== intent.kind || r.action !== intent.action
    || r.commandKey !== intent.commandKey || r.executionStarted !== false || r.modelCalls !== 0 || r.credentialMaterial !== 'NOT_INCLUDED'
    || (intent.identity !== undefined && r.identity !== intent.identity)) throw Error('RESOURCE_COMMAND_RECEIPT_MISMATCH');
  verifyManagedResource(r.resource);
  if (r.identity !== r.resource.resourceId || r.resource.kind !== intent.kind || r.aggregateVersion !== r.resource.aggregateVersion
    || (intent.expectedVersion !== undefined && r.aggregateVersion < intent.expectedVersion)
    || (intent.action === 'publish-tested' && r.publicationVerification?.ready !== true)) throw Error('RESOURCE_COMMAND_RECEIPT_MISMATCH');
  return r;
}
