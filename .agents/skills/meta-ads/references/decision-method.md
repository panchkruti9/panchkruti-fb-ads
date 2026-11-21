# Make a useful purchasing decision

Read this with the selected skill's decision guide. Knowledge reviewed 21 November 2026. This is a method for the agent; the client does not fill in a technical research form.

## Evidence and reasoning

Distinguish provider facts, account observations, practitioner heuristics and hypotheses. Save source, date, market, scope and limitations. A competitor ad, a forum success story and a product-page claim have different evidential roles. An ad's longevity does not establish profit. Retrieve official documentation when fields, permissions or behavior are uncertain. Recheck knowledge on relevant platform changes or errors; do not repeat all web research on every daily review.

For each meaningful choice record the evidence, selected action, strongest alternative, expected observation and what would change the decision. Preserve hypothesis → test → exposure → result → conclusion → next action across cycles. Use a previous failed hypothesis again only when a changed condition gives a reason. These records assess traceability, not a mechanical guarantee of strategy quality.

## The strategy contract

For management runs using decision contract version 2, Strategy Development supplies `data.decision_contract`:

```json
{
  "buyer": "The plausible shopper, distinguishing observations from inference",
  "buying_situation": "What happened that makes this purchase relevant",
  "objection": "The purchase question the test should resolve",
  "offer": "Actual product, price, contents and current verified terms",
  "message": "The buying reason to communicate",
  "proof": "What the asset and destination can demonstrate, with source references",
  "delivery": "Audience, placements, structure and funding rationale",
  "test_question": "What we can learn at the available spend",
  "alternatives": ["Another reasoned hypothesis if this one is contradicted"],
  "decision_conditions": {
    "continue": "Observable conditions supporting continued delivery",
    "change": "Evidence that would favor a specific alternative",
    "stop": "Operational or economic conditions that end this test"
  }
}
```

Carry the chosen message into the actual copy, visual and destination. If production changes the angle, revise the strategy record explicitly instead of claiming the original hypothesis was tested.

## Budget and evidence

Use verified contribution economics for a viable acquisition cost. Contribution before ads is retained receipts less applicable product, fulfillment, shipping and payment costs. Affordable acquisition cost must also leave the client's required contribution. A selling-price percentage or competitor CPA is not a viable financial target.

With missing costs, use existing approved spending for bounded learning. Retrieve available Shopify costs, shipping/payment information and actual retained orders; ask once for genuinely unavailable material costs. Do not claim profitable scaling. Do not create another mandatory client test-budget field.

`criteria.learning_spend_minor` is the agent's documented exposure/loss bound for the current question; it is not a fabricated CPA or extra spending authorization. Fit it inside existing daily/monthly authority and the selected observation period. Reaching it requires a decision, not automatic additional spending. If continuing an inconclusive test, record why the next bounded question merits the remaining authority.

`evidence_assessment` separates underexposure, maturation, usable evidence, inconclusive measurement and operational faults. Low delivery does not establish a loser. Zero qualified first-time buyers can reflect missing buyer history. Unmatched orders do not prove the ads produced those sales, and do not prove there were no sales. Use Meta attribution, Shopify outcomes and their coverage side by side.

The default scaling assessment uses two independent mature windows. A strategy can select `scale_windows: 1` only with a dated `repeatability_reference`, at least twice its ordinary qualified-order minimum, verified contribution and the remaining scaling checks. Neither route establishes causal incrementality. Choose the evidence design before looking for a favorable result.

## Test design

Choose distinct buying ideas, proof mechanisms and formats that can receive useful exposure. Do not require a fixed ad count. An initial one-ad plan needs a reason and a next creative question. At small budgets, simultaneous audience/format/offer splits can leave everything inconclusive. Preserve a useful control; challenger preparation need not await a verdict on the control.

Use `decision: TEST`, `test_kind: planned-challenger`, and `exposure_plan` with `question` and `comparison` for an additional planned exploration. Explain actual delivery allocation and what remains comparable. Ordinary ad delivery is not a randomized A/B test. Formal tests require their own available integration and adequately funded design. Never assume a forum's hours, CTR threshold, budget percentage or duplication trick applies universally.

## Diagnosis and timing

