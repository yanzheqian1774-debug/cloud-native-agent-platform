/** Shared frame owns page scrolling; standalone routes use the window. */
function scroller(){return document.querySelector<HTMLElement>('.f3-workspace-frame .skill-frame-content')}
export function pageScrollTop(){return scroller()?.scrollTop??window.scrollY}
export function scrollPageTo(top:number){const node=scroller();if(node)node.scrollTo(0,top);else window.scrollTo(0,top)}
