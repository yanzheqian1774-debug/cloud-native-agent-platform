import {formatTime} from '../journey/formatTime';

/** Identity comes from the recorded author, never the current viewer or a participant. */
export function ConversationMessageIdentity({statusPanel=false,author,assistant=false,timestamp,timeLabel,recordLabel}:{statusPanel?:boolean;author?:string;assistant?:boolean;timestamp?:string;timeLabel?:string;recordLabel?:string}){
 const recordedAuthor=author?.trim();
 const name=assistant?'工作助手':!recordedAuthor?'操作人未记录':recordedAuthor==='human:development-admin'?'开发管理员':recordedAuthor.startsWith('human:')?'用户':'记录账号';
 const valid=Boolean(timestamp&&Number.isFinite(Date.parse(timestamp)));
 return <header className="conversation-message-identity">
  <span className="conversation-message-avatar" aria-hidden="true">{recordLabel?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M6 3h9l3 3v15H6Z M9 9h6 M9 13h6 M9 17h4"/></svg>:assistant?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/></svg>:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="8" r="3.5"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/></svg>}</span>
  {recordLabel&&<strong className="conversation-record-label">{recordLabel}</strong>}
  {!assistant&&recordedAuthor?<details className="conversation-message-author conversation-author-details"><summary>{recordLabel?'操作人：'+name:name}</summary><span className="conversation-author-record">记录账号：{recordedAuthor}</span></details>:<span className="conversation-message-author">{name}</span>}
  {valid?<time dateTime={timestamp}>{timeLabel&&timeLabel+' · '}{formatTime(timestamp!)}</time>:statusPanel?null:<span className="conversation-message-time">{timestamp?'时间待核实':'时间未记录'}</span>}
 </header>;
}
