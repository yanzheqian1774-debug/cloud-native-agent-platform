import {Fragment,useEffect,useRef,useState,type FormEvent,type KeyboardEvent,type ReactNode} from "react";
import {formatTime} from "../journey/formatTime";
import {sourceLabels,understandingDisplay,isUnstructuredStatement} from "./problemUnderstandingModel";
import type {DraftTurn,ProblemDraft} from "./problemConversationModel";

export function ConversationFrame({children,composer,newMessageKey,startAtTop=false}:{children:ReactNode;composer:ReactNode;newMessageKey:string;startAtTop?:boolean}){
  const initial=useRef(true);
  const stream=useRef<HTMLDivElement>(null),nearBottom=useRef(true),[showNew,setShowNew]=useState(false);
  function scrollToLatest(){stream.current?.scrollTo({top:stream.current.scrollHeight,behavior:"smooth"});setShowNew(false)}
  useEffect(()=>{
    if(initial.current){initial.current=false;if(startAtTop){stream.current?.scrollTo({top:0});return;}}
    if(nearBottom.current){stream.current?.scrollTo({top:stream.current.scrollHeight});setShowNew(false)}
    else setShowNew(true);
  },[newMessageKey,startAtTop]);
  return <section className="px-conversation" aria-label="业务问题对话">
    <div className="px-message-stream" ref={stream} onScroll={event=>{const node=event.currentTarget;nearBottom.current=node.scrollHeight-node.scrollTop-node.clientHeight<72;if(nearBottom.current)setShowNew(false)}}>
      {children}
    </div>
    {showNew&&<button className="px-new-message" type="button" onClick={scrollToLatest}>有新消息，回到最新</button>}
    {composer}
  </section>;
}

export function ConversationComposer({value,onChange,onSend,onCancelEdit,disabled,sendBlocked=false,assisted=false,mode="NEW",contextLabel,maxLength=2_000}:{value:string;onChange:(value:string)=>void;onSend:()=>void;onCancelEdit:()=>void;disabled:boolean;sendBlocked?:boolean;assisted?:boolean;mode?:"NEW"|"SUPPLEMENT"|"DRAFT_REPLACE"|"FORMAL_REPLACE"|"CRITERION"|"CRITERION_REPLACE"|"PLANNING"|"FORMAL_SUPPLEMENT";contextLabel?:string;maxLength?:number}){
  const input=useRef<HTMLTextAreaElement>(null);
  useEffect(()=>{const node=input.current;if(!node)return;node.style.height="auto";node.style.height=`${Math.min(node.scrollHeight,144)}px`},[value,mode]);
  useEffect(()=>{if(mode==="DRAFT_REPLACE"||mode==="FORMAL_REPLACE"||mode==="CRITERION"||mode==="CRITERION_REPLACE")input.current?.focus()},[mode]);
  function submit(event:FormEvent){event.preventDefault();if(value.trim()&&!disabled&&!sendBlocked)onSend()}
  function keyDown(event:KeyboardEvent<HTMLTextAreaElement>){
    if(event.key!=="Enter"||event.shiftKey||event.nativeEvent.isComposing||event.keyCode===229)return;
    event.stopPropagation();if(event.repeat){event.preventDefault();return;}
    event.preventDefault();if(value.trim()&&!disabled&&!sendBlocked)onSend();
  }
  const formalSupplement=mode==="FORMAL_SUPPLEMENT",planning=mode==="PLANNING",criterion=mode==="CRITERION"||mode==="CRITERION_REPLACE",criterionReplace=mode==="CRITERION_REPLACE",replacing=mode==="DRAFT_REPLACE"||mode==="FORMAL_REPLACE"||criterionReplace,formal=mode==="FORMAL_REPLACE",supplement=mode==="SUPPLEMENT"||formalSupplement;
  return <form className={`px-composer${supplement?" is-supplement":""}${criterion?" is-criterion":""}`} aria-label={planning?"规划对话":criterion?"定义成功标准":replacing?"完整修改问题草稿":supplement?"准备待处理补充":"描述业务问题"} onSubmit={submit}>
    <label htmlFor="problem-composer">{planning?"补充信息或提出方案修改":criterionReplace?"修改成功标准原文":criterion?"怎样才算解决？":formal?"完整替换正式问题描述":replacing?"完整替换草稿描述":formalSupplement?"补充或纠正正式目标":supplement?"待处理补充（仅本页）":"你希望解决什么问题？"}</label>
    {criterion&&contextLabel&&<span className="px-composer-context">当前针对：{contextLabel} · 成功标准</span>}
    <textarea ref={input} id="problem-composer" value={value} disabled={disabled} maxLength={maxLength} rows={1} onChange={event=>onChange(event.target.value)} onKeyDown={keyDown} placeholder={planning?"说明希望调整的任务、约束或信息；目标和标准请返回问题页正式修订。":criterion?"用自己的话描述达到什么结果才算解决。":replacing?"请输入完整描述；采用后会替换当前描述。":supplement?"继续补充背景、约束或后续想法。":"描述现状、影响和希望解决的问题。"}/>
    <div className="px-composer-footer"><span>{planning?"生成持久化的后继建议，旧计划和批准保留；新建议需要重新确认。":criterion?"保留原文；发送后选择类型并确认，确认前不会保存。":replacing?"无模型模式：本次输入会完整替换描述。":formalSupplement?"发送后形成待保存修订；必须保存并重新核对标准，旧计划及批准保留。":supplement?(assisted?"补充或直接说明要修改哪一项；发送后更新理解，确认后才创建。":"仅保留在当前页面，尚未修改正式问题，管理员不会自动收到。"):"Enter 发送，Shift+Enter 换行；发送后仍需确认。"}</span><div>{(replacing||mode==="CRITERION")&&<button type="button" onClick={onCancelEdit}>取消修改</button>}<button className="px-primary-button" type="submit" disabled={disabled||sendBlocked||!value.trim()}>{planning?"提交规划补充":criterionReplace?"采用标准原文":criterion?"生成待确认卡片":formal?"采用正式描述":replacing?"采用草稿描述":formalSupplement?"准备正式修订":supplement?(assisted?"更新理解":"保留补充"):"发送"}</button></div></div>
  </form>;
}

