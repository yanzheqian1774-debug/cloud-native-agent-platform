import type {WorkbenchSession} from '../api/businessWorkspace';

// This browser locator remembers an explicit action, never grants authority.
// Each owner still checks the current subject, scope, exact version and policy.
export function journeyScope(session:WorkbenchSession){return JSON.stringify(session.principal)}
function key(scope:string,id:string,digest:string){return 'continuous-plan:'+JSON.stringify([scope,id,digest])}
export function rememberContinuous(scope:string,id:string,digest:string){sessionStorage.setItem(key(scope,id,digest),'explicit')}
export function hasContinuous(scope:string,id:string,digest:string){return sessionStorage.getItem(key(scope,id,digest))==='explicit'}
export function rememberContinuousRequest(scope:string,problem:string,request:string){sessionStorage.setItem('continuous-request:'+JSON.stringify([scope,problem,request]),'explicit')}
export function hasContinuousRequest(scope:string,problem:string,request?:string|null){return Boolean(request&&sessionStorage.getItem('continuous-request:'+JSON.stringify([scope,problem,request]))==='explicit')}
