import {FrozenNavigationIconContext} from './navigationIconTheme';
import type {ReactNode} from 'react';

export function WorkspaceFrame({journey=false,brand,home,workspace,navigation,identity,menu,breadcrumb,actions,children}:{journey?:boolean;brand:ReactNode;home?:ReactNode;workspace:ReactNode;navigation:ReactNode;identity:ReactNode;menu:ReactNode;breadcrumb:ReactNode;actions:ReactNode;children:ReactNode}){
 return <div className={`px-shell skill-workspace-frame f3-workspace-frame${journey?" journey-shell":""}`}><aside className="px-sidebar skill-frame-sidebar"><div className="skill-frame-brand"><FrozenNavigationIconContext value={true}>{brand}{home&&<span className="skill-frame-home">{home}</span>}</FrozenNavigationIconContext></div><div className="skill-frame-workspace">{workspace}</div><div className="skill-frame-navigation"><FrozenNavigationIconContext value={true}>{navigation}</FrozenNavigationIconContext></div></aside><header className="px-topbar skill-frame-header"><div className="skill-frame-menu"><FrozenNavigationIconContext value={true}>{menu}</FrozenNavigationIconContext></div><div className="skill-frame-breadcrumb">{breadcrumb}</div><div className="skill-frame-actions">{actions}<div className="skill-frame-identity">{identity}</div></div></header><div className="px-content skill-frame-content">{children}</div></div>;
}

// Isolated skill previews reuse the production frame.
export const SkillWorkspaceFrame=WorkspaceFrame;
