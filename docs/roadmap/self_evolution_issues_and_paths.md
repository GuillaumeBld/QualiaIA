# QualiaIA – Self‑Evolution Issues and Solution Paths

Goal: enable QualiaIA to gradually **rewrite parts of its own code**, **tune its behavior**, and **scale/grow itself** safely, with human and council oversight.

This document lists the main open issues and a proposed path forward for each. It is a design/work‑in‑progress doc, not final spec.

---

## 1. Product & Use Cases

**Issue**  
Vision is clear (autonomous business system / holding company), but v1 workflows are not crisply defined. The system lacks machine‑readable descriptions of what “success” looks like per workflow.

**Path / Direction**
- Define 2–3 canonical workflows as structured specs, e.g.:
  - "Handle a new business idea from intake → decision → first experiment"
  - "Propose an improvement to an existing venture"
- For each workflow, specify:
  - Goal (KPIs, time horizon, constraints)
  - Signals (metrics QualiaIA can observe)
  - Levers (things it is allowed to change: prompts, thresholds, routing, etc.)
- Store these as config / YAML / JSON so future self‑dev agents can:
  - Inspect underperforming workflows
  - See what levers exist
  - Propose changes targeted at specific workflows.

---

## 2. Users & Interaction (Human Owner UX)

**Issue**  
Telegram, dashboard, etc. are defined, but there is no explicit **developer / self‑dev UX** for QualiaIA to discuss code changes and experiments with the human owner.

**Path / Direction**
- Add a `/dev` command namespace on the primary channel (Telegram):
  - `/dev_status` – show active experiments and pending self‑change proposals
  - `/dev_propose` – QualiaIA sends a summarized proposal (what to change, why, risks)
  - `/dev_diff` – show a human‑readable description of the planned diff or config change
  - `/dev_approve` / `/dev_reject` – explicit owner approval for applying changes
- Standardize message schemas:
  - Reason / hypothesis
  - Impacted components
  - Risk level and rollback plan
- This becomes the main **human ↔ self‑dev negotiation interface**.

---

## 3. Governance & Decisions (Including Self‑Modification)

**Issue**  
The tiered decision system (auto / council / human) exists for financial ops, but self‑modification of code and policies is much more sensitive and needs its own explicit rules.

**Path / Direction**
- Introduce a dedicated **Tier 4: Self‑Modification** policy:
  - Always requires council deliberation
  - Always requires human approval
  - Requires tests and simulations to pass in a sandbox environment
- Represent policies explicitly (e.g. JSON / YAML):
  - `action_type` (e.g. `code_change`, `config_tweak`, `prompt_update`)
  - `max_impact` (low / medium / high)
  - `required_checks` (tests, simulations, legal review, etc.)
- Extend council prompts to reason about:
  - Alignment with owner’s goals and risk tolerance
  - Long‑term consequences of enabling certain classes of self‑change
- Log all Tier‑4 decisions separately for audit and post‑mortems.

---

## 4. Wallet / Treasury (Including Self‑Dev Budget)

**Issue**  
Treasury controls exist, but there is no explicit **budget for self‑improvement** (R&D, infra, external agents) separate from normal venture spending.

**Path / Direction**
- Add a "Self‑Dev / R&D" budget section to config:
  - Monthly cap for self‑improvement spend
  - Per‑project caps
- Tag all transactions with a `purpose` field:
  - `venture`, `ops`, `self_dev`, etc.
- Allow QualiaIA to propose **self‑dev ventures** (see HedgeFund, infra, tooling) that request R&D budget via MadaTech (or internal approval).
- Over time, enable adaptive budgeting rules:
  - If historical ROI from self‑dev ventures is good, gradually increase allowed budget ceilings (with council + human assent).

---

## 5. Risk & Safety (For Self‑Evolution)

**Issue**  
Safety mechanisms exist for financial operations, but there is no explicit safety pipeline for self‑modification (code and config changes).

**Path / Direction**
- Define a **Self‑Dev Safety Pipeline** with stages:
  1. **Sense** – aggregate logs/metrics to detect problems (high error rate, human overrides, etc.)
  2. **Propose** – generate a structured improvement proposal (what to change, expected benefits), not raw code yet
  3. **Validate** – run automatic checks:
     - Unit tests
     - Static analysis (lint, types)
     - Domain simulations (e.g., fake wallet txs, paper‑trading for strategies)
  4. **Govern** – council + human review of proposal and validation results
  5. **Apply** – apply changes only if all previous stages succeed
  6. **Monitor & Rollback** – watch post‑deploy metrics; revert on regressions
