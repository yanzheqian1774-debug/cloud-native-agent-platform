import type {ReactNode} from 'react';
import {NavigationIcon} from '../components/NavigationIcon';
import './SkillCatalogCard.css';

export type SkillCardStatus={label:string;tone:'neutral'|'green'|'amber';basis:'publication'|'validation'|'trial'};
export type SkillCatalogCardProps={name:string;purpose:string|null;statuses:SkillCardStatus[];tags?:string[];attribution?:string;details:ReactNode;edit?:ReactNode;children?:ReactNode};

/** Presentation only. Callers supply independently evidenced status and exact-version actions. */
export function SkillCatalogCard({name,purpose,statuses,tags=[],attribution,details,edit,children}:SkillCatalogCardProps){
 return <article className="skill-catalog-card" aria-label={name}>
  <div className="skill-card-top"><span className="skill-card-icon"><NavigationIcon name="skill"/></span><div className="skill-card-statuses">{statuses.map(s=><span key={s.basis+':'+s.label} className={'skill-card-badge '+s.tone} data-status-basis={s.basis}>{s.label}</span>)}</div></div>
  <h2>{name}</h2><p className="skill-card-purpose">{purpose?.trim()||'当前列表未返回用途说明，可打开详情核对。'}</p>
  {tags.length>0&&<div className="skill-card-tags">{tags.map(t=><span className="skill-card-badge neutral" key={t}>{t}</span>)}</div>}
  <div className="skill-card-bottom"><small>{attribution??'维护者信息未提供'}</small>{details}{edit}</div>
  {children&&<div className="skill-card-additional">{children}</div>}
 </article>;
}
