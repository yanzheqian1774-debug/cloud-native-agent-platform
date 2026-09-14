import {useEffect,useRef,useState,type FormEvent,type KeyboardEvent,type ReactNode} from "react";
import type {DraftTurn,ProblemDraft} from "./problemConversationModel";

export function ConversationFrame({children,composer,newMessageKey}:{children:ReactNode;composer:ReactNode;newMessageKey:string}){
  const stream=useRef<HTMLDivElement>(null),nearBottom=useRef(true),[showNew,setShowNew]=useState(false);
  function scrollToLatest(){stream.current?.scrollTo({top:stream.current.scrollHeight,behavior:"smooth"});setShowNew(false)}
  useEffect(()=>{
    if(nearBottom.current){stream.current?.scrollTo({top:stream.current.scrollHeight});setShowNew(false)}
    else setShowNew(true);
  },[newMessageKey]);
  return <section className="px-conversation" aria-label="业务问题对话">
    <div className="px-message-stream" ref={stream} onScroll={event=>{const node=event.currentTarget;nearBottom.current=node.scrollHeight-node.scrollTop-node.clientHeight<72;if(nearBottom.current)setShowNew(false)}}>
      {children}
    </div>
    {showNew&&<button className="px-new-message" type="button" onClick={scrollToLatest}>有新消息，回到最新</button>}
    {composer}
  </section>;
}

export function ConversationComposer({value,onChange,onSend,onCancelEdit,disabled,mode="NEW",lockedReason="当前操作请使用消息中的卡片。",lockedLabel="当前步骤"}:{value:string;onChange:(value:string)=>void;onSend:()=>void;onCancelEdit:()=>void;disabled:boolean;mode?:"NEW"|"DRAFT_REPLACE"|"FORMAL_REPLACE"|"LOCKED";lockedReason?:string;lockedLabel?:string}){
  const input=useRef<HTMLTextAreaElement>(null);
  useEffect(()=>{const node=input.current;if(!node)return;node.style.height="auto";node.style.height=`${Math.min(node.scrollHeight,144)}px`},[value,mode]);
  useEffect(()=>{if(mode==="DRAFT_REPLACE"||mode==="FORMAL_REPLACE")input.current?.focus()},[mode]);
  function submit(event:FormEvent){event.preventDefault();if(value.trim()&&!disabled&&mode!=="LOCKED")onSend()}
  function keyDown(event:KeyboardEvent<HTMLTextAreaElement>){
    if(event.key!=="Enter"||event.shiftKey||event.nativeEvent.isComposing||event.keyCode===229)return;
    event.preventDefault();if(value.trim()&&!disabled&&mode!=="LOCKED")onSend();
  }
  const replacing=mode==="DRAFT_REPLACE"||mode==="FORMAL_REPLACE",formal=mode==="FORMAL_REPLACE",locked=mode==="LOCKED";
  if(locked)return <section className="px-composer px-composer-locked" role="status" aria-live="polite"><span>{lockedLabel}</span><p>{lockedReason}</p></section>;
  return <form className="px-composer" aria-label={replacing?"完整修改问题草稿":"描述业务问题"} onSubmit={submit}>
    <label htmlFor="problem-composer">{formal?"完整替换正式问题描述":replacing?"完整替换草稿描述":"你希望解决什么问题？"}</label>
    <textarea ref={input} id="problem-composer" value={value} disabled={disabled} maxLength={2_000} rows={1} onChange={event=>onChange(event.target.value)} onKeyDown={keyDown} placeholder={replacing?"请输入完整描述；采用后会替换当前描述。":"描述现状、影响和希望解决的问题。"}/>
    <div className="px-composer-footer"><span>{replacing?"无模型模式：本次输入会完整替换描述。":"Enter 发送，Shift+Enter 换行；发送后仍需确认。"}</span><div>{replacing&&<button type="button" onClick={onCancelEdit}>取消修改</button>}<button className="px-primary-button" type="submit" disabled={disabled||!value.trim()}>{formal?"采用正式描述":replacing?"采用草稿描述":"发送"}</button></div></div>
  </form>;
}

export function UserMessage({children}:{children:ReactNode}){return <article className="px-message px-user-message"><div className="px-avatar" aria-hidden="true">H</div><div><span className="px-message-author">你</span><p>{children}</p></div></article>}