export function UserMessage({children,occurredAt}:{children:ReactNode;occurredAt?:string}){return <article className="px-message px-user-message"><div className="px-avatar" aria-hidden="true">H</div><div><span className="px-message-author">你</span>{occurredAt&&<time dateTime={occurredAt}>{formatTime(occurredAt)}</time>}<p>{children}</p></div></article>}

export function SystemMessage({children,label="系统",occurredAt}:{children:ReactNode;label?:string;occurredAt?:string}){return <article className="px-message px-system-message"><div className="px-avatar" aria-hidden="true">系</div><div className="px-message-body"><span className="px-message-author">{label}</span>{occurredAt&&<time dateTime={occurredAt}>{formatTime(occurredAt)}</time>}{children}</div></article>}

export function DraftCard({turn,busy,confirmBlocked=false,composerEditing,onConfirm,onRecover,onEditFields,onFinishFields,onEditWithComposer,onCancel,onChange}:{turn:DraftTurn;busy:boolean;confirmBlocked?:boolean;composerEditing:boolean;onConfirm:()=>void;onRecover:()=>void;onEditFields:()=>void;onFinishFields:()=>void;onEditWithComposer:()=>void;onCancel:()=>void;onChange:(draft:ProblemDraft)=>void}){
  const active=turn.phase==="DRAFT"||turn.phase==="FAILED"||turn.phase==="EDITING",editable=turn.phase==="EDITING"&&!composerEditing;
  const status={DRAFT:"待确认",FAILED:"创建失败",EDITING:"正在修改",SUBMITTING:"正在创建",UNKNOWN:"结果不确定",CANCELLED:"已取消",CREATED:"已创建"}[turn.phase];
  const confirm=useRef<HTMLButtonElement>(null),previousPhase=useRef(turn.phase),held=useRef(true),composing=useRef(false);
  useEffect(()=>{
    const down=(event:globalThis.KeyboardEvent)=>{if(event.key==="Enter")held.current=true};
    const up=(event:globalThis.KeyboardEvent)=>{if(event.key==="Enter"||event.key==="Tab")held.current=false};
    const start=()=>{composing.current=true},end=()=>{composing.current=false},pointer=()=>{held.current=false};
    document.addEventListener("keydown",down,true);document.addEventListener("keyup",up,true);document.addEventListener("compositionstart",start,true);document.addEventListener("compositionend",end,true);document.addEventListener("pointerdown",pointer,true);
    return()=>{document.removeEventListener("keydown",down,true);document.removeEventListener("keyup",up,true);document.removeEventListener("compositionstart",start,true);document.removeEventListener("compositionend",end,true);document.removeEventListener("pointerdown",pointer,true)};
  },[]);
  useEffect(()=>{
    if(previousPhase.current==="EDITING"&&turn.phase==="DRAFT"&&!held.current&&!composing.current&&document.activeElement?.tagName==="BUTTON")confirm.current?.focus({preventScroll:true});
    previousPhase.current=turn.phase;
  },[turn.phase]);
  function confirmKey(event:KeyboardEvent<HTMLButtonElement>){
    if(event.key!=="Enter")return;
    event.preventDefault();event.stopPropagation();
    if(!event.repeat&&!event.nativeEvent.isComposing&&event.keyCode!==229&&!composing.current&&!confirmBlocked&&!busy){onConfirm()}
  }
  return <section id="draft-problem-message" tabIndex={-1} className={`px-inline-card px-draft-card is-${turn.phase.toLowerCase()}`} aria-label="问题草稿卡片">
    <header><div><span className="px-eyebrow">{turn.phase==="CREATED"?"已提交草稿（历史）":"问题草稿（尚未创建）"}</span><h2>{turn.phase==="CREATED"?turn.draft.title:"确认后才会正式创建"}</h2></div><span role="status" aria-live="polite" className={`px-status ${turn.phase==="CREATED"?"success":turn.phase==="UNKNOWN"?"danger":"warning"}`}>{turn.phase==="CREATED"?"已用于创建":status}</span></header>
    {turn.phase==="CREATED"?<details><summary>展开已确认内容</summary><p>{turn.draft.description}</p><small>草稿版本 {turn.version} 已提交；旧确认和更新操作已经失效。</small></details>:<>
      <p className="px-truth-note">{turn.source==="AI_PROVIDER"?"草稿来自已授权的真实 AI 服务；仍需人工编辑或确认。":turn.source==="AI_SYNTHETIC"?"草稿来自明确标识的模拟辅助生成；没有调用真实 AI 服务。":"手工草稿模式：描述保留原文，名称可修改。"}</p>
      {editable?<><label className="px-field" htmlFor={`draft-title-${turn.id}`}><span>建议名称（可选修改）</span><input id={`draft-title-${turn.id}`} maxLength={200} value={turn.draft.title} disabled={busy} onChange={event=>onChange({...turn.draft,title:event.target.value})}/></label><label className="px-field" htmlFor={`draft-description-${turn.id}`}><span>完整描述</span><textarea id={`draft-description-${turn.id}`} maxLength={2_000} value={turn.draft.description} disabled={busy} onChange={event=>onChange({...turn.draft,description:event.target.value})}/></label></>:<details open><summary>查看当前草稿</summary><h3>{turn.draft.title}</h3>{!turn.understanding?.some(item=>isUnstructuredStatement(item,turn.draft.description))&&<p>{turn.draft.description}</p>}</details>}
      {turn.understanding&&<dl className="px-understanding-facts" aria-label="当前问题理解">{turn.understanding.map((item,index)=><Fragment key={`${item.field}-${index}`}><dt>{understandingDisplay(item,turn.draft.description).label}</dt><dd><span>{understandingDisplay(item,turn.draft.description).value}</span>{!isUnstructuredStatement(item,turn.draft.description)&&item.source!=="UNKNOWN"&&item.value!==sourceLabels[item.source]&&<small className={`px-fact-source is-${item.source.toLowerCase()}`}>{sourceLabels[item.source]}</small>}</dd></Fragment>)}</dl>}
      <small>{turn.understanding?.some(item=>item.source==="UNKNOWN")&&<>“尚未单独整理”不代表你未提供。<br/></>}草稿版本 {turn.version}。未提交草稿只保存在当前页面，刷新或离开可能丢失。</small>
      {composerEditing&&<p className="px-mode-note">正在底部输入框完整替换描述；采用或取消前，卡片确认操作不可用。</p>}
    </>}
    {active&&!composerEditing&&<div className="px-card-actions">
      <button type="button" disabled={busy} onClick={onCancel}>取消草稿</button>
      {editable?<><button type="button" disabled={busy} onClick={onEditWithComposer}>使用输入框完整修改</button><button type="button" className="px-primary-button" disabled={busy||!turn.draft.title.trim()||!turn.draft.description.trim()} onClick={onFinishFields}>采用字段修改</button></>:<><button type="button" disabled={busy} onClick={onEditFields}>修改</button><button ref={confirm} type="button" className="px-primary-button" disabled={busy||confirmBlocked||!turn.draft.title.trim()||!turn.draft.description.trim()} onKeyDown={confirmKey} onClick={event=>{if(!composing.current&&(event.detail>0||!held.current))onConfirm()}}>确认创建</button></>}
    </div>}
    {confirmBlocked&&active&&<p role="status">当前输入或理解尚未采用，请先发送修改并核对新版本。</p>}
    {turn.phase==="CANCELLED"&&<p>已取消本地草稿，没有提交 Problem，也没有撤销任何服务器事实。</p>}
    {turn.phase==="UNKNOWN"&&<><p>在确认原命令结果前不能修改内容、换新标识或自动重建。</p><button type="button" className="px-primary-button" disabled={busy} onClick={onRecover}>{busy?"正在恢复原结果…":"恢复原创建结果"}</button></>}
  </section>;
}
