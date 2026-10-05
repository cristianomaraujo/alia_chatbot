# ALIA

Assessment of Lesions with Intelligent Assistance. Text-only AI support for collecting and organizing oral lesion triage findings. It can cautiously discuss possible compatible alterations supported by supplied findings and the owner rules, without confirming the nature of an alteration. It can make errors and requires professional review. Clinical content is limited to the project owner's supplied rules; the nine references are shown as bibliography only.

## Features

- Email/password accounts, invite registration in production, eight-hour sessions and per-user case access.
- Encrypted saved cases, sequential questions, explicit unknown values, editable findings and resumption.
- Language-name selector; automatic UI and conversation translations. Language availability does not imply validated clinical performance.
- Sixteen supplied AI-generated illustrations, optionally consulted by the professional. A separate consultation page displays the illustrations without selection or a triage step. No photo upload or image analysis. Illustration labels are never used as patient findings.
- Reviewed referral printable from the browser or saved using the browser's PDF option. Offered after the conversational synthesis and enabled after acceptance. Optional international registration field; patient identification stays in the referral form and is not transmitted to the API/model.
- External Google Maps search using city, country and specialty only. Offered within the conversation before the referral offer, with city and country collected separately after consent. No provider database, endorsement or validation of search results.

## Public demonstration

The login page offers three fictional case starting points without registration. Demonstration conversations use the same model and clinical rules as registered cases. Findings are entered by the visitor, not prefilled from the example. Referral exports carry a demonstration watermark.

Guest case payloads are held only in process memory, are inaccessible after one hour, logout or restart, and are never written to the case database. Each session allows two cases and 45 model-consuming operations. Starting sessions and model operations also have shared and per-address limits. These limits reduce API use but are not a billing cap; configure account spending controls separately. Login and invite registration remain available for permanent saved cases.

The full AI scope notice appears in the opening conversation message and platform; it is not appended to the referral document. Compatibility candidates require a source label and exact excerpt present in the owner rules plus explicitly recorded supporting fields. Missing source support yields no correspondence; insufficient findings yield an explicit limitation. This provenance check does not establish clinical validity. Corrected findings invalidate the prior synthesis and enabled referral. It is not automatically repeated at phase transitions or gallery completion.

## Local startup

Python 3.12. Install `requirements.txt`, set `OPENAI_API_KEY`, then run:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='YOUR_KEY'
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. In development, encrypted SQLite data and an automatically generated development key are stored under `data/`. Never commit them. Paid model calls are made only when starting/translating a non-Portuguese session or submitting conversation turns.

## Railway

1. Use this GitHub repository: `cristianomaraujo/alia_chatbot`.
2. Create a Railway project from the repository. Dockerfile and `railway.json` configure the process and `/health`.
3. Add a persistent volume mounted at `/data`. Keep one service instance and one worker for the SQLite prototype.
4. Set `APP_ENV=production`, `DATA_DIR=/data`, `OPENAI_API_KEY`, `OPENAI_MODEL`, a strong `REGISTRATION_CODE`, and `CASE_ENCRYPTION_KEY`.
5. Generate the encryption key locally with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Store a secure backup separately. Losing it makes saved cases unreadable; do not rotate it without a migration.
6. Generate a public domain and set `PUBLIC_ORIGIN` to its exact HTTPS origin. Cookies are secure in production. Redeploy.
7. Create an invited test account. Test triage, resumption, correction, printing, logout and cross-account isolation using synthetic cases.

No patient data, API keys or session secrets belong in GitHub. Back up the encrypted database and encryption key separately. Registration is disabled in production if no invitation code is configured. Password reset and email verification are not implemented in this prototype; do not present them as available functions.

## Layout

`app/main.py` owns API, sessions, case authorization, encryption and model access. `app/questions.py` defines the sequential collection fields. `app/static` contains the UI and supplied visuals. `knowledge/system.txt` defines the current cautious conversational scope; `original_rules.txt` preserves the supplied clinical wording with the completed closing phrase. `gallery.json`, `references.json`, and `ui.json` are separate catalogs.

## Validation and limitations

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests mock the model and check access control, encryption, CSRF, model failures, unknown facts, concurrency and collection flow. They do not establish clinical validity. Model extraction and educational explanations still need expert evaluation, including prompt injection, omission, multilingual equivalence and repeated conversational runs. Cautious compatibility discussion and clinical correctness are instructed but not proven by software tests. The app does not provide automatic follow-up timing or treatment recommendations.

Clinical rules mention concepts that may require additional source clarification; do not infer that every listed publication is a guideline or that every rule has been independently verified. The full papers are not incorporated. UI translations require the configured model and fail explicitly; prior transcript messages retain their original language.

Before use with identifiable clinical records, the operator needs to define jurisdiction-specific data handling, retention, backups and account administration. The current application intentionally asks for case codes and excludes patient identity fields from the API.

Visual previews with synthetic content are in `docs/preview/`. The invitation gate, encryption key, public origin and API key must be configured by the operator. Railway deployment remains a separate configuration step.
