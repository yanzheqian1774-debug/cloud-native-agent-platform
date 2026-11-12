import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './KnowledgeDocumentContent.css';
import {StructuredKnowledgePreview} from './StructuredKnowledgePreview';

type Document = {id:string;title:string;text:string;role?:string;scope?:string};
function documents(raw:string):Document[]|null{
 try{
  const value:unknown=JSON.parse(raw);
  if(!value||typeof value!=='object')return null;
  const record=value as Record<string,unknown>;
  if(record.schemaVersion!=='document-review-source.v1'||!Array.isArray(record.documents)||!record.documents.length)return null;
  const rows=record.documents;
  if(!rows.every(d=>d&&typeof d==='object'&&typeof d.id==='string'&&typeof d.title==='string'&&typeof d.text==='string'&&(d.role===undefined||typeof d.role==='string')&&(d.scope===undefined||typeof d.scope==='string')))return null;
  return rows as Document[];
 }catch{return null}
}
export function MarkdownReading({text}:{text:string}){
 return <div className="knowledge-document-reading"><Markdown remarkPlugins={[remarkGfm]} urlTransform={url=>/^(https?:\/\/|mailto:)/i.test(url)?url:''} components={{a:({href,children})=>href?<a href={href} target="_blank" rel="noopener noreferrer">{children}</a>:<span>{children}</span>,img:({alt})=><span>图片引用：{alt||'未提供说明'}</span>,table:({children})=><div className="knowledge-document-table"><table>{children}</table></div>}}>{text}</Markdown></div>;
}
export function KnowledgeDocumentContent({text,showOriginal=true}:{text:string;showOriginal?:boolean}){
 const rows=documents(text);let structured:unknown;try{structured=JSON.parse(text)}catch{structured=null}
 return <div className="knowledge-document-content">{rows?rows.map((d,i)=><article key={d.id+':'+i} aria-label={d.title}><h3>{d.title}</h3>{(d.role||d.scope)&&<p className="knowledge-document-context">{d.role==='SUBMISSION'?'待检查材料':d.role==='POLICY'?'参考规范':d.role}{d.scope?' · '+d.scope:''}</p>}<MarkdownReading text={d.text}/></article>):structured!==null&&typeof structured==='object'?<StructuredKnowledgePreview value={structured}/>:<MarkdownReading text={text}/>} {showOriginal&&<details><summary>核对保存的原始正文</summary><pre>{text}</pre></details>}</div>;
}
