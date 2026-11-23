# Skill contracts

The orchestrator loads one skill at a time from `src/meta_ads/registry.json`. Its `fields` and `types` are the machine-checked output contract. `record` permits a structured report, list or summary string. `object?` permits null for an unavailable source window. The worker supplies the selected skill with its saved predecessor records and applicable live source results. The shared policy defines permitted names, budget, creative stages, approvals and verification.

Manual submissions use the same live checks where the worker binds verified product, account, asset or scaling evidence. The protected Meta job records activation checks and account-wide budget validation using saved plugin evidence. The agent still owns research, interpretation and the next decision.

### Connected agent steps

Use `meta-ads next RUN_ID` in the workspace. For `collect`, look up each requested source with the existing authenticated plugin. Send the source response fields to `meta-ads collect RUN_ID FILE` using a private JSON file or stdin (`-`). Copy the returned step revision into the envelope. Collect an empty source packet with that revision for a planning step without a live read. The active step selects the permitted source inputs.

- **Shopify product.** Use the supplied Admin GraphQL query and variables with the link for the saved shop. Page to completion. Send `shopify_product` with `observed_at` and `pages`, where each page has the requested `after` cursor and the untouched GraphQL `data` object. For product research, include `storefront` with the exact assigned URL, successful HTTP status from a direct storefront read, and `observed_at`. Use the timestamp of the actual read.
- **Shopify orders.** Use the supplied query and exact window filter. Send `shopify_orders` keyed by window name. Each window has its `query` filter string, `observed_at`, and `pages` in the same shape as the product query. Fetch the specified fields only. The lifecycle aggregates paid and refunded orders into matching windows. An unavailable order window stays absent. Do not retain source order rows in the run or commit them to GitHub.
- **Drive media.** Start with the returned root and approved stages. Send `drive` with `observed_at` and `folders`, mapping each inspected folder ID to its file metadata list. Use the returned provider values for `id`, `name`, `parents`, `mimeType`, `version`, `md5Checksum`, and `size`. Follow pagination and approved folder ancestry. Read the selected originals with the connected Drive plugin, inspect the files, and save their original bytes to `FILE_ID.REVISION.bin` in the returned private `media_directory`. The lifecycle checks the file digest and inspects the media before accepting selection and validation. Refresh the approved inventory when the orchestrator requests it again.
- **Meta.** A `meta_worker` source is queried by the Meta worker during collection. For a `meta-worker` action run `meta-ads worker --run RUN_ID` through the configured GitHub Meta gateway, then inspect the resulting run state. A `dispatch` action refers to an existing approved operation and uses the protected operator.

When the next campaign-strategy task includes `existing_campaign`, use the supplied complete Shopify product read. The lifecycle compares the encrypted Meta readback and saved Shopify assignment, then registers a matching paused draft on the same run. Review that draft in the returned step. A completed review can keep the campaign paused and store specific findings. After those findings are resolved, resume the same review through `meta-ads resume RUN_ID`. A draft that passes creative review continues to separate activation checks.

Read `next` again after collecting. When it returns `submit`, use the selected skill and supplied `source_data`. Send `{"revision": REVISION, "result": RESULT}` through `meta-ads submit RUN_ID STEP FILE --connected`. Continue using `next` through the due steps. Keep run state, downloads and temporary evidence private. If a tool fails, distinguish a provider read error from missing approval or a real business prerequisite.

When the Drive connector omits version or checksum, use its revision-history tool for the candidate's current revision. Download the original through the connector's authenticated file reference and recheck the current revision after download. If it stayed the same, save the bytes as `FILE_ID.CURRENT_REVISION_ID.bin` in the returned media directory and include `headRevisionId` and the original size in the corresponding listing row. The lifecycle checks the byte count and hashes the original. Discover and verify candidates through the plugin before asking the user for help. If an asset is unavailable, consider the other eligible files and continue the skill's existing rework route when appropriate.

A result submitted by a read or planning skill has `status`, `summary`, `evidence`, `data`, and `blockers`. Evidence entries contain `source`, `ref`, and `observed_at` (ISO-8601 with offset). `data` objects include the keys from the registry and the skill. Save actual external IDs as strings and money as integer minor currency units. A success needs evidence references. Limited results need both evidence and limitations and only apply to analysis steps that can use partial findings. A blocked result explains the missing facts. A rework result names the permitted `data.retry_step`. Campaign Build, Optimization Execution, Scaling Approval and Scaling Execution write their own confirmed records through the orchestrator. The model's transport encodes `data` as JSON in the `data_json` string and the worker converts it.

Creative rework also carries `data.issue`, `data.asset_ids` and the proposed correction. Asset Selection can send a brief back to Creative Concept when current approved media supports a different angle. Creative Validation routes to the owner of the failed element. The worker passes the failed evidence to the next attempt. An identical recorded issue stops rather than running the same loop again.

