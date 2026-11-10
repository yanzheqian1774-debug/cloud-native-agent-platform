import type {DirectoryPage} from '../api/resourceDirectory';
import type {ManagedResourceDirectory} from './ResourceManagement';

/** A navigation hint only. Commands still revalidate through their original owner. */
export function managedDirectoryMatches(page:DirectoryPage|null,managed:ManagedResourceDirectory|null,kind:string){
 const matches=new Set<string>();
 if(!page||!managed||page.subject!==managed.subject||page.scope.tenantId!==managed.scope.tenantId||page.scope.securityDomain!==managed.scope.securityDomain)return matches;
 for(const resource of managed.items){
  if(resource.kind!==kind)continue;
  const target=resource.currentDraftRevisionId??resource.publishedRevisionId;
  const revision=resource.revisions.find(x=>x.revisionId===target);
  if(!revision)continue;
  if(page.items.some(x=>x.kind===kind&&x.identity===resource.resourceId&&x.revisionId===target&&x.digest===revision.digest&&(resource.currentDraftRevisionId?x.isCurrentDraft:x.isCurrentPublished)))matches.add(resource.resourceId);
 }
 return matches;
}
