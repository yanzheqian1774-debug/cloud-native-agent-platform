import type {SkillMcpResource} from '../api/skillMcpResources';
// Cases do not carry a revision in the current owner contract: the saved result
// binds its testId to an exact revision/digest. Never infer it from array order.
export function savedTestCase(resource:SkillMcpResource,result:{resultId:string;testId?:string;revisionId:string;revisionDigest:string}|undefined){
 if(!result?.testId)return undefined;
 if(resource.testResults.filter(x=>x.resultId===result.resultId&&x.testId===result.testId&&x.revisionId===result.revisionId&&x.revisionDigest===result.revisionDigest).length!==1)return undefined;
 if(resource.revisions.filter(x=>x.revisionId===result.revisionId&&x.digest===result.revisionDigest).length!==1)return undefined;
 const cases=resource.savedTests.filter(x=>x.testId===result.testId);
 if(cases.length!==1)return undefined;
 const candidate=cases[0] as typeof cases[number]&{revisionId?:string;revisionDigest?:string};
 if((candidate.revisionId!==undefined||candidate.revisionDigest!==undefined)&&(candidate.revisionId!==result.revisionId||candidate.revisionDigest!==result.revisionDigest))return undefined;
 return candidate;
}
