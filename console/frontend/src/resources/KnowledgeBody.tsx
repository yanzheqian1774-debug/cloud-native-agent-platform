import {KnowledgeDocumentContent} from './KnowledgeDocumentContent';
type SavedDocument={documentId:string;chunks:{content:string}[]};
export function KnowledgeBody({content,metadataTitles=false,showStatusNote=true}:{content:Record<string,unknown>;metadataTitles?:boolean;showStatusNote?:boolean}){
 const source=content.source as Record<string,unknown>|undefined,docs=content.documents as SavedDocument[]|undefined;
 return <section aria-label="知识正文与来源"><h2>知识正文与来源</h2><details className="knowledge-source"><summary>资料来源与保存依据</summary><p>出处：{String(source?.provenance??'未提供')}</p><p>来源：{String(source?.sourceId??'未提供')}</p></details>{docs?.map(d=><article key={d.documentId} className="knowledge-saved-document"><KnowledgeDocumentContent text={d.chunks.map(c=>c.content).join('\n\n')} showOriginal={false} metadataTitles={metadataTitles}/><details><summary>核对保存的原始正文</summary><p>以下保留保存时的分段内容；阅读视图按保存顺序连接展示。</p>{d.chunks.map((c,i)=><pre key={i}>{c.content}</pre>)}</details></article>)}{showStatusNote&&<p>这里核对保存的正文版本；发布不代表索引已建立、已检索或已被业务采用。</p>}</section>;
}
