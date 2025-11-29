# MadaTech StartHub – Financing Hub Idea

## Summary
MadaTech is a startup financing hub that QualiaIA uses to present vetted venture ideas to human investors and partners.
It acts as the public/partner-facing "deal room" for ventures generated and operated by QualiaIA.

Repo: https://github.com/GuillaumeBld/MadaTech

## Role in the QualiaIA Ecosystem
- QualiaIA designs and validates ventures, then marks them as **READY_FOR_FUNDING**.
- Each ready venture is exported as a structured proposal and published to MadaTech.
- MadaTech lists these ventures, shows required capital and milestones, and lets investors commit funds.
- When funding targets are reached, MadaTech signals back to QualiaIA so the venture can move to **FUNDED → ACTIVE**.

## Key Questions / Design Notes
- What is the exact data schema for a **VentureProposal** shared between QualiaIA and MadaTech?
- How is funding status communicated back (API, webhooks, repo PRs, or manual for v1)?
- How do we differentiate **external ventures** vs **QualiaIA self-development ventures**?
- What metrics should MadaTech display (risk, expected ROI, time horizon, impact)?

## Next Steps
- Define a JSON/YAML schema for `VentureProposal` and store examples alongside this file.
- Implement export of ventures from `src/core/ventures.py` into that schema.
- Prototype a simple MadaTech view that reads sample proposals and renders them.