export function SystemMessage({children,label="系统"}:{children:ReactNode;label?:string}){return <article className="px-message px-system-message"><div className="px-avatar" aria-hidden="true">A</div><div className="px-message-body"><span className="px-message-author">{label}</span>{children}</div></article>}

export function DraftCard({turn,busy,composerEditing,onConfirm,onRecover,onEditFields,onFinishFields,onEditWithComposer,onCancel,onChange}:{turn:DraftTurn;busy:boolean;composerEditing:boolean;onConfirm:()=>void;onRecover:()=>void;onEditFields:()=>void;onFinishFields:()=>void;onEditWithComposer:()=>void;onCancel:()=>void;onChange:(draft:ProblemDraft)=>void}){
  const active=turn.phase==="DRAFT"||turn.phase==="EDITING",editable=turn.phase==="EDITING"&&!composerEditing;
  const status={DRAFT:"待确认",EDITING:"正在修改",SUBMITTING:"正在创建",UNKNOWN:"结果不确定",CANCELLED:"已取消",CREATED:"已创建"}[turn.phase];
  return <section id="draft-problem-message" tabIndex={-1} className={`px-inline-card px-draft-card is-${turn.phase.toLowerCase()}`} aria-label="问题草稿卡片">
    <header><div><span className="px-eyebrow">{turn.phase==="CREATED"?"已确认问题":"问题草稿"}</span><h2>{turn.phase==="CREATED"?turn.draft.title:"确认后才会正式创建"}</h2></div><span className={`px-status ${turn.phase==="CREATED"?"success":turn.phase==="UNKNOWN"?"danger":"warning"}`}>{status}</span></header>
    {turn.phase==="CREATED"?<details><summary>展开已确认内容</summary><p>{turn.draft.description}</p><small>草稿版本 {turn.version} 已提交；旧确认和更新操作已经失效。</small></details>:<>
      <p className="px-truth-note">无模型模式：描述保留原文；名称只是从首个非空句截取的建议，可修改。</p>
      {editable?<><label className="px-field" htmlFor={`draft-title-${turn.id}`}><span>建议名称</span><input id={`draft-title-${turn.id}`} maxLength={200} value={turn.draft.title} disabled={busy} onChange={event=>onChange({...turn.draft,title:event.target.value})}/></label><label className="px-field" htmlFor={`draft-description-${turn.id}`}><span>完整描述</span><textarea id={`draft-description-${turn.id}`} maxLength={2_000} value={turn.draft.description} disabled={busy} onChange={event=>onChange({...turn.draft,description:event.target.value})}/></label></>:<details open><summary>查看当前草稿</summary><h3>{turn.draft.title}</h3><p>{turn.draft.description}</p></details>}
      <small>草稿版本 {turn.version}。未提交草稿只保存在当前页面，刷新或离开可能丢失。</small>
      {composerEditing&&<p className="px-mode-note">正在底部输入框完整替换描述；采用或取消前，卡片确认操作不可用。</p>}
    </>}
    {active&&!composerEditing&&<div className="px-card-actions">
      <button type="button" disabled={busy} onClick={onCancel}>取消草稿</button>
      {editable?<><button type="button" disabled={busy} onClick={onEditWithComposer}>使用输入框完整修改</button><button type="button" className="px-primary-button" disabled={busy||!turn.draft.title.trim()||!turn.draft.description.trim()} onClick={onFinishFields}>采用字段修改</button></>:<><button type="button" disabled={busy} onClick={onEditFields}>修改</button><button type="button" className="px-primary-button" disabled={busy||!turn.draft.title.trim()||!turn.draft.description.trim()} onClick={onConfirm}>确认创建</button></>}
    </div>}
    {turn.phase==="CANCELLED"&&<p>已取消本地草稿，没有提交 Problem，也没有撤销任何服务器事实。</p>}
    {turn.phase==="UNKNOWN"&&<><p>在确认原命令结果前不能修改内容、换新标识或自动重建。</p><button type="button" className="px-primary-button" disabled={busy} onClick={onRecover}>{busy?"正在恢复原结果…":"恢复原创建结果"}</button></>}
  </section>;
}
