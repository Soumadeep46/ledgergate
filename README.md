# LedgerGate

## Compliance-Aware Merchant Verification & Revenue Recovery

LedgerGate is an AI-assisted merchant verification and revenue-recovery prototype built for the Razorpay Buildathon.

It helps identify merchant-verification exceptions that may prevent a merchant from accepting payments, recommends safe next actions, routes uncertain cases to human reviewers, and estimates the potential revenue impact of faster resolution.

> **Important:** LedgerGate uses entirely synthetic data. It is not connected to Razorpay production systems and does not perform live PAN, GSTIN, bank, sanctions, identity, or government verification.

---

## Why LedgerGate?

Merchant onboarding is not simply an approval-or-rejection problem.

A merchant may be blocked because of:

- Missing or low-quality documents
- Blurry or cropped evidence
- Low OCR confidence
- Legal-name and trade-name variations
- Bank-account name mismatches
- Address inconsistencies
- Duplicate applications
- Conflicting or restricted-entity signals
- Inactive or inconsistent GST information

Some exceptions can be safely resolved by requesting better evidence. Others require human judgment or must remain blocked for compliance reasons.

LedgerGate separates these outcomes instead of treating every exception as an automatic approval or rejection.

---

## Product Overview

LedgerGate combines:

1. **Deterministic verification rules** for consistent and auditable decisions
2. **AI-assisted evidence understanding** and decision preparation
3. **Bounded remediation** for issues that can safely be corrected
4. **Human-in-the-loop review** for ambiguous cases
5. **Append-only audit history** for traceability
6. **Revenue-impact estimation** to prioritize operational work

### Core principle

> **AI assists with evidence understanding and decision preparation. Deterministic rules and human review retain compliance authority.**

The AI does not autonomously:

- Approve a merchant
- Reject a merchant
- Override a compliance block
- Convert a hard compliance failure into an approval
- Use GMV to bypass verification rules

GMV is used only to prioritize work and estimate business impact. It never determines compliance eligibility.

---

## Workflow Architecture

```text
Merchant application
        |
        v
Case normalization
        |
        v
Document quality and evidence extraction
        |
        v
Deterministic verification rules
        |
        v
Exception classification and prioritization
        |
        +-----------------------------+
        |                             |
        v                             v
Safe evidence remediation       Human review / hard block
        |                             |
        v                             v
Revalidation                  Explainable decision brief
        |                             |
        +-------------+---------------+
                      |
                      v
               State transition
                      |
                      v
               Audit event ledger
                      |
                      v
             Estimated revenue metrics
```

---

## Exception Categories

Every case is classified into one of three categories.

### 1. `SAFE_TO_REMEDIATE`

Issues that may be resolved through bounded evidence correction.

Examples:

- Missing address proof
- Blurry document
- Cropped document
- Low OCR confidence
- Minor trade-name variation

Typical workflow:

```text
Issue detected
    -> Correction requested
    -> Replacement evidence submitted
    -> Revalidation
    -> Approval if all rules pass
```

### 2. `AMBIGUOUS_REVIEW`

Cases where the evidence is unclear or conflicting and a human must make the final decision.

Examples:

- Borderline name similarity
- Conflicting documents
- Unclear address mismatch
- Inconclusive bank-name match

### 3. `HARD_COMPLIANCE_BLOCK`

Cases that cannot be auto-approved or auto-remediated.

Examples:

- Inactive GST signal
- Restricted-entity signal
- Document-tampering signal
- Confirmed compliance inconsistency
- Serious conflicting evidence

---

## State Machine

The dashboard demonstrates the following lifecycle:

```text
RECEIVED
    -> PROCESSING
    -> NEEDS_EVIDENCE
    -> REVALIDATING
    -> APPROVED
    -> REVENUE_UNLOCKED
```

Other outcomes include:

```text
PROCESSING -> HUMAN_REVIEW
PROCESSING -> HARD_COMPLIANCE_BLOCK
PROCESSING -> REJECTED
```

`REVENUE_UNLOCKED` represents an estimated business-impact outcome in this prototype. It should be interpreted as the merchant becoming eligible to accept payments after successful verification, not as a claim of actual recovered Razorpay revenue.

---

## Features

- Synthetic merchant application dataset
- Deterministic verification rules
- Simulated document-quality and OCR checks
- Exception classification and prioritization
- Risk and GMV-based prioritization
- Bounded evidence remediation
- Revalidation workflow
- Human-in-the-loop review co-pilot
- Explainable decision summaries
- Append-only audit history
- Sanitized audit events
- Revenue-impact estimation
- FIFO benchmark comparison
- Streamlit dashboard
- Automated tests for rules, routing, and metrics
- Safe deterministic fallback when no AI API key is configured

---

## Technology Stack

- **Python**
- **Streamlit**
- **Pandas**
- **Pytest**
- **Deterministic rule engine**
- **Optional AI service integration**
- **JSON-based synthetic case data**

---

## Project Structure

```text
ledgergate/
|
├── app.py                       # Streamlit dashboard
├── requirements.txt
├── README.md
├── .gitignore
|
├── data/
│   ├── generate_cases.py        # Synthetic dataset generator
│   └── generated_cases.json     # Local generated data; not committed
|
├── core/
│   ├── models.py                # Case, Merchant, and enums
│   ├── rules.py                 # Deterministic verification rules
│   ├── classifier.py            # Exception classification and priority
│   ├── remediation.py           # Safe evidence-correction workflow
│   ├── audit.py                 # Append-only audit ledger
│   └── metrics.py               # Revenue and benchmark calculations
|
├── services/
│   ├── document_service.py      # Simulated OCR and extraction
│   └── ai_service.py            # AI explanations and review briefs
|
└── tests/
    ├── test_rules.py
    ├── test_routing.py
    └── test_metrics.py
```

