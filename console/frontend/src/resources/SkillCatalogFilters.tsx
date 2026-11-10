import type {ReactNode} from 'react';
import './SkillCatalogFilters.css';
export function SkillCatalogFilters({query,onQuery,filter,onFilter,options,filterLabel,action}:{query:string;onQuery:(value:string)=>void;filter:string;onFilter:(value:string)=>void;options:{value:string;label:string}[];filterLabel:string;action?:ReactNode}){
 return <form className="skill-catalog-filters" onSubmit={e=>e.preventDefault()}><input aria-label="搜索资源" placeholder="搜索技能名称、方法或业务用途" value={query} onChange={e=>onQuery(e.target.value)}/><select aria-label={filterLabel} value={filter} onChange={e=>onFilter(e.target.value)}>{options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select>{action}</form>;
}
