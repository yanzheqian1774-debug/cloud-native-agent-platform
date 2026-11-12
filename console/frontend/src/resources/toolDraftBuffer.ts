const prefix='f3-tool-buffer:v1:';
export function toolBufferKey(principal:string,page:string){return prefix+JSON.stringify([principal,page])}
export function readToolBuffer<T>(principal:string,page:string):T|null{
 try{const raw=sessionStorage.getItem(toolBufferKey(principal,page));return raw?JSON.parse(raw) as T:null}catch{return null}
}
// Persist pending command identity before sending. Storage failure must prevent
// writes, otherwise reload could lose the only reference to an unknown outcome.
export function writeToolBuffer(principal:string,page:string,value:unknown){
 sessionStorage.setItem(toolBufferKey(principal,page),JSON.stringify(value));
}
export function clearToolBuffers(){
 for(let i=sessionStorage.length-1;i>=0;i--){const key=sessionStorage.key(i);if(key?.startsWith(prefix))sessionStorage.removeItem(key)}
}
