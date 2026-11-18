---
name: ad-library-research
description: "Identify visible creative approaches that can inspire a distinct, substantiated brand test."
---

## Skill Name

Meta Ad Library Research

## Purpose

Identify visible creative approaches that can inspire a distinct, substantiated brand test.

## Trigger

Run only when the lifecycle orchestrator selects `ad-library-research`.

## Required Inputs

Competitor Research result and relevant earlier evidence. Read the selected run, product, strategy and campaign target as applicable.

## Required Files

`.agents/skills/meta-ads/references/policy.md`, the effective brand policy, and the orchestrator's referenced result records. For execution or handoff, also read `README.md`.

## Tools & APIs

Public Meta Ad Library, web or authorized browser.

## Instructions

Read [the practical decision guide](references/decision-guide.md) before preparing this step.

1. Use Meta Ad Library with intended country and the relevant category. Start with verified advertiser Pages, then search product and category terms. Record date, country, search terms, Page, library ID or URL, and which sources were accessible.
2. For each ad, record the opening scene or hook, product reveal, proof type, offer, format, CTA and destination when visible. Group near-identical variants as one concept so duplicated versions do not inflate the pattern. Infer the shopper question and stage as hypotheses.
3. Build a short list of adaptable mechanisms, such as product demonstration or routine explanation. Tie each to a verified product fact and a customer question. Carry no competitor wording or unsupported result promise into Create.

## Rules

When the library is inaccessible, persist the failed query and scope as limited evidence. Apply the shared operating rules.

## Decision Logic

An active or long-running ad is evidence of visible use. Its spend, targeting and sales remain unknown unless directly disclosed by a reliable source. If the API and UI show different coverage, report their scopes and limits separately. [Meta Ad Library](https://www.facebook.com/ads/library/) · [Meta Ads Archive reference](https://developers.facebook.com/docs/graph-api/reference/ads_archive/)

## Output

Find observable ad concepts and message patterns; save the findings as a step result with dated source references.

## Output Schema

The envelope uses `status`, `summary`, `evidence`, `data` and, for a blocked or limited result, `blockers`. Required `data` keys: `queries`, `ads`, `patterns`, `coverage`. See the operator guide for types and special cases.

## Validation

Verify references, dates, scope and required fields. Reconcile contradictions. Check that conclusions follow from the evidence and list limitations before submission.

## Error Handling

Record the failed source or step and the next concrete action. Retry transient reads within provider limits. Do not retry an ambiguous write or change the approved target to bypass a failure.

## Approval

Read/analysis only; no approval or Meta mutation at this step.

## Execution Log

The orchestrator records run, step and UTC timestamp. Include source timestamps, precise decisions and blockers; store receipts via the executor.

## Next Step

Account Research. Follow the CLI's returned route.