Example with synthetic evidence:

```json
{
  "status": "limited",
  "summary": "Customer reviews were unavailable. Paid order behavior is visible.",
  "evidence": [{"source":"Shopify aggregate orders","ref":"product 123, 2026-10-01 to 2026-10-30","observed_at":"2026-11-17T10:00:00+05:30"}],
  "data": {"segments":[],"motivations":[],"objections":[],"hypotheses":["A two-step routine may simplify product selection."],"coverage":"Hypothesis only"},
  "blockers":["No verified review or support feedback source."]
}
```

### Creative build contract

Campaign Strategy sets `campaign_key`, `account_id`, `objective` and `budget` with `level` and `daily_minor`. The asset manifest is `assets[]` under Asset Selection. Each entry has `file_id`, `revision`, and `stage` from the live Drive inventory. Copywriting returns `variants[]` keyed by `name` with exact `primary_text`, `headline`, `description`, and `cta`.

Creative Validation returns these extra fields alongside its problem-specific evidence:

```text
data.plan =
  objective: "OUTCOME_SALES"
  budget_level: "campaign" | "adset"
  daily_minor: positive integer total (the existing budget for additions)
  adsets[]:
    name: "<campaign-key>-<audience>"
    daily_minor: positive integer for ad set funding, otherwise 0
    country_codes: list from the request
    placements: list from the placement names below
    existing_adset_id: null for new build, exact Meta string ID for existing parents; null for a new ad set under existing campaign funding
    ads[]:
      name: "<campaign-key>-<stage>-<concept>-<format>-v01"
      format: static | video | story | carousel | catalogue
      stage: discovery | consideration | purchase
      asset_id: exact Drive file ID
      poster_asset_id: exact approved poster Drive ID for video, otherwise null
      primary_text, headline, description: strings
      cta: SHOP_NOW | LEARN_MORE | ORDER_NOW
      destination: verified Shopify product HTTPS URL
      url_tags: URL query string with utm_source=meta, utm_medium=paid_social,
                utm_campaign=<campaign-key>, utm_content=<ad-name>
data.ads[] =
  name: the exact ad name
  approved_ad: identical copy of the ad object in the plan
  checks: claims, packaging, rights, destination, placement, copy, brand (each boolean)
  evidence: nonempty list of inspection references
```

Placement keys are `facebook_feed`, `instagram_feed`, `facebook_story`, `instagram_story`, `facebook_reels`, and `instagram_reels`. Stories use Story placements. This recipe supports JPEG/PNG and MP4 with a separate approved JPEG/PNG poster. Requested settings outside this recipe need a reviewed connector addition. The operator checks actual rendering in Meta at activation.

Ad sets can carry an `audience` object with `mode` (`broad`, `retargeting`, or `lookalike`) and `include` and `exclude` lists of numeric Meta audience ID strings. Match the exact saved Audience Planning scope by ad set name. The operator reads the account's saved audiences before proposals and writes and checks the targeting returned by Meta. Explicit inclusion uses manual audience controls and requires exact readback.

The connected agent uses the Drive filing map for new creative. TOFU uses Discovery, MOFU uses Consideration, and BOFU uses Purchase. It creates missing folders, files new artwork under the product, and verifies its Drive readback before selection.

### Campaign decisions

The lifecycle has four recorded outcomes, `COMPLETE`, `STOP`, `RECREATE`, and `SCALE`. Job status records where it is, such as ready, awaiting approval, monitoring, or blocked. A paused build can be complete while activation is waiting. Decisions inside Optimize are HOLD, FIX, TEST, REFRESH, PAUSE, RECREATE, SCALE, ALLOCATE, AUDIENCE and RESUME.

Business windows distinguish Meta delivery and attributed actions from Shopify exact last-visit Meta UTM matches. Growth uses the strategy's recorded repeatability design: two independent mature windows by default, or scale_windows=1 with a dated repeatability_reference and twice the usual qualified-order minimum. All selected windows must meet the verified CPA ceiling and show positive measured contribution after ad spend. Add verified `facts.economics` with the exact `product_id`, `variant_id` where applicable, `campaign`, `success_metric` and `source`. Each `windows` entry has `start`, `end`, and measured `product_cost_minor`, `shipping_fulfillment_minor` and `fees_minor` for that exact cohort. Use Shopify receipts less refunds and retained tax for fully attributable carts. For mixed carts, provide `verified_product_net_receipts_minor` for the whole cohort from an auditable allocation. Include losses from refunded orders and avoid subtracting refunds twice. Missing receipts or costs block scaling. This measures matched-order contribution, so it does not establish incrementality.