| Observation | Check first | Useful next action |
|---|---|---|
| No delivery | Actual account/review status, hierarchy, budget owner, audience, bids | Repair a verified fault; read back effective state |
| Clicks without arrivals | Redirects, page loading, event definitions and placement mix | Verify the destination and measurement |
| Arrivals without intent | Message/offer consistency, delivered price, trust, product explanation | Isolate one buying objection or destination problem |
| Checkout without paid orders | Payment, shipping, stock and checkout errors | Verify the operational cause; do not default to new targeting |
| Sparse purchases | Exposure, time-to-purchase, matching and buyer-history coverage | Continue bounded learning or test a justified alternative |
| Deteriorating purchases | Comparable contribution, frequency, auction/offer changes and creative mix | Diagnose before refreshing or excluding audiences |
| Repeatable positive contribution | Marginal performance, stock, fulfillment and remaining authority | Redistribute within authority or prepare a concrete increase |

Operational checks can happen before a purchase verdict. Performance reviews use actual delivery, exposure and lag. window_days is a target lookback; earlier complete clean dates can support a decision when exposure is informative. Compare equal periods and label uncertainty rather than claiming significance from repeated daily inspection. A strategy review asks whether evidence changed the buying hypothesis; a calendar date alone does not erase research. Dayparting needs adequate time-zone-specific purchase evidence. Learning Limited is context, not a reason to abandon Purchase or duplicate campaigns.

## Creative ownership and approval

Existing approved brand assets are reusable. Flag concrete material issues, not a blanket demand for new clinical proof. Use ordinary product benefits at the qualification level of the product page or packaging. Do not invent testimonials, discounts, urgency or guarantees. New agent-designed visuals/videos require the user's finished-preview approval, recorded against exact file ID, revision and bytes before build. Mark those Asset Selection entries `origin: agent`; never relabel them as brand assets. Ordinary factual caption changes within brand guidance do not require another creative approval.

Use `approve-creative` only after the user actually approves the completed preview. If revisions change, obtain approval for the changed design. Put drafts in the excluded/review area and file approved originals into their configured Discovery/Consideration/Purchase product folder. Record identity, revision and placement adaptations. Hashes identify the approved media; connector metadata omissions use the documented download fallback.

## Authority and operation

`management_authority` records the client's approved account-wide daily/monthly allocation and actual instruction reference. It is narrower than policy maxima. Under it, strategy, targeting, launch, pause, replacement and redistribution are routine operator work. Total increases and new agent-designed media need user decisions. Account-wide funding-control changes remain separate concrete spending decisions. Existing legacy runs retain their original authorization until explicitly migrated; do not infer consent from a schedule or research.

Always prepare, sign through the authorized operator, execute through the Meta gateway and verify readback. A transfer reduces and verifies the old allocation first. An uncertain write is reconciled before another attempt. Missing optional sources only defer affected conclusions. The calling agent owns recovery and setup, and requests user help only for a genuine missing decision/access step.

## Sources and use

- [Meta Performance 5](https://www.facebookblueprint.com/student/path/253157-performance-5): simplification, automation, creative variety, data quality and validation.
- [Meta creative diversification](https://www.facebookblueprint.com/student/path/253130-increase-campaign-performance-with-diversified-creative): concepts, motivators and formats.
- [Meta test design](https://www.facebookblueprint.com/student/path/219763-ab-test-conversion-brand-lift-course): distinguish exploratory delivery, A/B tests and lift studies.
- [Meta Conversions API](https://www.facebookblueprint.com/student/activity/609643-optimize-meta-conversions-api): coverage, matching, deduplication and freshness.
- [Meta Insights best practices](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights/best-practices): reporting revisions and bounded reads.
- [Shopify marketing reports](https://help.shopify.com/en/manual/reports-and-analytics/shopify-reports/report-types/default-reports/marketing-reports): attribution models and outcome definitions.
- [Jon Loomer on creative testing](https://pubcast.jonloomer.com/should-you-start-new-campaigns-with-creative-testing/): practitioner design considerations, not a mandatory test allocation.
- [Advertiser discussion of underexposed challengers](https://www.reddit.com/r/FacebookAds/comments/1wdm5aq/how_to_approach_testing_new_creatives_when_meta/): a diagnostic example, not a verified performance standard.

Meta Business Help and some API reference pages were rate-limited during review. Use current accessible official references and account readback for a recipe; do not present unavailable material as verified.
