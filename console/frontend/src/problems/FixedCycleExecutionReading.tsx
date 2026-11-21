import {useRef} from 'react';
import {Link} from 'react-router-dom';
import type {ExecutionView} from '../api/preparedExecution';
import {PreparedDeliverySummary} from './PreparedDeliverySummary';
import {ExecutionWorkView} from './ExecutionWorkView';
import {readViewString,saveViewString,useViewString} from './workViewState';

/** Presentation of an already verified exact cycle. No execution/answer commands. */
export function FixedCycleExecutionReading({view,viewKey,conversation}:{view:ExecutionView;viewKey:string;conversation:string}){
 const [tab,setTab]=useViewString(viewKey,'tab','result'),[artifact,setArtifact]=useViewString(viewKey,'artifact'),[review,setReview]=useViewString(viewKey,'review');
 const section=useRef<HTMLElement>(null);
 function inspect(identity:string){
  const stream=section.current?.closest('.px-message-stream');
  if(stream)saveViewString(viewKey,'artifactReturnScroll',String(stream.scrollTop));
  saveViewString(viewKey,'artifactReturnTab',tab);setArtifact(identity);setTab('result');
 }
 function close(){setArtifact('');setTab(readViewString(viewKey,'artifactReturnTab','result'));requestAnimationFrame(()=>{const stream=section.current?.closest('.px-message-stream'),top=Number(readViewString(viewKey,'artifactReturnScroll','0'));if(stream&&Number.isFinite(top)){stream.dispatchEvent(new Event('wheel',{bubbles:true}));stream.scrollTop=top}})}
 return <section ref={section} aria-label="本次周期的过程与成果" data-execution-digest={view.digest}>
  <nav className="work-view-tabs" aria-label="本次运行视图"><button type="button" aria-pressed={tab!=='process'} onClick={()=>setTab('result')}>成果与记录</button><button type="button" aria-pressed={tab==='process'} onClick={()=>setTab('process')}>办理过程</button></nav>
  {tab==='process'?<ExecutionWorkView view={view} viewKey={viewKey} onArtifact={inspect}/>:<>
   {view.artifacts.length?<PreparedDeliverySummary view={view} viewKey={viewKey} selectedArtifact={artifact} onArtifact={inspect} onCloseArtifact={close} query="" onReview={()=>setReview(review?'':'open')}/>:<p>本次运行尚未读到可展示的成果。</p>}
   {view.progress?.state!=='SUCCEEDED'&&view.artifacts.length>0&&<p>以上是本次已保存产物，不代表执行已经完成。</p>}
   {review&&<p>{view.outcome?'本次已有评价记录，执行完成与业务结论分别核对。':'暂未读到本次评价记录，不能据此认定业务已经解决。'}</p>}
  </>}
  <details className="fixed-cycle-resources"><summary>本次资源与依据</summary><Link to={'/knowledge?'+new URLSearchParams({kind:'knowledge',query:view.preparation.source_snapshot.resource_id,selected:view.preparation.source_snapshot.resource_id,resourceRevision:view.preparation.source_snapshot.revision_id,resourceDigest:view.preparation.source_snapshot.digest,fromExecution:view.digest,returnConversation:conversation})}>查看本次资料与固定版本</Link><dl>{view.preparation.participants.map(p=><div key={p.task_id}><dt>{view.preparation.semantics.tasks.find(t=>t.task_id===p.task_id)?.title??'本次任务'}</dt><dd>数字员工 {p.definition.resource_id} / {p.definition.revision_id}</dd><dd>工具操作 {p.skill.operation} · {p.skill.reference.revision_id}</dd><dd>运行配置 {p.profile.revision_id}</dd></div>)}</dl></details>
 </section>;
}
