export type MessagePosition={cursor:string;messageId:string;offset:number};
const prefix='conversation-message-position.v1:';
const key=(scope:string,conversation:string)=>prefix+JSON.stringify([scope,conversation]);
export function readMessagePosition(scope:string,conversation:string):MessagePosition|null{
 try{const value=JSON.parse(sessionStorage.getItem(key(scope,conversation))??'null');return value&&typeof value.cursor==='string'&&value.cursor.length>0&&value.cursor.length<=8192&&typeof value.messageId==='string'&&value.messageId.length>0&&value.messageId.length<=512&&Number.isFinite(value.offset)&&Math.abs(value.offset)<100000?{cursor:value.cursor,messageId:value.messageId,offset:value.offset}:null}catch{return null}
}
export function saveMessagePosition(scope:string,conversation:string,value:MessagePosition){
 try{sessionStorage.setItem(key(scope,conversation),JSON.stringify({cursor:value.cursor,messageId:value.messageId,offset:value.offset}))}catch{/* A position is optional and never grants access. */}
}
export function clearMessagePosition(scope:string,conversation:string){try{sessionStorage.removeItem(key(scope,conversation))}catch{/* No authoritative record is changed. */}}
