# Meta Ads runbook

Use Python 3.11 or newer from the repository root. On Windows, install Python's `tzdata` package if the account time zone is unavailable.

## Plan and build

Start from the [example plan](examples/campaign-plan.json) and complete the [12 decisions](campaign-template.md). Follow the [project naming convention](brand-rules.md#naming) and use the plan ID for filenames in `campaigns/` and `evidence/`. Save the plan in the scheduled campaign folder once the Meta target ID and review criteria are ready. Use Meta IDs as strings, budgets and spend as integer account minor units, and calendar dates in the account time zone. Set `minor_per_unit` for the account currency.

Before a build, use the reviewed files and final copy from the [creative workflow](creative.md).

Use the monthly maximum and daily range from the [ad brief](brand-rules.md). If the team changes a limit, update the brief before launch or a live budget change. Record the daily amounts and limits in the campaign plan. The example plan uses fictional amounts. For an INR account, write rupee amounts in paise in the plan.

Prefix campaign, ad set, ad, and saved audience names with `agi-`. The paused build validates ad names and checks the selected custom audiences in Meta before creation. Use a verified `agi-` campaign or ad set for review. A saved offline snapshot needs the exact Meta name in `target_name`. Live reviews verify the reporting scope before pulling performance data. [Meta audience fields](https://developers.facebook.com/docs/marketing-api/reference/custom-audience/)

For previously saved plans, add decision details and evidence, the reporting basis, and any missing pixel-backed build fields before validation. Recreate action previews from the updated plan.

```text
python automation/meta_ads.py validate docs/meta-ads/examples/campaign-plan.json
python automation/meta_ads.py build docs/meta-ads/examples/campaign-plan.json
```

A build without `--confirm` prints all proposed operations without contacting Meta. The build supports one campaign, its ad sets, and existing single-link image creatives. For pixel-backed ads, set `build.conversion_domain` and each ad set's `settings.attribution_spec`. For ad-set budgets, the preview includes `is_adset_budget_sharing_enabled`, which defaults to `false`. Check objective, targeting, assets, destination, and budget. The operator runs an authorized paused build with `build <plan> --confirm <approval_id> --state <private-state.json>`. Reuse the **same state file** on every run. It records confirmed IDs and uncertain operations.

If a build times out, the record identifies the uncertain object by its planned name and stage. Confirm in Ads Manager whether it exists and belongs to the expected parent. If it exists, reconcile its ID in the execution record. If Meta confirms it never existed, clear only that pending record before resuming. A stale lock should be cleared only after confirming the previous process is stopped and checking the saved progress.

Use `previews <plan> --state <private-state.json>` to get Meta's links, exact IDs, and creative versions. If a link is unavailable, review the ad in Ads Manager. Save a QA JSON file with the output's `build_id`, `object_ids`, and `creative_versions`, evidence in the `placement_previews`, `destination`, and `tracking` fields, and `passed: true` when verified. Under `skincare`, key each entry by its creative ID and record `passed: true` plus evidence for the four checks in the [skincare playbook](skincare.md). The operator reviews the actual evidence and previews. Keep the build plan fixed until launch. A change to the Meta creative fields requires a fresh preview and review.

```text
python automation/meta_ads.py launch <plan> <qa.json> --state <private-state.json>
python automation/meta_ads.py launch <plan> <qa.json> --state <private-state.json> --confirm <approval_id>
```

The first command previews activation. The second verifies the saved objects, settings, and brand budget, then activates the campaign after its ads and ad sets. Use the returned effective status to check delivery. After launch, save the actual target ID in the plan under `campaigns/` and run its first read-only review.

### Video and Story operator handoff

Use Ads Manager for video or Story creatives outside the CLI's existing single-link image path. Give the operator the saved campaign and ad set settings, asset and usage rights, copy, CTA, destination, placement, and test hypothesis. For Stories, supply a vertical asset and check text and controls in the actual placement preview. Use the same `agi-` naming, approved budgets, format rules, product QA, and tracking checks as the image path.

The authorized operator saves the campaign, ad set, and ads as drafts or paused objects, confirms the asset and destination in each placement preview, and checks the exact account and budget before activation. Record the returned IDs and the approved creative version in the campaign notes. Save the verified reporting target after launch. For a mixed-format build, the operator uses this path for the whole build to keep placement checks and approval together.

## Account budget

Fill in the three amounts in [brand-rules.md](brand-rules.md). Enter rupees there, for example `₹12,000`. Launch and live budget changes check the current limits and read spend so far this month from Meta. The check includes the whole account for budgeting.

Put an `account_budget` object in the launch QA file and the daily evidence file. Give it `as_of` for today in the account time zone and these amounts in paise.

| Field | What to enter |
|---|---|
| `other_daily_min_minor` | Lowest combined daily budget for the rest of the account during the proposed run |
| `other_daily_max_minor` | Highest combined daily budget for the rest of the account during the proposed run |
| `other_remaining_minor` | Money still planned for the rest of the account this month |

Exclude the campaign or ad set whose budget is being proposed from these three amounts. Include every other campaign or ad set that will spend, including older ads. The operator checks the figures before confirming. The monthly check reserves the proposed daily amount through the end of the current month, including today. A successful check validates the planned amounts. Use a hard limit in Meta when the account needs an enforced delivery cap.

## Review and scale

```text
python automation/meta_ads.py review docs/meta-ads/examples/campaign-plan.json docs/meta-ads/examples/snapshot.json --output review.json
python automation/meta_ads.py live-review docs/meta-ads/campaigns/<plan>.json --evidence <business-evidence.json> --output review.json
```

For an on-demand agent review, give the agent the request, campaign plan, current evidence and latest change receipt. Use `live-review` when the configured read connection and target are available. Use `review` with a dated offline snapshot for rehearsal. Inspect the report with the [Meta Ads skill](../../.agents/skills/meta-ads/SKILL.md) and record the decision, evidence and next review. Ask the agent to prepare an exact preview for the operator if a change is justified.

The live review reads spend and delivery from Meta. The business evidence supplies independently checked results, tracking health, and available capacity. Give it the same `account_id`, `target`, `currency`, and `as_of` as the live run plus a `source` reference and `business_source`. The plan's `review.result_basis` identifies the `campaign_key`, `attribution_model`, `result_definition`, and account `time_zone`. Apply those filters to the actual export and include the same basis in the evidence. Include `current` and `previous` with the exact dates, `results`, and `value_minor` when needed. Include `tracking_verified`, `capacity_verified`, and the latest applied budget receipt as `last_budget_change` when one exists. The example snapshot shows the same period layout and uses `evidence_source` for the report reference. For cost per result the targets are in minor units. For value per spend use a ratio. A result count alone cannot authorize an increase.

The review can hold, request investigation, or propose a scale or reversal. A live budget proposal requires a passing account budget check. Copy the report's `proposal` object to a separate JSON file and reuse the same plan and snapshot for approval. The live report includes the snapshot in its output.

```text
python automation/meta_ads.py apply-budget <plan> <snapshot> <proposal>
python automation/meta_ads.py apply-budget <plan> <snapshot> <proposal> --confirm <approval_id> --state <private-state.json>
```

The first command previews the change. The second requires an authorized operator and verifies the current budget in Meta. Keep one persistent execution file per ad account outside Git. A new change requires the latest applied receipt in the snapshot. A timed-out change is reconciled by reading the budget back. When the result still cannot be confirmed, inspect it in Ads Manager before further execution. The cap controls the configured daily budget, not actual delivery spend. Set any required hard spending limit in Meta before launch.

## Pause an individual ad

Pause instead of deleting campaign objects. Keep the history available for future reviews.

```text
python automation/meta_ads.py pause-ad <plan> <ad-id> <agi-ad-name> --reason "Evidence supporting the pause"
python automation/meta_ads.py pause-ad <plan> <ad-id> <agi-ad-name> --reason "Evidence supporting the pause" --confirm <approval-id> --state <private-state.json>
```

Review the exact ad and evidence before confirming. The confirmed command verifies the ad and its parents in the saved account and campaign scope, pauses the ad, and reads its status back from Meta. If an attempted pause is unconfirmed, verify the ad in Ads Manager. For creative additions to an existing ad set, provide the destination ad set, asset and copy, and test design for the operator in Ads Manager. Record the returned ad ID and verify the new ad before reading performance.

## Scheduled review

The [GitHub workflow](../../.github/workflows/meta-ads-review.yml) is configured for 10:17 India time daily on the default branch and can run on demand after deployment. It posts each decision in the run summary and uploads the reports for 14 days. The agent uses the report and the Meta Ads skill to propose the next test or change. An operator confirms changes separately.

| Surface | Credential |
|---|---|
| Scheduled or local Marketing API review | `META_READ_TOKEN` with read-only ad account access, plus `META_AD_ACCOUNT_ID` and `META_API_VERSION` |
| Authorized operator execution | `META_WRITE_TOKEN`, account ID, and API version in a separate operator environment |
| [Manual MCP connection check](../../.github/workflows/check-meta-mcp.yml) | `META_ACCESS_TOKEN` for the MCP check |

Keep the write credential and private execution state out of the agent and scheduled environments. The confirmation ID binds the preview to exact inputs. Operator access and user authorization establish who can execute it. The script verifies that required evidence is recorded, and the operator verifies its substance.

Committed evidence files, if used, belong in `docs/meta-ads/evidence/<plan>.json` and should contain only aggregate data. The runner checks dates, account, currency, and target. If evidence is missing or dated before the review, the job still reports Meta spend and requests fresh evidence. A budget proposal requires matched evidence. Prepare the evidence JSON from a Shopify export and commit it for the scheduled job or pass it to the local command.

To prepare the first scheduled review, save a real plan after its target ID is verified, provide the matching aggregate Shopify evidence for the review date, and configure the read credential and repository variables in the table above. Once the workflow is on the default branch, run it on demand and check the summary and uploaded report. A missing plan produces a skip notice. Missing or stale Shopify evidence limits the report to Meta results and the evidence required for a decision.

[Meta Insights API](https://developers.facebook.com/docs/graph-api/reference/adaccount/insights) · [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
