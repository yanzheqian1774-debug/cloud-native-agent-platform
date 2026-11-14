# F3 login alignment (G1)

Presentation-only follow-up to the 702e login review. Keep the frozen F3 two-column introduction/form hierarchy, plain product tag, and self-contained login view without a second product navigation header. Do not copy the prototype viewer toolbar, simulated identities, demo password or SSO button. SSO is explicitly deferred.

Show the known local test environment only when the existing accounts flag is true; otherwise retain the existing product entry context. Do not invent tenant/workspace identity or add workspace selection. Put credential-delivery mechanics and SSO availability in the existing collapsed help. Add clear account/credential form subsection beneath context.

No account, nonce, session, CSRF, origin, return allowlist, authority, database or model changes. Existing backend render replaces only presentation text, with unchanged field names/actions and escaped values. Validate real renderer output in offline desktop/narrow browser views, errors and return fields, plus existing login boundary tests. Offline screenshots are not actual installed acceptance; root owns deployment and prototype review.
