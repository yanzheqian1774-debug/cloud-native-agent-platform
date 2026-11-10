import {useState} from 'react';
import {Link} from 'react-router-dom';
import {BusinessNavigation} from './BusinessNavigation';

export function AllFunctionsMenu({sessionIdentity}:{sessionIdentity:string|null}){
 const [open,setOpen]=useState(false);
 return <details onToggle={event=>{
  if(event.target===event.currentTarget)setOpen(event.currentTarget.open);
 }}>
  <summary>☰ 菜单</summary>
  {open&&<nav aria-label="全部功能">
   <BusinessNavigation mobile sessionIdentity={sessionIdentity}/>
   <Link to="/help">帮助中心</Link>
  </nav>}
 </details>;
}
