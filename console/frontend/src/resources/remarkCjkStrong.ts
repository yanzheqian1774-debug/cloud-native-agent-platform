import type {Root} from 'mdast';

type Node={type:string;value?:string;children?:Node[];position?:{start:{offset?:number};end:{offset?:number}}};
/** Tolerate Chinese label punctuation without changing saved Markdown or code. */
export function remarkCjkStrong(){
 return (tree:Root,file:{value:unknown})=>{
  const source=String(file.value);
  function visit(parent:Node){
   if(!parent.children)return;
   parent.children=parent.children.flatMap(node=>{
    if(node.type!=='text'||!node.value){visit(node);return [node]}
    const start=node.position?.start.offset,end=node.position?.end.offset;
    // Escaped markers and entity-decoded text remain literal; never infer syntax.
    if(start===undefined||end===undefined||source.slice(start,end)!==node.value)return [node];
    const pieces:Node[]=[];let cursor=0;
    const pattern=/\*\*([^*\n]*[：，。！？；、）】》」』])\*\*(?=[\p{L}\p{N}])/gu;
    for(const match of node.value.matchAll(pattern)){
     const index=match.index;
     if(index>cursor)pieces.push({type:'text',value:node.value.slice(cursor,index)});
     pieces.push({type:'strong',children:[{type:'text',value:match[1]}]});cursor=index+match[0].length;
    }
    if(!cursor)return [node];
    if(cursor<node.value.length)pieces.push({type:'text',value:node.value.slice(cursor)});
    return pieces;
   });
  }
  visit(tree);
 };
}
