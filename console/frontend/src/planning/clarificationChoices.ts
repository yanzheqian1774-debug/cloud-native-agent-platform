// Render only explicit choices supplied by the provider; never infer an answer.
export function clarificationChoices(question:string):{label:string;answer:string}[]{
 const lines=question.split('\n').map(line=>line.trim()).filter(Boolean);
 const start=lines.findIndex(line=>/^[ABC][.、）)]\s*\S/.test(line));
 if(start<1)return [];
 const choices=lines.slice(start);
 if(choices.length<2||choices.length>3||!choices.every((line,index)=>line.startsWith(`${'ABC'[index]}`)&&/^[ABC][.、）)]\s*\S/.test(line)))return [];
 const prompt=lines.slice(0,start).join(' ');
 return choices.map(line=>({label:line,answer:`${prompt}：${line}`}));
}
