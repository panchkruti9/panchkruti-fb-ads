# Meta Ads campaign plan

Save campaign plans in `campaigns/` using the [runbook format](runbook.md). Use the [strategy playbook](strategy.md) to make these decisions and link the evidence that supports them.

| Decision | Record in the plan |
|---|---|
| Campaign objectives | Business outcome, Meta objective, event, primary metric, and target. |
| Audience research | Buyer, motivation, barrier, and supporting evidence. |
| Customer journey and funnel | Message, proof, and desired action at each relevant stage. |
| Campaign architecture | The job of each campaign and where budgets can be shared. |
| Audience targeting | Geography, controls, and justified exclusions. |
| Ad set structure | Distinct delivery or testing needs and how settings are grouped. |
| Creative and copy | Distinct concepts and destination. Link the [creative brief](creative-template.md) for each ad version to record its source, claims, and files. |
| Budget allocation | Use the monthly maximum and daily range in the [ad brief](brand-rules.md). Record the proposed split, daily amounts, and spending limits. |
| Testing | Hypothesis, comparison, fixed settings, metric, and decision conditions. |
| Retargeting | Eligibility, message, size, and reassessment condition if deferred. |
| Optimization and scaling | Minimum evidence, scale step, cooldown, and reversal condition. |
| Tracking and reporting | Event verification, Meta attribution settings, reporting dates and lag, campaign-specific business filter, result definition, business attribution model, and account time zone. |

Mark each decision `decided`, `deferred`, or `open`. Record a reason for each. For `deferred`, state when to revisit it. Each `decided` entry needs the named fields in `details` and an `evidence` list pointing to source records or explicitly approved decisions. Use the [example plan](examples/campaign-plan.json) for field names. Keep a decision open if its evidence is missing. The validator checks that those records are referenced. Confirm the underlying facts when planning and in preflight.

Save review decisions and test learnings beside the plan in `campaigns/<plan-id>-notes.md`. Use the [review format](optimize.md#save-the-decision-and-learning) and link the notes from the next plan or test that relies on them. Keep campaign notes and evidence free of customer identifiers.
