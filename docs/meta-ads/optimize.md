# Meta Ads testing, optimization, and scaling

Use the campaign plan, actual Meta and Shopify evidence, and the latest changes. The [runbook](runbook.md#review-and-scale) shows how to collect a campaign review. Apply the saved result definition, attribution basis, targets, and limits.

## Test

Choose one question and primary metric before launch. Record the baseline, smallest useful effect, budget, sample or duration, conversion lag, and stopping rule. Specify what a win, loss, or inconclusive result would change. Keep other decision-relevant settings comparable. Use Meta Experiments or another randomized design when the decision requires a causal comparison and the volume supports it. Treat ordinary ad delivery as directional because Meta may deliver each variant to different people or give it different spend. If a split would leave each variant too little evidence, narrow the question, compare fewer options, or plan a directional first run.

Use an existing ad set when a creative can answer the question under its current settings. Use a separate test when it needs controlled delivery, different eligibility or its own budget. If copying an object helps set up a test, identify the changed variable, relevant settings to carry forward and how the agent will judge the result. After the test, keep a supported winner, retire a confirmed loser when warranted, and record what would resolve an inconclusive result.

## Diagnose

1. Check spend and delivery against the plan. Review the latest changes, stock, offer, destination, and tracking before interpreting a swing.
2. Compare like-for-like windows and allow for delayed conversions. Use verified, campaign-matched Shopify orders to judge purchase cost and use Meta delivery data to explain it. Keep the two attribution views separate. Mark unavailable evidence and state whether it blocks the decision.
3. Trace the funnel. If clicks hold while page views fall, check load and tracking. If page views hold while carts fall, check the offer or page. If carts hold while orders fall, check shipping and checkout. If Meta results fall while Shopify orders hold, investigate measurement. Treat a metric pattern as a lead and verify the suspected cause before acting.

## Decide what to do

| Decision | Evidence that supports it |
|---|---|
| Hold or continue | Results meet the target, the current swing fits normal variation, or the test has time and budget left to collect mature evidence. |
| Investigate or fix | Reconcile conflicting measurement before judging performance. Fix a confirmed blocker such as broken checkout or invalid offer at the smallest affected scope. |
| Test or refresh creative | Name the likely bottleneck and test a new concept when the existing one appears exhausted. Rising frequency alongside falling response and worsening purchase cost can support that hypothesis when the page and offer are stable. If the concept still converts but the opening underperforms, test a new hook or format first. |
| Pause | A verified blocker makes the ad unusable, or it hits the plan's stopping condition after allowing for conversion lag. At the test limit, a result can remain inconclusive. Record that difference and use a reversible pause at the smallest useful scope. |
| Scale | Mature, comparable results meet the saved purchase cost or value target at the planned minimum volume. Tracking, fulfilment capacity, other recent changes, and budget headroom support an increase. Use the saved plan's scale step and review interval. Compare the additional purchase cost after the change and apply the saved reversal condition if it is met. |

If orders fall after a recorded budget increase and the post-change period has matured, inspect the saved reversal target. The review flags a possible reversal for operator review when purchase efficiency misses that target and order volume is too low for a normal proposal. For zero orders on a cost-per-order plan, it flags the drop once spend reaches the reversal target. Check tracking, delivery, stock, and checkout before drawing a conclusion.

## Save the decision and learning

Record facts, likely explanations, missing evidence, and the next review condition. For a proposed change, name the exact object, baseline, action, expected outcome, and reversal condition. Use the runbook for operator handoff and post-change verification.

Add a concise learning to the [campaign notes](campaign-template.md) after each completed test or material decision. Include the buyer, offer, angle or destination tested, source and dates, result volume, and where the conclusion applies. Mark early signals as provisional. Carry supported lessons into the next plan and update them when stronger evidence changes the conclusion.

[Meta Performance 5](https://www.facebookblueprint.com/student/path/253157-performance-5) · [Meta experiments](https://developers.facebook.com/docs/graph-api/reference/user/ad_studies/)
