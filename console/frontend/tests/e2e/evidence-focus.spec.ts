import {expect,test} from "@playwright/test";
import type {TraceabilityDTO} from "../../src/api/productAssembly";

const subject={kind:"AGENT",resourceId:"agent:focus-synthetic",revisionId:"revision:1",digest:"sha256:focus"};
const data:TraceabilityDTO={subject,claims:[{claimKey:"resource.lifecycle",productLabel:"Synthetic lifecycle",status:"SUPPORTED",limitationCodes:[],evidenceRefs:["review:1"],technicalFactKeys:[],affectedBusinessStepIds:[]}],evidence:[{evidenceId:"review:1",evidenceType:"HUMAN_REVIEW",subject,provenance:{synthetic:true},observedAt:null,limitationCodes:[]}],technicalFacts:[]};
const traceability="**/api/internal/v0.2.2/product/traceability/AGENT/**";

test.use({trace:"retain-on-failure",screenshot:"only-on-failure"});
for(const viewport of [{width:390,height:844},{width:1440,height:900}]){
 test(`Evidence close owns its DOM transition and preserves Tab focus ${viewport.width}`,async({page,context},testInfo)=>{
  await page.setViewportSize(viewport);
  // Synthetic-only projection. No backend, original acceptance state or provider.
  await page.route(/\/api\/(internal|workbench)\//,route=>route.fulfill({status:404,json:{}}));
  await page.route(traceability,route=>route.fulfill({json:data}));
  await page.addInitScript(()=>{
   type FocusEventRecord={type:string;key?:string;time:number;route:string;target:string;dialog:boolean};
   const state=window as unknown as {evidenceFocusEvents:FocusEventRecord[]};state.evidenceFocusEvents=[];
   const record=(type:string,key?:string)=>{const element=document.activeElement;state.evidenceFocusEvents.push({type,key,time:performance.now(),route:location.pathname,target:element?.id||element?.getAttribute("aria-label")||element?.tagName||"NONE",dialog:!!document.querySelector('[role="dialog"]')})};
   for(const type of ["keydown","keyup","focusin","focusout","click"])document.addEventListener(type,event=>record(type,event instanceof KeyboardEvent?event.key:undefined),true);
   document.addEventListener("click",event=>{if(event.target instanceof Element&&event.target.closest('[aria-label="Close Evidence Inspector"]'))record("close-handler-completed")});
   let dialog=false;new MutationObserver(()=>{const present=!!document.querySelector('[role="dialog"]');if(present!==dialog){dialog=present;record(present?"dialog-mounted":"dialog-unmounted")}}).observe(document,{childList:true,subtree:true});
  });
  const cdp=await context.newCDPSession(page);
  // Controlled scheduling stress reproduces the old pending React route commit.
  await cdp.send("Emulation.setCPUThrottlingRate",{rate:6});
  let release=()=>{};
  try{
   await page.goto(`/product-view?${new URLSearchParams({...subject,claimKey:"resource.lifecycle",view:"product"})}`);
   const claim=page.locator('[id="claim-resource.lifecycle"]'),link=claim.getByRole("link",{name:"Evidence review:1"}),close=page.getByRole("button",{name:"Close Evidence Inspector"});
   await link.focus();await page.keyboard.press("Enter");await expect(close).toBeFocused();
   await page.keyboard.press("Enter");
   const closeEvents=await page.evaluate(()=>(window as unknown as {evidenceFocusEvents:{type:string;dialog:boolean}[]}).evidenceFocusEvents.filter(event=>event.type==="close-handler-completed"));
   expect(closeEvents).toHaveLength(1);expect(closeEvents[0].dialog).toBe(false);
   await expect(claim).toBeFocused();
   await page.keyboard.press("Tab");await expect(link).toBeFocused();
   await page.keyboard.press("Enter");await expect(close).toBeFocused();await expect(page.getByRole("dialog")).toContainText("review:1");
   let requested=()=>{};const pending=new Promise<void>(resolve=>{requested=resolve}),held=new Promise<void>(resolve=>{release=resolve});
   await page.route(traceability,async route=>{requested();await held;await route.fulfill({json:data})},{times:1});
   await page.keyboard.press("Enter");
   // Intentionally no readiness wait: the next physical key must not reach the
   // inspector being removed. The real-service test separately awaits readiness.
   await page.keyboard.press("Tab");
   const events=await page.evaluate(()=>(window as unknown as {evidenceFocusEvents:{type:string;key?:string;dialog:boolean}[]}).evidenceFocusEvents);
   expect(events.filter(event=>event.type==="keydown"&&event.key==="Tab").at(-1)?.dialog).toBe(false);
   await expect(page.getByRole("dialog")).toHaveCount(0);await pending;
   await expect(page.locator(":focus")).toHaveCount(1);
   const userTarget=await page.locator(":focus").elementHandle();expect(userTarget).not.toBeNull();
   await expect(claim).toHaveCount(0);release();await expect(claim).toBeVisible();await expect(claim).not.toBeFocused();
   expect(await userTarget!.evaluate(element=>element===document.activeElement)).toBe(true);
  }finally{
   release();await cdp.send("Emulation.setCPUThrottlingRate",{rate:1});
   await testInfo.attach("focus-timeline",{body:JSON.stringify(await page.evaluate(()=>(window as unknown as {evidenceFocusEvents:unknown[]}).evidenceFocusEvents)),contentType:"application/json"});
  }
 });
}
