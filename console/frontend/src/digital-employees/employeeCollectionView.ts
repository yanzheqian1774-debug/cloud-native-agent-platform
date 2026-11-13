/** View coordinates only; all content and authority are re-read after navigation. */
export type EmployeeCollectionView={query:string;status:string;index:number;cursors:(string|null)[];scroll:number;selected:{id:string;revision:string}|null};
const key=(scope:string)=>'employee-collection-view:'+scope;
export function readEmployeeCollectionView(scope:string):EmployeeCollectionView|null{
 try{const v=JSON.parse(sessionStorage.getItem(key(scope))??'null');if(!v||typeof v.query!=='string'||v.query.length>200||!['ALL','PUBLISHED','NOT_PUBLISHED'].includes(v.status)||!Number.isInteger(v.index)||v.index<0||v.index>99||!Array.isArray(v.cursors)||v.cursors.length>100||v.cursors.length<=v.index||v.cursors.some((c:unknown)=>c!==null&&(typeof c!=='string'||c.length>4096))||!Number.isFinite(v.scroll)||v.scroll<0||v.scroll>1e7||v.selected&&(typeof v.selected.id!=='string'||v.selected.id.length>512||typeof v.selected.revision!=='string'||v.selected.revision.length>512))return null;return v}catch{return null}
}
export function saveEmployeeCollectionView(scope:string,value:EmployeeCollectionView){try{sessionStorage.setItem(key(scope),JSON.stringify(value))}catch{/* Storage failure does not change reads or execution authority. */}}
