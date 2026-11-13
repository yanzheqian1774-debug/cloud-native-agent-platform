export type FixedTeam = {teamId:string;revisionId:string;digest:string};
export type FixedTrigger = {kind:'SCHEDULE'|'EVENT';timezone:string|null;localTime:string|null;cadence:'DAILY'|'WEEKDAY'|null;eventDescription:string|null};
export type FixedCommand = {workId:string;revisionId:string;predecessorRevisionId:string|null;expectedVersion:number;commandId:string;title:string;instruction:string;trigger:FixedTrigger};
export type FixedDraft = {schemaVersion:'fixed-work-draft.v1';state:'DRAFT_ONLY';team:FixedTeam;workId:string;revisionId:string;predecessorRevisionId:string|null;aggregateVersion:number;title:string;instruction:string;trigger:FixedTrigger;createdBy:string;createdAt:string};
export type FixedItem = {draft:FixedDraft;digest:string};
export type FixedResult = FixedItem & {aggregateVersion:number;executionEnabled:false;authorityGranted:false;triggerCreated:false;validation:'CONFIGURATION_STRUCTURE_ONLY'};
export type FixedPage = {items:FixedItem[];team:FixedTeam;nextCursor:string|null;configurationCanSave:boolean;executionEnabled:false;authorityGranted:false;triggerCreated:false};
function canonical(value:unknown):string {
 if(typeof value==='string')return JSON.stringify(value.normalize('NFC'));
 if(value===null||typeof value==='number'||typeof value==='boolean')return JSON.stringify(value);
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical((value as Record<string,unknown>)[k])).join(',')+'}';
 throw Error('配置内容尚未核实。');
}
export async function verifyFixedItem(item:FixedItem,team:FixedTeam,expected?:FixedCommand){
 const d=item?.draft;
 if(!d||d.schemaVersion!=='fixed-work-draft.v1'||d.state!=='DRAFT_ONLY'||canonical(d.team)!==canonical(team)||!Number.isInteger(d.aggregateVersion)||d.aggregateVersion<1||!d.title?.trim()||!d.instruction?.trim()||!d.workId||!d.revisionId||!d.createdBy||!Number.isFinite(Date.parse(d.createdAt)))throw Error('配置与所选团队版本不一致。');
 const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(d)));
 if([...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('')!==item.digest)throw Error('配置内容与读取依据不一致。');
 if(expected&&(d.workId!==expected.workId||d.revisionId!==expected.revisionId||d.predecessorRevisionId!==expected.predecessorRevisionId||d.aggregateVersion!==expected.expectedVersion+1||d.title!==expected.title||d.instruction!==expected.instruction||canonical(d.trigger)!==canonical(expected.trigger)))throw Error('保存结果与本次说明不一致。');
 return item;
}
export function verifyFixedFlags(value:{executionEnabled:boolean;authorityGranted:boolean;triggerCreated:boolean}){
 if(!value||value.executionEnabled!==false||value.authorityGranted!==false||value.triggerCreated!==false)throw Error('配置状态尚未核实。');
}
