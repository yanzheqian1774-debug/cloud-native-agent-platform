export type BusinessEditorPosition={fields:Record<string,string>;scroll:{selector:string;top:number;left:number}[];windowTop:number;windowLeft:number};
const selectors=['.skill-frame-content','.bp-editor-local-fields','.bp-editor .bp-map-scroll'];
export function captureBusinessEditorPosition(form:HTMLFormElement):BusinessEditorPosition{
 return {fields:Object.fromEntries([...new FormData(form)].filter((entry):entry is [string,string]=>typeof entry[1]==='string')),scroll:selectors.flatMap(selector=>{const node=document.querySelector<HTMLElement>(selector);return node?[{selector,top:node.scrollTop,left:node.scrollLeft}]:[]}),windowTop:window.scrollY,windowLeft:window.scrollX};
}
export function restoreBusinessEditorPosition(form:HTMLFormElement,position:BusinessEditorPosition){
 if(!position||!position.fields||typeof position.fields!=='object'||!Array.isArray(position.scroll))return;
 for(const element of Array.from(form.elements))if((element instanceof HTMLInputElement||element instanceof HTMLTextAreaElement)&&element.name&&typeof position.fields[element.name]==='string')element.value=position.fields[element.name];
 const coordinate=(value:number)=>Number.isFinite(value)&&value>=0&&value<=10000000?value:0;
 for(const item of position.scroll)if(item&&selectors.includes(item.selector)){const node=document.querySelector<HTMLElement>(item.selector);if(node){node.scrollTop=coordinate(item.top);node.scrollLeft=coordinate(item.left)}}
 window.scrollTo(coordinate(position.windowLeft),coordinate(position.windowTop));
}
