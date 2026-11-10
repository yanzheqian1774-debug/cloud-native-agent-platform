type DocumentLines={lines:{line:number;text:string}[];title:string};
const object=(value:unknown):value is Record<string,unknown>=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value);
export function documentLines(value:unknown):DocumentLines|null{
 if(!object(value))return null;
 const result=object(value.output)?value.output:value;
 if(!Array.isArray(result.lines)||!result.lines.length||!result.lines.every(l=>object(l)&&Number.isInteger(l.line)&&Number(l.line)>0&&typeof l.text==='string'))return null;
 const lines=result.lines as DocumentLines['lines'];if(new Set(lines.map(l=>l.line)).size!==lines.length)return null;
 const heading=lines.find(l=>l.line===1)?.text.match(/^#\s+(.+?)\s*$/)?.[1];
 return {lines,title:heading||(typeof result.documentId==='string'?result.documentId:'')};
}