An early operational pause can use the worker's verified allocation or month-to-date spending breach, or a verified `facts.operational_issue` on the exact target. That record includes `kind`, `target_id`, `verified`, `reference`, and `observed_at`. The existing approval process still applies. Health problems while a live run is waiting are recorded as `live_campaign_attention` and shown in run status.

The review re-reads selected campaign, ad set and creative settings from Meta. The first configuration read establishes a baseline without changing the last known material-change timestamp; state historical comparability limits. A subsequent changed configuration invalidates windows starting on or before the time it was detected. The next clean window starts on the next full account-local day. Configured runs require a baseline for performance decisions and recheck it before a scale proposal and before its first write. Snapshot comparison detects settings changes that are present at readback. An edit reverted between reviews may leave no difference.

When the brand explicitly sets `blocked_pause_after_hours`, the worker prepares a pause proposal if an unresolved blocked campaign is still active after that period and no proposal is pending. The existing approval and verified execution process still applies. Without this policy option, the worker logs attention for an active blocked run.

On a scheduled strategy refresh, configured runs return a `cycle_action` of `continue` or `recreate`. The worker provides `source_data.strategy_history` for comparison.


### GitHub Meta jobs

`meta-ads gateway-setup --repo OWNER/REPO` configures encrypted transport once. Connected `worker`, `execute`, `operator-check` and `reconcile` use the repository's existing Meta secret. Job inputs and results are encrypted; durable checkpoints are saved before each provider mutation. No Shopify or Drive token is required by this runner. The agent supplies product/order evidence and verified media through its plugins. A timed-out dispatch is resumable; an uncertain write must be reconciled before retrying. A conflicting local revision cannot be overwritten by a returning job.

### User-facing updates

Every committed step refreshes `logs/activity.md` and `logs/<brand>/<campaign>.md`. Use the CLI's `update` fields to report completed work, the current task, next action, timing and responsible party. Technical IDs remain available for diagnosis; they are not the main user-facing status. Ask for a real missing business decision or exact required approval, and preserve what was already authorized. Continue independent work while awaiting that answer.


### AGI launch and spend ledger

A paused build or approved plan does not start AGI spending. Before activation, capture exact campaign Insights for the account-local launch day and month as a baseline, persist it before mutation, and preserve it across ambiguous-write recovery. On verified activation, record `launch_verified_at`. Record the first observed delivery separately as a date when only daily Insights are available. Use absolute campaign totals less the saved pre-start baseline, not account `amount_spent`, to measure AGI usage. Repeated snapshots replace observations instead of adding them twice. A replacement campaign retains the preceding campaign's ledger; a new month retains total spend while starting a new monthly counter. Never turn an unknown legacy baseline into zero.

The readable log shows start, first delivery, daily budget, spend since start, month spend, observation date, next review and responsible party. Meta's account spending counter, account limit and account-wide funding checks remain separate. Earlier account spending cannot be charged to a new AGI run. A temporary reporting read failure is an agent-owned reconciliation task; preserve unknown/stale evidence and existing authorized execution rather than inventing a number or asking the owner to calculate it.

### Standing authority and completed creative approval

Record the actual user instruction with `meta-ads management-authority RUN_ID --daily-minor N --monthly-minor N --reference "ACTUAL USER INSTRUCTION"`. This changes private run authority, not Meta budgets; policy maxima remain separate. Existing proposals must be resolved first. Under standing authority routine operator signing is automatic; legacy runs retain exact owner actions. Use the current user's actual approval for total increases and account-wide funding-control changes.

Mark selected newly agent-designed media `origin: agent`. After showing the finished preview and receiving approval, record each original with `meta-ads approve-creative RUN_ID --file-id FILE --revision REV --md5 HASH --owner OWNER --reference "ACTUAL PREVIEW APPROVAL"`. The signed receipt is checked against bytes/revision at proposal and build. Existing brand artwork can use `origin: brand` (legacy default). Changed generated media needs a fresh decision.

### Strategy and adaptive decisions

Version-2 management strategies supply the decision_contract documented in [the decision method](decision-method.md). `criteria` keeps window_days, lag_days, minimum_matched_orders, maximum_cpa_minor and recheck_hours; optional fields are learning_spend_minor, scale_windows and repeatability_reference. A learning allowance fits the current approved allocation and is never an extra authorization or fabricated CPA. Missing costs permit bounded learning, not unsupported profit claims.

`TEST` with `test_kind: planned-challenger` requires `exposure_plan: {question, comparison}`. Ordinary performance verdicts still require usable evidence. `ALLOCATE` requires changes[] with target_id/from_daily_minor/to_daily_minor for distinct active funding owners in enrolled campaigns for the same client/account, using campaign or ad-set funding at its actual level; total cannot increase and decreases execute first. `AUDIENCE` requires audience: {name, event, retention_days, product_url}; event is PageView/ViewContent/AddToCart/InitiateCheckout/Purchase, name stays in the assigned product namespace, retention is 1..180 days and URL matches the assigned product. Creation does not establish delivery eligibility.

