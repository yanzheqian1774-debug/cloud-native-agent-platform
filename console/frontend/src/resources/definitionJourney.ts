export function exactDefinitionHref(kind:'agent'|'knowledge',identity:string,revision:string,digest:string){
 if(!identity||!revision||!/^[a-f0-9]{64}$/.test(digest))throw Error('DEFINITION_REFERENCE_INVALID');
 return (kind==='agent'?'/agents?':'/knowledge?')+new URLSearchParams({kind,query:identity,selected:identity,resourceRevision:revision,resourceDigest:digest});
}
