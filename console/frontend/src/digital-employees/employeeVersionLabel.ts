import type {EmployeeAuthoring,EmployeeDefinition} from '../api/digitalEmployees';

export function employeeVersionLabel(item:EmployeeDefinition,value:EmployeeAuthoring|undefined,error?:string){
 const same=(definition:EmployeeDefinition)=>definition.employeeDefinitionRevisionId===item.employeeDefinitionRevisionId&&definition.employeeDefinitionDigest===item.employeeDefinitionDigest;
 if(!value)return (item.publicationState==='PUBLISHED'?'已发布记录':'所选未发布修订')+(error?' · 当前状态暂不可核实':' · 状态核对中');
 if(value.publication.status==='AVAILABLE'&&same(value.publication.definition))return '当前发布版本';
 if(value.draft.status==='AVAILABLE'&&same(value.draft.definition))return value.draft.definition.lifecycleState==='VALIDATED'?'修改草稿 · 已验证':value.draft.definition.lifecycleState==='APPROVED'?'修改草稿 · 待发布':'修改草稿 · 待验证';
 if(item.publicationState==='PUBLISHED'){
  if(value.publication.status==='AVAILABLE')return same(value.publication.definition)?'当前发布版本':'历史发布版本';
  return value.publication.status==='WITHDRAWN'?'已发布记录 · 当前发布已撤销':'已发布记录 · 当前版本待核实';
 }
 return value.head.status==='AVAILABLE'&&!same(value.head.definition)?'历史修订 · 未发布':'所选未发布修订';
}
