# AutoHedge / HedgeFund – QualiaIA-Managed Fund Idea

## Summary
The HedgeFund repo (AutoHedge) is an autonomous, multi-agent hedge fund environment
where specialized agents collaborate to manage a trading portfolio.

Repo: https://github.com/GuillaumeBld/HedgeFund

Core idea: QualiaIA does **governance, capital allocation, and oversight**, while AutoHedge
runs the specialized trading agents and simulations.

## Role in the QualiaIA Ecosystem
- Treat AutoHedge as a **venture** fully or partially owned by QualiaIA.
- QualiaIA decides **how much capital** to allocate to this hedge fund vs other ventures.
- QualiaIA monitors performance (returns, drawdown, risk metrics) and can scale up/down
  the allocation based on thresholds and council/human approvals.
- For external LPs, MadaTech can present the hedge fund as a funding opportunity,
  while QualiaIA enforces risk limits and reporting.

## Integration Points
- Wallet: QualiaIA treasury allocates capital to the hedge fund smart contracts/venues.
- Agents: AutoHedge agents focus on trading logic; QualiaIA focuses on meta-decisions
  (when to deploy, when to pause, when to reallocate).
- Monitoring: performance metrics from AutoHedge feed into QualiaIA's state and reports
  (daily report, risk alerts, council reviews).

## Open Questions
- Regulatory stance: which jurisdictions / investor types is this fund allowed to serve?
- How conservative should default allocation limits be (per-tx, daily, max AUM share)?
- How do we simulate and validate strategies before QualiaIA allocates real capital?
- What human approval flow is required for strategy changes or big reallocation moves?

## Next Steps
- Model the hedge fund as a first-class `Venture` in QualiaIA's `ventures` core module.
- Define metrics and thresholds that QualiaIA will watch for this venture.
- Decide on a minimal path to connect AutoHedge simulation results into QualiaIA's
  monitoring and reporting.
