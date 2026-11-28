/** Entirely synthetic: no account, credential, invocation or real resource identity. */
export const fixture={
 schemaVersion:'document-review-output.v1',operation:'RENDER_REPORT',
 sourceSnapshot:{resource_id:'fixture-source',revision_id:'fixture-source-v1',digest:'1'.repeat(64)},
 source:{schemaVersion:'document-review-source.v1',synthetic:true,documents:[
  {id:'fixture-submission',title:'合成提交材料',role:'SUBMISSION',scope:undefined as string|undefined,text:'# 合成提交材料\n## 交接责任\n唯一上线负责人：合成甲\n唯一上线负责人：合成乙\n## 变更范围\n影响范围：待确认\n## 验证依据\n验证记录：合成示例\n'},
  {id:'fixture-policy',title:'合成核对规范',role:'POLICY',scope:'合成范围',text:'# 合成核对规范\n只适用于本合成样本。\n## 交接责任\n同一系统与同一发布批次必须明确一位唯一上线负责人；多个不同人名仅在此单值约束下算冲突。\n## 变更范围\n影响范围不得填待确认。\n## 回退步骤\n生产变更应提供回退步骤、触发条件及负责人。\n## 验证依据\n记录存在不代表验证实际通过。\n'}
 ]},
 documentReview:{scope:'合成范围',documentId:'fixture-submission',policyId:'fixture-policy',sourceSnapshot:{resource_id:'fixture-source',revision_id:'fixture-source-v1',digest:'1'.repeat(64)},
 ruleBinding:{schema_version:'document-semantics-binding.v1',scope:'合成范围',source:{resource_id:'fixture-source',revision_id:'fixture-source-v1',digest:'1'.repeat(64)},ontology:{resource_id:'fixture-ontology',revision_id:'fixture-ontology-v1',digest:'2'.repeat(64)}},
 ruleResult:{schemaVersion:'document-rule-result.v1',scope:'合成范围',documentTitle:'合成提交材料',rulesDigest:'3'.repeat(64),sourceDigest:'4'.repeat(64),findings:[
 {ruleCode:'release_owner',ruleName:'唯一负责人',section:'交接责任',status:'CONFLICT',evidence:[{documentId:'fixture-submission',line:3,text:'唯一上线负责人：合成甲'},{documentId:'fixture-submission',line:4,text:'唯一上线负责人：合成乙'}]},
 {ruleCode:'impact_scope',ruleName:'明确范围',section:'变更范围',status:'UNKNOWN',evidence:[{documentId:'fixture-submission',line:6,text:'影响范围：待确认'}]},
 {ruleCode:'rollback',ruleName:'回退步骤',section:'回退步骤',status:'MISSING',evidence:[]},
 {ruleCode:'validation',ruleName:'验证记录',section:'验证依据',status:'SATISFIED',evidence:[{documentId:'fixture-submission',line:8,text:'验证记录：合成示例'}]}
 ]}}
};
