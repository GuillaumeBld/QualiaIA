# QualiaIA – Research System

The **Research System** is QualiaIA's R&D and learning team.

It specializes in discovering and understanding new tools, architectures, technologies, and methods that can:

- Make QualiaIA more capable
- Give it more agency
- Help it take better decisions for ventures and the hedge fund

It also gathers and structures information to support:

- Venture discovery and design
- Strategy improvements (including for HedgeFund/AutoHedge)
- Market & regulatory awareness

---

## Responsibilities

- **Market & Opportunity Research**
  - Track industries, niches, and trends
  - Identify potential ventures and validate problem/solution fit

- **Technical & Tooling Research**
  - Discover frameworks, APIs, and tools that can make QualiaIA and ventures more capable
  - Evaluate tradeoffs (cost, complexity, risk, lock‑in)

- **Regulatory & Legal Research** (in collaboration with `src/legal`)
  - Monitor relevant legal changes (AI, data protection, financial regulation)
  - Surface constraints and opportunities to the council and venture manager

- **Support for Ventures & HedgeFund**
  - Provide research reports to the venture manager and AutoHedge agents
  - Supply data and narratives for MadaTech venture proposals

---

## Outputs

- Structured research briefs (e.g., YAML/JSON + markdown summaries)
- Scored opportunity lists
- Risk/benefit analyses that can be consumed by:
  - Council deliberation
  - Venture manager
  - Marketing system

Over time, these outputs can also drive the self‑evolution loop by informing which tools/architectures QualiaIA should adopt next. In terms of **production readiness**, the Research System defines what must be monitored and learned so QualiaIA can stay up to date and safe in a live environment.

---

## Integration Points

- Feeds into **VentureProposal** creation for MadaTech
- Feeds into **self‑review jobs** for improvement ideas (e.g. new markets, new trading strategies, new infra)
- Provides evidence and background for web content (via the Marketing System)
- Informs configuration and architecture changes that the self‑dev pipeline may later propose
