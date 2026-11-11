import {safeBusinessProcessReturn} from '../businessProcesses/businessRelationNavigation';
import {Link,useLocation} from 'react-router-dom';
import {safeCapabilityReturn} from './capabilityNavigation';
export function CapabilityReturnLink(){
 const location=useLocation(),processHref=safeBusinessProcessReturn(new URLSearchParams(location.search).get('businessProcessReturn')),href=safeCapabilityReturn(new URLSearchParams(location.search).get('capabilityReturn'));
 if(processHref&&['/employees','/digital-employees','/knowledge'].includes(location.pathname))return <Link className="capability-origin-return" to={processHref}>← 返回原流程与活动</Link>;
 if(!href||!['/employees','/digital-employees','/skills','/mcp','/knowledge','/runtime-profiles'].includes(location.pathname))return null;
 return <Link className="capability-origin-return" to={href}>← 返回业务能力详情</Link>;
}
