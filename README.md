# Meta Ads management

Say **Start manage ads**. The agent uses the saved product assignments and continues the same lifecycle. A specific request narrows the task.

## Open these first

- [Activity and next actions](logs/activity.md) - generated automatically after saved work.
- [Skills by lifecycle](.agents/skills/meta-ads/references/skill-map.md).
- [Operating knowledge](.agents/skills/meta-ads/references/operating-knowledge.md).

## Who does what

| Component | Responsibility |
|---|---|
| Agent and skills | Research, strategy, funnel, audience, creative, diagnosis, decisions, user updates |
| Shopify and Drive plugins | Product/order evidence and approved or newly produced creative files |
| GitHub Meta jobs | Fresh Meta reads, exact authorized writes, recovery checkpoints and verified readback |
| Scheduled Meta snapshot | Collect delivery history while the agent is closed |
| Scheduled connected agent | Import that history and continue due work when an agent session is available |

A scheduled snapshot records evidence; it does not invent a new strategy. Closing the agent does not stop Meta delivery. Plugin research and creative work resume when the connected agent runs. A schedule is not a promise that a closed desktop can execute plugin work.

## Lifecycle

Research -> Strategy Development -> Campaign Strategy -> Funnel and Audience Planning -> Creative -> Paused Build -> Authorized Launch -> Monitor -> Diagnose -> Hold, Fix, Test or Recreate -> Scale.

Each cycle starts with a strategy. Subsequent cycles read previous hypotheses, results and failed approaches. TOFU, MOFU and BOFU describe message jobs; separate campaigns require a useful audience, budget or measurement reason. Existing `agi-` campaigns are inspected and enrolled before deciding to keep, improve or replace them. Other campaigns are left alone; their spend still counts toward account limits.

## Folder structure

```text
.agents/skills/         One standard folder per skill, with knowledge references
src/meta_ads/          Lifecycle, Meta execution and logging code
config/examples/       Generic setup examples safe to share
config/brands/         Private saved brand policy and product assignments
logs/activity.md       Human-readable overview
logs/<brand>/          Campaign decisions, results and full timeline
data/                 Private database, evidence, media and job receipts
.github/workflows/     Meta execution and scheduled snapshots
tests/                Regression checks
```

Private configuration, logs, media, credentials and job contents are ignored by Git. GitHub job assets are encrypted. Copying the repository supplies the system; each user fills their own brand information and connections. Local private history needs its own backup and is not shared by forking the code.

## Setup and commands

Install once from the repository root: `python -m pip install -e .`.

Ask the agent to set up a brand by name and website. It discovers technical IDs through connected sources and asks only for missing business choices. `meta-ads init "BRAND NAME"` creates blank private setup files. Put assigned product filenames in `assignments.json` beside `brand.json`; one `product.json` is the default. The [examples](config/examples/brand-profile.json) explain the saved structure.

Use the existing GitHub account and Meta secret: `meta-ads gateway-setup --repo OWNER/REPOSITORY`. This configures encrypted job transport and approval signing. Shopify and Drive tokens are not needed by GitHub. The one-time setup uses authenticated GitHub CLI and OpenSSL. The Meta account secret is `META_CATCHUP_ACCOUNT_ID`; the existing `META_ACCESS_TOKEN` can supply Meta reads and writes subject to its actual permissions.

```powershell
meta-ads manage --connected
meta-ads next RUN_ID
meta-ads status RUN_ID
meta-ads log RUN_ID
meta-ads operator-check RUN_ID
```

`next` returns the exact skill, evidence needed and action. `worker --run RUN_ID`, `execute RUN_ID` and `reconcile` use GitHub automatically when configured. Run IDs stay in technical records; user reports use product and campaign names.

## Decisions and authorization

The agent continues research, supported preparation and diagnosis without repeatedly asking the same question. Missing optional research or a warning does not stop unrelated work. It asks for genuine missing help, higher total spending and finished new agent-designed media. With saved standing management allocation it handles routine launches, strategy and redistribution without another owner question. Legacy runs retain their original policy until migrated, and existing approvals are preserved. Builds are paused. Only a verified receipt supports a claim that Meta changed.

A failed or uncertain write is reconciled before another attempt. Signed requests are serialized in GitHub, checkpointed before each provider mutation, and imported only into the matching local revision. Resume a timed-out request rather than starting a duplicate. A concurrent local edit requires receipt reconciliation.

