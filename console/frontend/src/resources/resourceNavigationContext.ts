/** Conversation locators are view context; every destination reauthorizes reads. */
export function resourceNavigationUrl(path:string,search:string){
 if(path!=='/skills'&&path!=='/mcp')return path;
 const params=new URLSearchParams(search),conversation=params.get('conversation')||params.get('returnConversation');
 return path+(conversation?'?'+new URLSearchParams({returnConversation:conversation}):'');
}
