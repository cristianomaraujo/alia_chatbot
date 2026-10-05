# Verification record

Fourteen automated API tests passed with a simulated model: account isolation; encrypted case storage; CSRF and cross-origin rejection; fact corrections; optimistic concurrency; explicit unknown values; invalid model field rejection; failure atomicity; gallery ordering; case deletion; session logout; illustration provenance; translation rejection; invitation gating; referral-data separation; rate limiting.

JavaScript syntax validation passed. No paid model calls or real patient data were used in the verification. The model, the clinical flow and translations have not undergone clinical validation. The reference bibliography has not been treated as a validated, executable guideline.

The default question sequence has 35 fields. A model may extract multiple explicitly provided fields from one message; the server asks the next remaining question. Unknown is a recorded value, never an assumed negative. The server does not classify malignancy risk or confirm the nature of an alteration. It can discuss possible compatible alterations within the supplied source rules.

Source illustrations are AI-generated. Visual resemblance does not prove a diagnosis. Image selection does not modify clinical findings, and image bytes are never sent to the model.

The browser's print function generates the referral/PDF. Identity is entered in that form locally. Printed information must be reviewed and signed by the professional. An incomplete case can be printed at any time with missing fields identified.

Browser checks passed for registration/login, starting a case, resuming from history, referral form and print/PDF generation. Desktop and mobile screenshots were inspected; no JavaScript errors or mobile horizontal overflow were observed. Tests used synthetic content only.

The 16-figure gallery and a complete 35-field synthetic referral were also checked in the browser. The complete A4 export has two pages; all pages were rendered and visually inspected.

Update: 20 API tests passed, including notice placement, temporary demo storage, demo/account isolation, expiry, CSRF, limits, shared model instructions, optional gallery and conversation after skipping or choosing no similar figure. Guest demo start, referral watermark, mobile layout and logout were checked in the browser without a live model call.

Conversational closing update: 25 API tests passed with a simulated model, including strict response schema, sourced compatibility, explicit insufficient/no-correspondence outcomes, early synthesis, consent ordering, corrections invalidating the summary, referral gating, and city/country separation. No real model or clinical validation was performed.

Browser verification passed for sequential summary/referral/services offers, conditional action visibility, separate city/country questions, fixed Google Maps URL encoding, referral synthesis and demonstration watermark, and mobile layout with no horizontal overflow. The two A4 referral pages were rendered and inspected.

Conversation regression checks: 28 automated tests passed, including duplicate-question suppression, clarification without advancing or recording unknowns, and suppression of intermediate clinical interpretation. Browser check confirmed automatic referral dialog after conversational consent, external city/country search, and no JavaScript errors or mobile horizontal overflow. Model responses were mocked; no clinical validation or live GPT-6 Luna evaluation was performed.

Workspace redesign: 29 simulated-model API tests passed. New conversations offer services before referral; declining or cancelling location still offers referral. Previous saved flow ordering is preserved for conversations already in progress. Browser checks verified the 16-image read-only consultation page, city/country search before the automatic referral dialog, no JavaScript errors and no mobile horizontal overflow. Desktop and mobile screenshots were visually inspected. No live-model or clinical validation was performed.

Structured record update: 42 simulated-model API tests passed. Regressions cover professional versus explicit patient attribution, original excerpts, separate states, unassessed statements not rewritten as negatives, conflicting measurements pending confirmation, explicit corrections, invalid excerpts, review gating/invalidation, owner-scoped evaluation exports, phase separation, unsupported synthesis rejection, and owner attention criteria. Browser checks with simulated model replies covered clarification without advancement, field provenance, state badges, service refusal followed by referral, professional review before document opening, state/origin information in the referral, evaluation JSON download, mobile conversation/record tabs, and absence of JavaScript errors or horizontal overflow. Desktop/mobile screenshots were inspected. The clinical source, question content, references and illustrations were not modified. No live OpenAI calls or clinical validation were performed.

Checked attention explanations are reused only while their supporting evidence is unchanged, avoiding repeated verification calls for unchanged owner criteria.

The browser also verified recovery from a stale case version with the message draft preserved. Repeated model contexts omit full original-message metadata, audit history and review identity while retaining field states and exact excerpts.
