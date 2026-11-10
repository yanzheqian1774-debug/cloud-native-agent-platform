import type {ReactNode,Ref} from 'react';
import './SkillCatalogHeader.css';

/** Layout slots retain the management owner's commands and authorization checks. */
export function SkillCatalogHeader({back,secondary,primary,primaryRef,secondaryRef}:{back?:ReactNode;secondary?:ReactNode;primary?:ReactNode;primaryRef?:Ref<HTMLDivElement>;secondaryRef?:Ref<HTMLDivElement>}){
 return <div className="skill-catalog-heading">
  {back&&<div className="skill-heading-back">{back}</div>}
  <div className="skill-heading-secondary" ref={secondaryRef}>{secondary}</div>
  <header className="skill-heading-title"><div><h1>技能</h1><p>复用经过验证的方法与规则，让数字人按一致口径完成工作。</p></div><div className="skill-heading-primary" ref={primaryRef}>{primary}</div></header>
 </div>;
}
