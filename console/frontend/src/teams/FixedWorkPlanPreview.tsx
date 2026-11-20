import {useState} from 'react';
import type {FixedItem,FixedTrigger} from '../api/fixedWorkDrafts';
const when=(trigger:FixedTrigger)=>trigger.kind==='EVENT'?`当发生：${trigger.eventDescription??'事件条件未填写'}`:`${trigger.cadence==='WEEKDAY'?'每个工作日':'每天'} ${trigger.localTime??'时间未填写'}（${trigger.timezone??'时区未填写'}）`;
export function FixedWorkPlanPreview({title,instruction,trigger,prior,busy,onConfirm}:{title:string;instruction:string;trigger:FixedTrigger;prior:FixedItem|null;busy:boolean;onConfirm:()=>void}){
 const [preview,setPreview]=useState<string|null>(null),fingerprint=JSON.stringify([title,instruction,trigger,prior?.digest]),open=preview===fingerprint;
 const fields=[{label:'工作名称',before:prior?.draft.title,after:title},{label:'工作说明',before:prior?.draft.instruction,after:instruction},{label:'安排',before:prior?when(prior.draft.trigger):undefined,after:when(trigger)}];
 return <div>{!open?<button className="px-primary-button" disabled={busy} onClick={()=>setPreview(fingerprint)}>预览本次安排</button>:<section className="f3-team-card" aria-label="本次安排预览"><h3>{prior?'核对本次修改':'核对本次安排'}</h3><p>以下按你填写的说明与安排展示；尚未解释为可执行计划，也不会因保存开始运行。</p>{fields.filter(field=>!prior||field.before!==field.after).map(field=><div key={field.label}><h4>{field.label}</h4>{prior&&<p>原安排：{field.before||'未填写'}</p>}<p>{prior?'修改为：':''}{field.after||'未填写'}</p></div>)}{prior&&fields.every(field=>field.before===field.after)?<p>内容没有变化，无需另存。</p>:<button className="px-primary-button" disabled={busy} onClick={onConfirm}>确认保存配置</button>}<button disabled={busy} onClick={()=>setPreview(null)}>返回修改</button></section>}</div>;
}