Read the [policy](.agents/skills/meta-ads/references/policy.md), [data contracts](.agents/skills/meta-ads/references/contracts.md) and [launch checks](.agents/skills/campaign-launch/references/checks.md) for exact behavior. Supported builds cover website Purchase, image/video, permitted Feed/Stories/Reels placements, and existing Custom Audience inclusion/exclusion. Additional recipes cover Feed carousel, additions to campaign-funded campaigns, verified existing-catalogue Sales, product-page and explicitly all-store event audience creation and within-campaign ad-set budget transfers. Catalogue provisioning, customer-list uploads, earlier-event optimization and formal experiments remain separate capabilities. The returned inventory distinguishes implemented recipes from unverified account access.

## User updates

Report **Done**, **Now**, **Next and when**, and **Your action** only when needed. Include the readable log link at meaningful milestones. State the specific business effect and next recovery action when something fails. A routine technical recovery belongs to the agent. Never call work successful before checking the saved result, or promise profitable advertising from system readiness alone.

## Verification

Run `python -m unittest discover -s tests -v`. Simulations use temporary state and a fake Meta API. Live verification must be labeled separately and does not authorize activation.

Launch checks collect available Meta and public checkout evidence automatically. An exhausted account limit is presented as a concrete, bounded account-wide change within the launch proposal, requiring explicit owner approval before execution. Store-wide Purchase activity and checkout navigation are recorded with their limits; no automatic paid test order is placed.

AGI accounting starts on verified campaign activation. Logs separate that timestamp from the first observed delivery date, deduct a saved pre-start campaign baseline, and show campaign spend since start and this month. Earlier account spending stays in a separate Meta account-control section. Catch-up snapshots replace absolute observations, so retries and missed-day imports do not double-count spend.

## Purchasing decisions and management authority

Read [the shared decision method](.agents/skills/meta-ads/references/decision-method.md) and the selected skill guide. The local runner includes both in its prompt. Skills connect buying situation, objection, offer, proof and test conditions to the actual ad. Evidence states distinguish underexposure, reporting lag, usable results, inconclusive measurement and operational faults. A low-spend challenger is not automatically a loser; a daily check is not a requirement to edit. Dated research is reconsidered when facts change, not erased on a calendar tick.

The client's approved operating allocation is narrower than policy maxima. Record a real standing instruction with `meta-ads management-authority RUN_ID --daily-minor N --monthly-minor N --reference "USER INSTRUCTION"`. This updates private authority and signs routine proposals through the existing operator; it makes no Meta budget change. Total increases still require their exact owner decision. Existing generated assets require a finished-preview decision using `approve-creative`, bound to exact file/revision/hash. Mark them `origin: agent` in Asset Selection.

Logs show purchases, matched net receipts, contribution where verified, attribution coverage, the buying question and next decision condition. Unknown economics remain unknown. Meta attributed outcomes, Shopify matched outcomes and incremental business impact are distinct. Current receipts and spending baselines survive migration; live campaigns are not rebuilt by a code update.

Logs also show the current strategy's learning allowance, verified exposure, remaining amount and earliest clean purchase-review date. Spending on immature reporting dates still counts against a saved strategy ledger baseline. Reaching the allowance brings the agent's risk review forward; it can pause verified exposure through the existing authorized Meta route without declaring the ad unsuccessful. A reporting-window fallback is labeled as a lower bound. Missing counters stay unknown. This is an agent decision trigger, not a Meta hard cap or a new client budget form.

Schedules retain their review anchor after missed runs. GitHub collects Meta history while the connected agent is unavailable; strategy/creative and Shopify/Drive work resume with that agent. With standing authority, `meta-ads guard RUN_ID` and ordinary Meta health jobs can pause the enrolled campaign when verified account-month spend reaches its approved monthly allocation. This uses the existing signed Meta gateway, recovery journal and exact readback; no Shopify/Drive tokens or strategy work is needed. A host scheduler can call this command while the desktop app is closed, provided that host is running; GitHub snapshots alone remain read-only. Reporting/cron delays mean a polling guard is not an exact hard spending cap.


Use `meta-ads capabilities RUN_ID` when a strategy needs actual audience/catalogue discovery. These are optional reads through the existing connection, and limitations do not disable ordinary Sales. Routine performance pauses keep management scheduled under standing authority. RESUME is an explicit optimization decision with fresh delivery/budget checks, not an automatic reaction to a calendar date. A user stop of management remains terminal. The monthly guard schedules a new-month review, while preserving launch history and spending baselines.
