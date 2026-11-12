import {RememberedDetails} from './RememberedDetails';
import {Link,useSearchParams} from 'react-router-dom';
import type {ExecutionView,Ref} from '../api/preparedExecution';

/** Saved bindings are read context, never permission or a request to execute. */
export function ExecutionSkillBindings({view,viewKey}:{view:ExecutionView;viewKey?:string}){
 const [params]=useSearchParams();
 const conversation=params.get('conversation')||params.get('returnConversation');
 const groups=new Map<string,{reference:Ref;titles:string[]}>();
 for(const participant of view.preparation.participants){
  const reference=participant.skill?.reference;
  if(!reference||!['resource_id','revision_id'].every(k=>typeof reference[k as keyof Ref]==='string'&&reference[k as keyof Ref].length>0)||!/^[a-f0-9]{64}$/.test(reference.digest))continue;
  const task=view.preparation.semantics.tasks.find(t=>t.task_id===participant.task_id);
  if(!task)continue;
  const key=JSON.stringify([reference.resource_id,reference.revision_id,reference.digest]),group=groups.get(key)??{reference,titles:[]};
  group.titles.push(view.taskTranslation?.tasks.find(t=>t.task_id===task.task_id)?.title??task.title);groups.set(key,group);
 }
 if(groups.size===0)return null;
 return <section className="px-result-card" aria-label="本次方案绑定的技能"><RememberedDetails viewKey={viewKey} name="skill-bindings" summary="使用的技能与版本依据"><p>查看本次执行保存的准确版本；读取资格在目标页核对。</p><ul>{Array.from(groups,([key,{reference,titles}])=>{
  const query=new URLSearchParams({selected:reference.resource_id,resourceRevision:reference.revision_id,resourceDigest:reference.digest,fromExecution:view.digest,...(conversation?{returnConversation:conversation}:{})});
  return <li key={key}><Link to={'/skills?'+query}>查看准确版本</Link><p>对应任务：{Array.from(new Set(titles)).join('、')}</p><details><summary>查看绑定依据</summary><dl><dt>资源</dt><dd>{reference.resource_id}</dd><dt>修订</dt><dd>{reference.revision_id}</dd><dt>摘要</dt><dd>{reference.digest}</dd></dl></details></li>;
 })}</ul></RememberedDetails></section>;
}
