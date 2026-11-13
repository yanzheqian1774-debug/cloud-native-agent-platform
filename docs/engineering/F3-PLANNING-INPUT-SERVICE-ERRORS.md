# G1: separate preparation-service authentication from browser-session expiry

The BFF first authenticates the browser session, checks CSRF and LIST. The question
activity owner then authenticates its preparation service credential. Expiry there
raises AUTHENTICATION_REQUIRED and previously escaped as HTTP401, causing the
frontend to broadcast session-expired even while the browser session remained valid.

Translate only exceptions from that service authentication step: expired/missing
service credentials, service grant absence and storage/file failures become a
safe service-unavailable503; service policy scope rejection becomes403. Preserve
all BFF user authentication/CSRF/entry-grant handling, including genuine401. No
credential/configuration/grant changes and no skip of authentication. Stop before
source input, planning/model dispatch or execution. UI retains the original request
and shows service-specific recovery guidance, without automatic retries.

Real BFF route tests cover service credential expiry, missing service grant, policy
scope rejection, storage/file failure, genuine expired browser, and entry grant
denial. Assert service failures leave browser session readable and no downstream
owner is reached. Frontend build validates the existing original-conversation error
rendering. Actual credential renewal remains the mainline operator's task.
