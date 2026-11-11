import {formatTime} from '../journey/formatTime';

/** Identity comes from the recorded author, never the current viewer or a participant. */
export function ConversationMessageIdentity({author,assistant=false,timestamp,timeLabel}:{author?:string;assistant?:boolean;timestamp?:string;timeLabel?:string}){
 const recordedAuthor=author?.trim();
 const name=assistant?'工作助手':recordedAuthor==='human:development-admin'?'开发管理员':'用户';
 const valid=Boolean(timestamp&&Number.isFinite(Date.parse(timestamp)));
 return <header className="conversation-message-identity">
  <span className="conversation-message-avatar" aria-hidden="true">{assistant?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/></svg>:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="8" r="3.5"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/></svg>}</span>
  {!assistant&&recordedAuthor?<details className="conversation-message-author conversation-author-details"><summary>{name}</summary><span className="conversation-author-record">记录账号：{recordedAuthor}</span></details>:<span className="conversation-message-author">{name}</span>}
  {valid?<time dateTime={timestamp}>{timeLabel&&timeLabel+' · '}{formatTime(timestamp!)}</time>:<span className="conversation-message-time">{timestamp?'时间待核实':'时间未记录'}</span>}
 </header>;
}
