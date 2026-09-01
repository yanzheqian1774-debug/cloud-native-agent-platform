import { expect, test } from "@playwright/test";
import { parseUrlContext, serializeUrlContext, type CanonicalUrlContext } from "../../src/shared/urlContext";

test("canonical URL context is deterministic and round-trip stable", () => {
  const context:CanonicalUrlContext={
    kind:"AGENT",resourceId:"agent:quality",revisionId:"revision:1",digest:"sha256:exact",
    view:"evidence",evidenceId:"review:1",relationshipId:"relationship:1",claimKey:"resource.lifecycle",
    factKey:"resource.lifecycle",businessStepId:"govern-resource",query:"quality",kindFilter:"AGENT",
    lifecycleFilter:"PUBLISHED",timeFrom:"2026-08-01T00:00:00Z",timeTo:"2026-09-01T00:00:00Z",
    returnTo:"/catalog?query=quality&kind=AGENT&status=PUBLISHED",
  };
  const serialized=serializeUrlContext(context);
  expect(serialized).toBe("kind=AGENT&resourceId=agent%3Aquality&revisionId=revision%3A1&digest=sha256%3Aexact&view=evidence&evidenceId=review%3A1&relationshipId=relationship%3A1&claimKey=resource.lifecycle&factKey=resource.lifecycle&businessStepId=govern-resource&query=quality&kindFilter=AGENT&lifecycleFilter=PUBLISHED&timeFrom=2026-08-01T00%3A00%3A00Z&timeTo=2026-09-01T00%3A00%3A00Z&returnTo=%2Fcatalog%3Fquery%3Dquality%26kind%3DAGENT%26status%3DPUBLISHED");
  expect(parseUrlContext(serialized)).toEqual({state:"VALID",context});
});

test("invalid, partial, duplicate, external, and sensitive URL context fails closed", () => {
  for(const search of [
    "kind=AGENT&resourceId=agent%3Aquality",
    "view=latest",
    "view=product&view=technical",
    "returnTo=https%3A%2F%2Fexample.com",
    "returnTo=%2Fcatalog%3Ftoken%3Dsecret",
    "namespace=tenant-a",
  ]) expect(parseUrlContext(search)).toEqual({state:"INVALID",reason:"INVALID_URL_CONTEXT"});
});
