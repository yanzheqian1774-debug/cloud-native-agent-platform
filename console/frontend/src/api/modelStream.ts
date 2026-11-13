export type ModelProgress={kind:string;stage?:string;preview?:string;characters?:number;eventCount?:number;completed?:boolean};
export async function readEvents(response:Response,onEvent:(event:string,value:unknown)=>void){
 const reader=response.body?.getReader();if(!reader)throw Error('连接未提供流式内容，原请求不会自动重发。');
 const decoder=new TextDecoder();let buffer='';
 try{while(true){const {done,value}=await reader.read().catch(()=>{throw Error('流式连接已断开，结果尚待核实；不会自动重发原请求。');});buffer=(buffer+decoder.decode(value,{stream:!done})).replace(/\r\n/g,'\n');if(buffer.length>2_000_000)throw Error('流式内容超出范围。');let split;while((split=buffer.indexOf('\n\n'))>=0){const frame=buffer.slice(0,split);buffer=buffer.slice(split+2);let event='message';const data:string[]=[];for(const line of frame.split('\n')){if(line.startsWith('event:'))event=line.slice(6).trim();if(line.startsWith('data:'))data.push(line.slice(5).trimStart());}if(data.length)onEvent(event,JSON.parse(data.join('\n')));}if(done)break;}}finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
}
export async function modelResult<T>(response:Response,onProgress?:(p:ModelProgress)=>void,failure:(status:number,reason?:string)=>Error=(_status,reason)=>Error(reason??'请求未完成')):Promise<T>{
 if(!response.headers.get('content-type')?.includes('text/event-stream')){const value=await response.json();if(!response.ok)throw failure(response.status,value.reasonCode);return value.result as T;}
 let result:T|undefined,finished=false;
 await readEvents(response,(event,value)=>{const item=value as {status:number;body:{result:T;reasonCode?:string};reasonCode?:string};if(event==='progress')onProgress?.(value as ModelProgress);else if(event==='error'){const messages:Record<string,string>={STREAM_PROGRESS_VALIDATION_UNAVAILABLE:'进度读取未通过校验',STREAM_PROGRESS_READ_UNAVAILABLE:'进度读取服务暂不可用'};throw Error(`${messages[item.reasonCode??'']??'进度服务暂不可用'}，结果尚待核实；不会自动重发原请求。`);}else if(event==='result'){if(finished)throw Error('流式结果重复，需核对原记录。');finished=true;if(item.status>=400)throw failure(item.status,item.body.reasonCode);result=item.body.result;}});
 if(!finished)throw Error('流式连接已断开，结果尚待核实；不会自动重发原请求。');return result as T;
}
