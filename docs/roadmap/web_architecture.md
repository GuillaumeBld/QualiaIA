# QualiaIA – Web & VPS Architecture

This document describes how QualiaIA, MadaTech (StartHub), HedgeFund/AutoHedge, and the QualiaIA-Frontend fit together on the Hostinger VPS, and how QualiaIA can safely update web pages using a combination of **API‑driven** and **Git‑driven** content.

It focuses on **what is required at the web/VPS layer to run QualiaIA in production**.

For details on the Research and Marketing systems that feed into this architecture, see:
- `research_system.md`
- `marketing_system.md`

---

## 1. Hosting Overview (Hostinger VPS + Dokploy)

The Hostinger VPS is the "home" of QualiaIA.

On this VPS, managed via Dokploy and Docker, we run multiple services:

- **QualiaIA Core**
  - Orchestrator (`src/main.py`) and API (`src/api.py`)
  - Manages ventures (including HedgeFund), council, wallet, monitoring, and self‑dev logic.

- **MadaTech (StartHub Financing Hub)**
  - Web app where ventures are listed and funded.
  - Consumes QualiaIA APIs to display venture data and status.

- **HedgeFund / AutoHedge**
  - Separate service running the hedge fund agents (Director, Execution, Tickr, etc.).
  - QualiaIA treats this as one venture and allocates capital + risk limits.

- **Web Frontends** (marketing site, dashboards, docs)
  - Each frontend has its own GitHub repo.
  - Dokploy builds and deploys containers from these repos to subdomains on the VPS.

Typical routing (examples):

- `qualia.yourdomain.com` → QualiaIA API/dashboard
- `funding.yourdomain.com` → MadaTech StartHub
- `hedge.yourdomain.com` → AutoHedge visualization
- `www.yourdomain.com` → main marketing / public site

---

## 2. Content Model: API‑Driven + Git‑Driven

QualiaIA affects what users see on the web in two complementary ways.

### 2.1 API‑Driven Content (Live Data & State)

- **What:** dynamic data that changes often and is naturally computed by QualiaIA:
  - Venture list and details
  - Funding status (from MadaTech)
  - Hedge fund performance metrics
  - System status, KPIs, daily reports, etc.

- **How:** QualiaIA exposes read‑only JSON APIs, e.g.:
  - `GET /ventures` → list of ventures (including HedgeFund, self‑dev projects)
  - `GET /ventures/{id}` → details, milestones, KPIs, risk info
  - `GET /funds/hedge` → hedge fund performance and constraints

- **Frontends (web, MadaTech) consume these APIs** and render the data.
  - When QualiaIA updates its internal state or venture definitions, pages update automatically without redeployment.

### 2.2 Git‑Driven Content (Docs, Marketing, Investor Copy)

- **What:** more static but evolving text and media:
  - Venture one‑pagers and detailed write‑ups
  - Hedge fund overview / pitch / legal disclaimers
  - Company story, FAQs, docs, roadmap pages

- **Where:** stored in one or more dedicated GitHub repos as content files:
  - `content/ventures/*.md` or `content/ventures/*.json`
  - `content/funds/hedgefund.md`
  - Possibly MDX pages for richer layouts

- **How:**
  - Dokploy rebuilds and redeploys the site when content changes in Git.
  - QualiaIA can propose and eventually apply edits to these content files via a constrained "WebsiteUpdater" module.

This separation keeps **layout/framework code** human‑owned, while **data and narrative** can be gradually influenced by QualiaIA.

---

## 3. Safe Web Update Pipeline for QualiaIA

To let QualiaIA update pages without risking the whole site, we restrict how it can interact with web repos.

### 3.1 Scope Restrictions

- QualiaIA can only write under specific paths, e.g.:
  - `content/ventures/`
  - `content/funds/`
  - other whitelisted content directories
- It **cannot** modify:
  - `pages/`, `components/`, `app/` (framework code)
  - `Dockerfile`, CI configs, deployment scripts

### 3.2 Validation Before Push

Before committing content changes, WebsiteUpdater should:

- Validate file formats:
  - Markdown/MDX parses
  - JSON/YAML schema validity where applicable
- Optionally run a fast static check or build in a sandbox:
  - `npm run lint` or equivalent
  - (Later) a full `npm run build` in a controlled environment

If validation fails, QualiaIA should:

- Roll back the local change
- Log the failure and notify via the communication hub

### 3.3 Governance (Branches, PRs, Approvals)

Initial safe pattern:

- QualiaIA pushes content edits to a dedicated branch, e.g. `bot/content-updates`.
- It opens a Pull Request with:
  - Summary of changes
  - Motivation (why this update)
  - Risk assessment (e.g., "copy only", "no legal changes")
- A human reviews and merges the PR.
- Dokploy detects the merge and redeploys the site.

Later, for low‑risk areas (e.g., metrics snapshots, non‑legal docs), we can optionally allow:

- Auto‑merging under strict rules:
  - Tests + lint pass
  - Change stays within approved content sections
  - Council + human have pre‑agreed policies for such updates

---

## 4. Putting It Together

On your Hostinger VPS, at the web layer:

- QualiaIA core exposes APIs for ventures, funds, and system status.
- MadaTech and other frontends consume those APIs to show live data.
- Web frontends are deployed via Dokploy from GitHub repos.
- QualiaIA influences what users see by:
  - Updating **live data** via its APIs (API‑driven content)
  - Proposing and eventually applying **content changes** in web repos (Git‑driven content) through a controlled WebsiteUpdater module.

The Research and Marketing systems (documented separately) drive *what* should be surfaced, while this architecture doc focuses on *how* it gets surfaced safely.
