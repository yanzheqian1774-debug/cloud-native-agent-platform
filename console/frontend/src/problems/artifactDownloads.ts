// Local exports derive only from content already authorized and read by the page.
export function downloadArtifact(name:string,content:string,type:string){
 const url=URL.createObjectURL(new Blob([content],{type}));const link=document.createElement('a');link.href=url;link.download=name;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function csvCell(value:unknown){const text=String(value);return `"${(/^[=+@\t\r-]/.test(text)?"'":"")+text.replaceAll('"','""')}"`}
