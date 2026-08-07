<!--
Onboarding and promotion PRs are opened by automation; this template is what a reviewer reads.
Fill in what the automation could not know. An empty template is a reason to request changes.
-->

## What changes

- [ ] a project joins the **dry-run** configuration (additive, nothing is blocked)
- [ ] a member is **promoted to enforced** (from now on their traffic is really blocked)
- [ ] a **profile** changes (affects every division using it)
- [ ] a member is **offboarded** (stops being protected)
- [ ] a **raw exception** is added (needs security approval)

ServiceNow ticket: <!-- RITM… — must match the ticket verified by the intake workflow -->

## Why

<!-- The use case in one or two sentences. "The division asked for it" is not a why. -->

## Evidence (for promotions)

- Days in dry-run: <!-- from dry_run_since; the gate requires the window from policy.yaml -->
- Violations in the window: <!-- attach violations.json from violations-report -->
- Every legitimate flow has a rule: <!-- which profile covers what appeared in the report -->

## Blast radius

- Who feels it if this is wrong: <!-- which application / which team -->
- Rollback: `git revert` + apply, or break-glass for an ongoing incident
- Attribute budget after this change: <!-- from the validate job summary -->

## Reviewer checklist

- [ ] the project belongs to the division that requested it
- [ ] profiles match the described use case (no profile "just in case")
- [ ] no raw rule that an existing profile already covers
- [ ] pre-flight green (Private Google Access, DNS on the restricted VIP)
- [ ] for promotions: the observation window really is clean, and long enough to have seen rare jobs