> The large dataset generator and large generated datasets are intentionally excluded from the public repository where applicable. The repository contains the application code and files required for a lightweight demonstration.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Soumadeep46/ledgergate
cd ledgergate
```

### 2. Create a virtual environment

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

#### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Generate Synthetic Data

Run the generator locally:

```bash
python data/generate_cases.py
```

The default demonstration dataset contains approximately 200 synthetic merchant cases distributed across:

- `SAFE_TO_REMEDIATE`
- `AMBIGUOUS_REVIEW`
- `HARD_COMPLIANCE_BLOCK`

The generated file is written to:

```text
data/generated_cases.json
```

The generated dataset is not real merchant data and must not be interpreted as live verification output.

---

## Run the Dashboard

Start the Streamlit application:

```bash
streamlit run app.py
```

The dashboard normally opens at:

```text
http://localhost:8501
```

The dashboard includes:

- Overview
- Verification Queue
- Case Detail
- Human Co-Pilot
- Benchmark and revenue metrics
- Audit History
- Verification and remediation actions

---

## Run Tests

```bash
pytest tests/ -v
```

The tests cover:

- Deterministic rule behavior
- Exception classification
- Routing safety
- GMV prioritization without compliance override
- Revenue metric calculations
- Zero estimated revenue for rejected or hard-blocked cases
- State-transition behavior

A successful test run is expected to show all project tests passing.

---

## Revenue-Impact Estimation

LedgerGate estimates potential revenue impact using a synthetic formula:

```text
Estimated Revenue Impact
=
Monthly GMV
× Take Rate
× (Time Saved / 720)
× Confidence
```

### Current assumptions

- Take rate: `0.02`, configurable
- `720`: approximate hours in a 30-day month
- Confidence:
  - `1.0`: successfully eligible to accept payments
  - `0.7`: pending or partially resolved
  - `0.3`: evidence issue fixed but not fully approved
  - `0.0`: rejected, escalated, or hard-blocked

These numbers are illustrative estimates. They are not actual recovered revenue, actual Razorpay metrics, or production performance claims.

---

## Benchmark

The dashboard compares LedgerGate with a synthetic FIFO baseline.

The benchmark is intended to demonstrate the potential effect of prioritization and bounded remediation on resolution time.

It is based on:

- Synthetic applications
- Simulated resolution times
- An assumed FIFO baseline
- Estimated business impact

The benchmark must not be interpreted as a comparison against Razorpay's real internal operations.

---

## Safety and Governance Guarantees

LedgerGate is designed with the following safeguards:

1. GMV affects queue priority only.
2. GMV cannot override compliance outcomes.
3. Hard-compliance cases cannot reach approval through an AI-driven path.
4. AI recommendations are validated by deterministic rules.
5. Ambiguous cases are routed to human review.
6. Rejected and blocked cases receive zero estimated revenue unlock.
7. Audit events record important state transitions and actions.
8. Raw PAN, GSTIN, and document contents are not written to the audit log.
9. Replacement evidence is handled ephemerally in the simulated workflow.
10. All data is synthetic and isolated from production systems.

---

## Optional AI Integration

The dashboard works without an AI API key.

Without a key, the application uses deterministic fallback explanations and templates. This allows the complete demo, tests, and core workflow to run locally.

To enable live AI-generated explanations or review briefs, configure the relevant API key in your local environment.

### Windows PowerShell

```powershell
$env:ANTHROPIC_API_KEY="your_key_here"
```

### macOS/Linux

```bash
export ANTHROPIC_API_KEY="your_key_here"
```

Never commit API keys, secrets, or `.env` files to GitHub.

---

## Suggested Demo Flow

A 3–4 minute demonstration can follow this sequence:

1. Open the dashboard and show the synthetic application count.
2. Explain the three exception categories.
3. Open a blurry-document or missing-evidence case.
4. Show the deterministic checks and AI explanation.
5. Send a correction request.
6. Upload or simulate replacement evidence.
7. Re-run verification and show the state transition.
8. Open an ambiguous case and demonstrate human review.
9. Open a hard-compliance case and show that it cannot be auto-approved.
10. Show the audit trail.
11. Show the benchmark and estimated revenue metrics.
12. End by highlighting zero autonomous compliance overrides.

---

## Limitations

This is a buildathon prototype and has important limitations:

- Data is synthetic.
- Government, bank, sanctions, and identity checks are simulated.
- OCR and document processing are simulated.
- Revenue calculations are estimates.
- The system is not connected to Razorpay production infrastructure.
- The prototype does not establish legal or regulatory compliance.
- Production deployment would require secure integrations, access controls, monitoring, retention policies, model evaluation, and compliance approval.

---

## Future Improvements

Possible next steps include:

- Integration with approved verification providers
- Real document-quality models
- Calibrated entity-matching models
- Human-review feedback loops
- Drift and fairness monitoring
- Role-based access control
- Secure object storage
- Production-grade audit infrastructure
- Larger synthetic benchmark suites
- Offline evaluation against labeled verification outcomes
- Latency and cost monitoring
- Multilingual merchant communication

---

## Disclaimer

LedgerGate is an independent buildathon prototype.

It is not connected to Razorpay's production systems and does not represent Razorpay's actual policies, verification timelines, internal tools, customer data, or operational performance.

All merchant records, documents, identifiers, verification results, revenue values, and benchmark figures used in this repository are synthetic or simulated.
