# Governance

This project is community-run with clear ownership and lightweight decision rules.

## Roles

- Project owner: Alejandro Pena ([`@adpena`](https://github.com/adpena))
- Maintainers: trusted contributors with merge/release permissions
- Reviewers: contributors who review docs/tooling/benchmark methodology changes

## Decision model

- Default path: rough consensus in pull requests.
- Source integrity and benchmark-policy changes require maintainer review.
- CinderX framing policy is non-negotiable for published comparisons in this repo:
  comparisons must be CinderX-baselined.

## Change categories

- `docs`: source-cited or explicitly marked TODO/hypothesis.
- `tooling`: must pass lint/test/build and include migration notes when behavior changes.
- `benchmark-policy`: must preserve or strengthen reproducibility and anti-mislabel guardrails.

## Enforcement and escalation

- Code of conduct applies to all repo interactions (`CODE_OF_CONDUCT.md`).
- Security reports follow private process in `SECURITY.md`.
- If consensus stalls, project owner makes the final decision with rationale documented in the PR.

## Maintainer expectations

- Be explicit about what is confirmed vs inferred.
- Favor reproducible evidence over anecdote.
- Keep contributor onboarding approachable and respectful.
