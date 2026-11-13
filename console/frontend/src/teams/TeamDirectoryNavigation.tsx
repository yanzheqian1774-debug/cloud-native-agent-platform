import {Link,useSearchParams} from 'react-router-dom';
import './TeamsPage.css';
export function TeamDirectoryNavigation({active}:{active:'teams'|'members'|'work'}){
 const [params]=useSearchParams(),q=params.get('q')??'';
 const href=(view:string)=>{const next=new URLSearchParams();if(q)next.set('q',q);if(view==='work')next.set('view','work');return (view==='members'?'/employees':'/teams')+(next.size?'?'+next:'')};
 return <nav className="f3-team-directory-tabs" aria-label="数字人团队导航">{([['teams','团队'],['members','全部成员'],['work','本次工作团队']] as const).map(([view,label])=><Link key={view} aria-current={view===active?'page':undefined} to={href(view)}>{label}</Link>)}</nav>;
}
