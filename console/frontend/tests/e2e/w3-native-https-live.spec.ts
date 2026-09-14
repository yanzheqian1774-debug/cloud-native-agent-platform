import {expect,test,type BrowserContext} from "@playwright/test";

test.skip(
  process.env.S5_V023_IMPL_299_LIVE !== "1",
  "requires the exclusive IMPL-299 native HTTPS harness",
);

async function login(context:BrowserContext,credential:string){
  const page=await context.newPage();
  await page.goto("/api/workbench/v1/login");
  await page.locator('input[name="bootstrapCredential"]').fill(credential);
  await Promise.all([
    page.waitForURL(url=>url.pathname==="/work"),
    page.getByRole("button",{name:"Sign in"}).click(),
  ]);
  return page;
}

test("native HTTPS preserves browser origin metadata and CSRF rejection",async({browser})=>{
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  const page=await login(context,process.env.IMPL299_ALICE_CREDENTIAL!);
  const origin=new URL(page.url()).origin;
  expect(origin.startsWith("https://")).toBe(true);
  const session=await page.evaluate(async()=>fetch("/api/workbench/v1/session").then(response=>response.json()));
  const observedPromise=page.waitForRequest(request=>request.method()==="POST"&&new URL(request.url()).pathname==="/api/workbench/v1/session/rotate").then(request=>request.allHeaders());

  const rotated=await page.evaluate(async csrf=>fetch("/api/workbench/v1/session/rotate",{method:"POST",headers:{"X-CSRF-Token":csrf}}).then(async response=>({status:response.status,body:await response.text()})),session.csrfToken);
  expect(rotated.status,rotated.body).toBe(204);
  const observed=await observedPromise;
  expect(observed.origin).toBe(origin);
  expect(observed["sec-fetch-site"]).toBe("same-origin");

  const stale=await page.evaluate(async csrf=>fetch("/api/workbench/v1/session/rotate",{method:"POST",headers:{"X-CSRF-Token":csrf}}).then(async response=>({status:response.status,body:await response.json()})),session.csrfToken);
  expect(stale).toMatchObject({status:403,body:{reasonCode:"CSRF_VALIDATION_FAILED"}});
  const missing=await page.evaluate(async()=>fetch("/api/workbench/v1/session/rotate",{method:"POST"}).then(async response=>({status:response.status,body:await response.json()})));
  expect(missing).toMatchObject({status:403,body:{reasonCode:"CSRF_VALIDATION_FAILED"}});

  const foreign=await context.newPage();
  const foreignOrigin=origin.replace("127.0.0.1","localhost");
  await foreign.goto(foreignOrigin);
  const responsePromise=foreign.waitForResponse(response=>new URL(response.url()).pathname==="/api/workbench/v1/session/rotate");
  await foreign.evaluate(action=>{
    const form=document.createElement("form");
    form.method="POST";
    form.action=action;
    document.body.append(form);
    form.submit();
  },`${origin}/api/workbench/v1/session/rotate`);
  const foreignResponse=await responsePromise;
  expect(foreignResponse.status()).toBe(403);
  expect(await foreignResponse.json()).toMatchObject({reasonCode:"CSRF_VALIDATION_FAILED"});
  await context.close();
});
