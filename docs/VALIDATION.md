# Verification record

Fourteen automated API tests passed with a simulated model: account isolation; encrypted case storage; CSRF and cross-origin rejection; fact corrections; optimistic concurrency; explicit unknown values; invalid model field rejection; failure atomicity; gallery ordering; case deletion; session logout; illustration provenance; translation rejection; invitation gating; referral-data separation; rate limiting.

JavaScript syntax validation passed. No paid model calls or real patient data were used in the verification. The model, the clinical flow and translations have not undergone clinical validation. The reference bibliography has not been treated as a validated, executable guideline.

The default question sequence has 35 fields. A model may extract multiple explicitly provided fields from one message; the server asks the next remaining question. Unknown is a recorded value, never an assumed negative. The server does not classify malignancy risk or determine a diagnosis.

Source illustrations are AI-generated. Visual resemblance does not prove a diagnosis. Image selection does not modify clinical findings, and image bytes are never sent to the model.

The browser's print function generates the referral/PDF. Identity is entered in that form locally. Printed information must be reviewed and signed by the professional. An incomplete case can be printed at any time with missing fields identified.

Browser checks passed for registration/login, starting a case, resuming from history, referral form and print/PDF generation. Desktop and mobile screenshots were inspected; no JavaScript errors or mobile horizontal overflow were observed. Tests used synthetic content only.

The 16-figure gallery and a complete 35-field synthetic referral were also checked in the browser. The complete A4 export has two pages; all pages were rendered and visually inspected.
