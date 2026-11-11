import {Link,useLocation} from 'react-router-dom';
import {safeCapabilityReturn} from './capabilityNavigation';
export function CapabilityReturnLink(){
 const location=useLocation(),href=safeCapabilityReturn(new URLSearchParams(location.search).get('capabilityReturn'));
 if(!href||!['/employees','/digital-employees','/skills','/mcp','/knowledge'].includes(location.pathname))return null;
 return <Link className="capability-origin-return" to={href}>← 返回业务能力详情</Link>;
}
