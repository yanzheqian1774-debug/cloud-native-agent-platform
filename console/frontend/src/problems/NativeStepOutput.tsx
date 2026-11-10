import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {RememberedDetails} from './RememberedDetails';
import {documentLines} from './nativeDocumentLines';
import './NativeDocumentReading.css';
export function NativeStepOutput({value,viewKey,stepId,documentExpected=false}:{value:unknown;viewKey:string;stepId:string;documentExpected?:boolean}){
 const doc=documentLines(value),complete=doc?.lines.every((l,i)=>l.line===i+1);
 const original=doc&&<section className="native-document-lines" aria-label="本步返回原文">{!complete&&doc.title&&<h4>{doc.title}</h4>}<ol>{doc.lines.map(l=><li key={l.line}><span className="native-line-number">第 {l.line} 行</span><span className="native-line-text">{l.text}</span></li>)}</ol></section>;
 return <>{doc?<>{complete?<><section className="native-document-reading" aria-label="文档阅读"><Markdown remarkPlugins={[remarkGfm]} urlTransform={url=>/^(https?:\/\/|mailto:)/i.test(url)?url:''} components={{a:({href,children})=>href?<a href={href} target="_blank" rel="noopener noreferrer">{children}</a>:<span>{children}</span>,img:({alt})=><span className="native-image-reference">图片：{alt||'原文图片引用'}</span>,table:({children})=><div className="native-markdown-table"><table>{children}</table></div>}}>{doc.lines.map(l=>l.text).join('\n')}</Markdown></section><RememberedDetails viewKey={viewKey} name={'step-original:'+stepId} summary="核对原文与行号">{original}</RememberedDetails></>:<><p>本步返回的是部分行记录，按原始行号展示。</p>{original}</>}</>:documentExpected?<p>本步返回未提供可直接展示的完整原文行记录，请查看实际返回记录。</p>:null}<RememberedDetails viewKey={viewKey} name={'step-data:'+stepId} summary={doc?'查看原始技术记录':'查看本步实际返回'}><pre>{JSON.stringify(value,null,2)}</pre></RememberedDetails></>;
}