- Treat this pipeline configuration itself as data, so it can be improved cautiously over time.

---

## 6. Tech Architecture (Self‑Modification‑Friendly)

**Issue**  
Architecture is modular but not yet clearly split between "hard" safety‑critical core and "soft" tweakable behavior. Self‑modification should start with the soft surface.

**Path / Direction**
- Clearly separate:
  - **Core kernel** – wallet signing, auth, limits, policy enforcement (very hard to change)
  - **Soft skills** – prompts, scoring functions, agents, opportunity filters, routing logic (easy to change)
- Design extension points:
  - Plugin‑style agents
  - Prompt templates in config / files
  - Policy modules that can be swapped with versioning
- Stage self‑modification rollout:
  1. Phase 1 – only config + prompt tuning
  2. Phase 2 – plugin/module swapping with strict interfaces
  3. Phase 3 – full code diffs with heavy governance and tests

---

## 7. Data, Logging, Observability (For Learning What to Change)

**Issue**  
Metrics and logs exist, but there is no structured "learning loop" that turns observations into improvement opportunities.

**Path / Direction**
- Extend logging/metrics to capture:
  - Decision path (auto / council / human)
  - Outcomes (success/failure, revenue, user satisfaction proxies)
  - Where humans overrule the system
- Create a periodic **Self‑Review Job** that:
  - Reads logs/metrics
  - Clusters failures, overrides, and underperforming ventures
  - Emits structured "improvement opportunities", e.g.:
    - `{"area": "opportunity_scoring", "symptom": "too many false positives", "evidence": ...}`
- Feed these opportunities into the self‑dev agent as its **backlog**, rather than letting it roam aimlessly over the codebase.

---

## 8. Legal & Compliance Constraints

**Issue**  
Legal entities and regulations are described conceptually, but constraints are not represented as machine‑checkable policies that can gate self‑change.

**Path / Direction**
- Model legal/compliance rules as structured policies, e.g.:
  - Per region: GDPR/CCPA data rules, retention, consent
  - Per action type: what checks are required (e.g. KYC for certain financial flows)
- For every self‑dev proposal, require a **compliance impact assessment**:
  - Which policies are touched?
  - Does data flow change? Any new data sources/sinks?
- Add a compliance agent that can:
  - Review self‑dev proposals against policies
  - Veto or request modifications
- Log compliance decisions alongside technical governance decisions.

---

## 9. Operations & Deployment (Environments for Safe Self‑Change)

**Issue**  
CI/CD exists, but environments are not clearly organized for experiments vs production, especially for autonomous changes.

**Path / Direction**
- Standardize three environments:
  - `dev` – experimentation, can break
  - `staging` – realistic sandbox (fake funds, sandbox APIs)
  - `prod` – real operations
- Self‑dev rules:
  - QualiaIA can propose and test changes only against `dev`
  - Successful changes can be auto‑deployed to `staging` for shadow/soak testing
  - Promotion to `prod` requires human approval (and possibly council sign‑off)
- Tailor CI pipeline for self‑modification:
  - Require tests for any self‑proposed change
  - Block merges if coverage drops or critical tests fail

---

## 10. Self‑Evolution Loop – Phased Roadmap

**Issue**  
The ultimate goal (self‑rewriting, self‑scaling QualiaIA) is ambitious; we need phased capability levels.

**Path / Direction**
- **Phase 0 – Manual evolution**
  - Humans and external AIs (like this assistant) evolve QualiaIA by hand
- **Phase 1 – Self‑review + suggestions**
  - QualiaIA automatically surfaces improvement opportunities and suggests:
    - Config tweaks
    - Prompt revisions
    - High‑level design changes (descriptions, not code)
- **Phase 2 – Supervised self‑modification**
  - Introduce a self‑dev agent that proposes concrete patches (diffs) on a dev branch
  - Full safety pipeline + council + human approval required
- **Phase 3 – Limited autonomous changes**
  - In clearly bounded, low‑risk areas (e.g. analytics, non‑critical UX), allow auto‑merging when:
    - Tests + simulations pass
    - Council consensus is strong
    - Changes fit within pre‑defined safe patterns

This document is intended as a living roadmap: we can refine each section into more detailed specs and implementation tickets as QualiaIA and its ecosystem (MadaTech, HedgeFund, etc.) evolve.
