import {test,expect} from '@playwright/test';
import {modelResult} from '../../src/api/modelStream';
const response=(text:string)=>new Response(text,{headers:{'content-type':'text/event-stream'}});
for(const [code,label] of [
 ['STREAM_PROGRESS_VALIDATION_UNAVAILABLE','进度读取未通过校验'],
 ['STREAM_PROGRESS_READ_UNAVAILABLE','进度读取服务暂不可用'],
 ['STREAM_SERVICE_UNAVAILABLE','进度服务暂不可用'],
 ['unknown-private-token','进度服务暂不可用'],
 ['STREAM_INTERRUPTED_READ_ORIGINAL_REQUEST','进度服务暂不可用'],
])test(`safe server category ${code}`,async()=>{
 const error=await modelResult(response(`event: error\ndata: ${JSON.stringify({reasonCode:code,private:'must-not-show'})}\n\n`)).catch(e=>e);
 expect(error.message).toBe(`${label}，结果尚待核实；不会自动重发原请求。`);
 expect(error.message).not.toContain('must-not-show');
 expect(error.message).not.toContain(code);
});
test('EOF and reader transport failure are distinct from server validation',async()=>{
 for(const value of [response(''),new Response(new ReadableStream({start(controller){controller.error(Error('private-network-token'));}}),{headers:{'content-type':'text/event-stream'}})]){
  await expect(modelResult(value)).rejects.toThrow('流式连接已断开，结果尚待核实；不会自动重发原请求。');
 }
});
test('progress and successful result retain one consumer and original outcome',async()=>{
 const progress:unknown[]=[];
 const value=await modelResult(response('event: progress\ndata: {"kind":"accepted"}\n\nevent: result\ndata: {"status":201,"body":{"result":{"state":"OUTCOME_UNKNOWN"}}}\n\n'),p=>progress.push(p));
 expect(progress).toEqual([{kind:'accepted'}]);
 expect(value).toEqual({state:'OUTCOME_UNKNOWN'});
});
