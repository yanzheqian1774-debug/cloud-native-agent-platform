import {RememberedDetails} from './RememberedDetails';
import {documentLines} from './nativeDocumentLines';
export function NativeStepOutput({value,viewKey,stepId,documentExpected=false}:{value:unknown;viewKey:string;stepId:string;documentExpected?:boolean}){
 const doc=documentLines(value);
 return <>{doc?<section className="native-document-lines" aria-label="本步返回原文">{doc.title&&<h4>{doc.title}</h4>}<ol>{doc.lines.map(l=><li key={l.line}><span className="native-line-number">第 {l.line} 行</span><span className="native-line-text">{l.text}</span></li>)}</ol></section>:documentExpected?<p>本步返回未提供可直接展示的完整原文行记录，请查看实际返回记录。</p>:null}<RememberedDetails viewKey={viewKey} name={'step-data:'+stepId} summary={doc?'查看原始技术记录':'查看本步实际返回'}><pre>{JSON.stringify(value,null,2)}</pre></RememberedDetails></>;
}