A dated strategy review alone does not restart research. To reconsider it explicitly, submit a decision with strategy_reconsideration: {required: true, reason: "changed evidence", reference: "source"}. Keep unchanged research when possible and save the replacement rationale.

### Additional build recipes

For a Feed carousel add cards[] to the ad, each with asset_id/headline/description/destination. Use 2..10 approved image cards, same assigned destination and stage, first card as asset_id, null poster, exact saved card order, passing QA for the entire carousel and a matching carousel name/format. Include every card original in Asset Selection.

For a verified existing catalogue add plan.catalogue: {catalogue_id, product_set_id, retailer_ids}. All ads in that build use format catalogue. Save facts.catalogue with these same values, exact assigned product_id/variant_id and source. The provider verifies product-set membership, item URLs/currency/availability and assigned Purchase source before proposal, build and activation. This recipe does not provision a catalogue, change the feed or allow unassigned products. A selected approved original remains the visual-review reference; final rendered catalogue previews require inspection.

`next` returns capabilities, evidence_assessment and update with reason/due_condition/data_freshness. An approved operation returns dispatch; an uncertain pending write returns reconcile with pending_operations. Structured status and readable logs come from the same committed records.

### Version-2 knowledge handoffs

After a new strategy is saved with contract_version 2, Campaign Strategy, Creative Concept and Creative Validation include its exact strategy_id. Each creative concept has name (the exact final ad name), message, hypothesis, proof, format and stage; portfolio_rationale explains the number of concepts and how useful exposure is expected. Creative Validation maps each ad with concept_name, exact matching ad name/format/stage and approved_ad. This prevents a stale or unrelated brief from silently becoming the executed strategy; it does not mechanically certify creative quality.

New Asset Selection submissions on version-2 management runs identify origin: brand or agent for every selected original. Historical brand-approved selections remain compatible. Signed creative approvals can be reused across runs for the same brand/account and unchanged bytes/revision; changed designs and changed owner whitelists are rechecked.

window_days is the target lookback. Before that much post-delivery history exists, collection uses available complete clean dates after the relevant change and first observed delivery, with an equally long previous comparison. Exposure and reporting lag still determine usability. A new creative portfolio starts a fresh aggregate comparison while object_changes preserves the identity/history of unaffected controls. Saved dates do not imply a statistically conclusive randomized result.

`meta-ads capabilities RUN_ID` performs optional read-only audience/catalogue discovery through the existing gateway. Inventory access does not prove write permissions, audience delivery or catalogue eligibility. Catalogue IDs, product mappings and product-set filters come from connected discovery; the client is not asked to fill technical ID forms. Limited optional discovery never blocks ordinary Sales preparation.

Replacement builds remain paused while the predecessor continues. Their proposed funding models the replacement rather than simultaneous funding. At release the executor checkpoints and verifies the predecessor pause before activating the replacement. Partial handovers remain in the same journal; do not reactivate the old campaign while the replacement status is uncertain.

`meta-ads guard RUN_ID` uses only Meta and the saved standing monthly allocation. At a verified account-month ceiling it prepares, signs, journals and reads back a pause of the enrolled campaign. It never increases funding. It requires a running host/job, and its reporting/polling delay is not a guaranteed hard cap. Existing unresolved proposals must be reconciled before a separate guard operation.

### Pause, continue management and resume

A performance or budget pause under standing authority keeps management scheduled; it does not silently hand the lifecycle back to the user. The monthly guard schedules the next allocation review at the start of the next account-local month. The agent reviews current conditions before choosing whether to resume; a calendar wake itself is not an activation.

Use optimization decision RESUME for a paused campaign/ad set/ad in the enrolled hierarchy. The recipe verifies Purchase-source/product/variant evidence, recorded operational issues, destination reachability, current creative destinations, parent status and fresh account exposure. It pins current configuration and uses the normal signed journal/readback route. Resumption preserves the original AGI launch/spend baseline and begins a new comparison window. `meta-ads resume` is the separate command for reopening blocked lifecycle state; it does not activate Meta objects.

If the user explicitly stops management, set stop_management: true on the PAUSE decision. That terminal stop is not automatically reversed. Ordinary reductions and reallocations can use ALLOCATE with one or more funding owners; no aggregate increase is allowed. Fresh execution checks enforce standing monthly authority as well as daily allocation and broader policy limits.


Product-page audience scope is limited to PageView/ViewContent. A product URL is not a verified Purchase/checkout-event identifier. For a store-wide purchaser exclusion or store-wide intent cohort, set scope: all-store explicitly; the rule then filters the selected event without a product URL. Its receipt records the broader scope. Product-specific lower-funnel event filtering requires a separately verified mapping and is not silently approximated with a product-page URL.
