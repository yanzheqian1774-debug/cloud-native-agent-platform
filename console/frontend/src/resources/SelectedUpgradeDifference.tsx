import type {UpgradePreview,UpgradeSelection} from '../api/resourceUpgrades';

function VersionChange({name,before,after}:{name:string;before:string;after:string}) {
 return <div className="rd-diff-item"><strong>{name}</strong><p>当前引用 → 本次新版本</p><details><summary>核对准确版本</summary><dl><dt>更新前</dt><dd style={{overflowWrap:'anywhere'}}>{before}</dd><dt>更新后</dt><dd style={{overflowWrap:'anywhere'}}>{after}</dd></dl></details></div>;
}

export function SelectedUpgradeDifference({preview,selection,names,resourceName}:{preview:UpgradePreview;selection:UpgradeSelection;names:{kind:string;identity:string;name?:string}[];resourceName:string}) {
 const name=(kind:string,id:string)=>kind===(selection.resourceKind??'skill').toUpperCase()?resourceName:names.find(n=>n.kind===kind&&n.identity===id)?.name??id;
 return <div aria-label="本次准确引用变化">
  <VersionChange name={resourceName} before={selection.oldSkill.revisionId} after={selection.newSkill.revisionId}/>
  {preview.preview.employees.map(({before,after})=><section key={before.definitionId}><h4>{before.role} · 数字人</h4>
   {after.members.filter(m=>before.members.some(old=>old.kind===m.kind&&old.resource_id===m.resource_id&&old.revision_id!==m.revision_id)).map(m=>{
    const old=before.members.find(old=>old.kind===m.kind&&old.resource_id===m.resource_id)!;
    const responsibilities=(after.responsibilityBindings??[]).filter(b=>b.member.kind===m.kind&&b.member.resource_id===m.resource_id).map(b=>b.responsibility);
    return <div key={m.kind+':'+m.resource_id}><VersionChange name={name(m.kind,m.resource_id)} before={old.revision_id} after={m.revision_id}/><p>{responsibilities.length?'以下职责改用该新版本：'+responsibilities.join('；'):'该引用未关联具体职责，本次不新增职责关联。'}</p></div>;
   })}<p>职责内容保持不变。</p></section>)}
  {preview.preview.capabilities.map(c=><section key={c.capabilityId}><h4>{name('BUSINESS_CAPABILITY',c.capabilityId)} · 业务能力</h4>{c.bindingChanges.map(b=><div key={b.kind+':'+b.resourceId}><VersionChange name={name(b.kind,b.resourceId)} before={b.before?.reference.revision_id??'无引用'} after={b.after?.reference.revision_id??'无引用'}/><p>用途：{b.after?.purpose??b.before?.purpose??'未声明'}</p></div>)}</section>)}
  <p>未选引用、历史任务和已有成果保持原版本；本次发布不触发重新执行。</p>
 </div>;
}
