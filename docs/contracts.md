# Skill contracts

The orchestrator loads one skill at a time from `ads/registry.json`. Its `fields` and `types` are the machine-checked output contract. `record` permits a structured report, list or summary string. `object?` permits null for an unavailable source window. The worker supplies the selected skill with its saved predecessor records and applicable live source results. The shared policy defines permitted names, budget, creative stages, approvals and verification.

Manual submissions use the same live checks where the worker binds verified product, account, asset or scaling evidence. The worker alone records activation checks and account-wide budget validation.

### Connected agent steps

Use `python -m ads next RUN_ID` in the workspace. For `collect`, look up each requested source with the existing authenticated plugin. Send the source response fields to `python -m ads collect RUN_ID FILE` using a private JSON file or stdin (`-`). Copy the returned step revision into the envelope. Collect an empty source packet with that revision for a planning step without a live read. The active step selects the permitted source inputs.

- **Shopify product.** Use the supplied Admin GraphQL query and variables with the link for the saved shop. Page to completion. Send `shopify_product` with `observed_at` and `pages`, where each page has the requested `after` cursor and the untouched GraphQL `data` object. For product research, include `storefront` with the exact assigned URL, successful HTTP status from a direct storefront read, and `observed_at`. Use the timestamp of the actual read.
- **Shopify orders.** Use the supplied query and exact window filter. Send `shopify_orders` keyed by window name. Each window has its `query` filter string, `observed_at`, and `pages` in the same shape as the product query. Fetch the specified fields only. The lifecycle aggregates paid and refunded orders into matching windows. An unavailable order window stays absent. Do not retain source order rows in the run or commit them to GitHub.
- **Drive media.** Start with the returned root and approved stages. Send `drive` with `observed_at` and `folders`, mapping each inspected folder ID to its file metadata list. Use the returned provider values for `id`, `name`, `parents`, `mimeType`, `version`, `md5Checksum`, and `size`. Follow pagination and approved folder ancestry. Read the selected originals with the connected Drive plugin, inspect the files, and save their original bytes to `FILE_ID.REVISION.bin` in the returned private `media_directory`. The lifecycle checks the file digest and inspects the media before accepting selection and validation. Refresh the approved inventory when the orchestrator requests it again.
- **Meta.** A `meta_worker` source is queried by the Meta worker during collection. For a `meta-worker` action run `python -m ads worker --run RUN_ID` on the configured Meta host, then inspect the resulting run state. A `dispatch` action refers to an existing approved operation and uses the protected operator.

Read `next` again after collecting. When it returns `submit`, use the selected skill and supplied `source_data`. Send `{"revision": REVISION, "result": RESULT}` through `python -m ads submit RUN_ID STEP FILE --connected`. Continue using `next` through the due steps. Keep run state, downloads and temporary evidence private. If a tool fails, distinguish a provider read error from missing approval or a real business prerequisite.

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
    existing_adset_id: null for new build, exact Meta string ID for additions
    ads[]:
      name: "<campaign-key>-<stage>-<concept>-<format>-v01"
      format: static | video | story
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

### Campaign decisions

The lifecycle has four recorded outcomes, `COMPLETE`, `STOP`, `RECREATE`, and `SCALE`. Job status records where it is, such as ready, awaiting approval, monitoring, or blocked. A paused build can be complete while activation is waiting. Decisions inside Optimize are HOLD, FIX, TEST, REFRESH, PAUSE, RECREATE, and SCALE.

Business windows distinguish Meta delivery and attributed actions from Shopify exact last-visit Meta UTM matches. Growth requires two separate, mature windows, each within the verified CPA ceiling and each showing positive measured product contribution after ad spend. Add verified `facts.economics` with the exact `product_id`, `variant_id` where applicable, `campaign`, `success_metric` and `source`. Each `windows` entry has `start`, `end`, and measured `product_cost_minor`, `shipping_fulfillment_minor` and `fees_minor` for that exact cohort. Use Shopify receipts less refunds and retained tax for fully attributable carts. For mixed carts, provide `verified_product_net_receipts_minor` for the whole cohort from an auditable allocation. Include losses from refunded orders and avoid subtracting refunds twice. Missing receipts or costs block scaling. This measures matched-order contribution, so it does not establish incrementality.

An early operational pause can use the worker's verified allocation or month-to-date spending breach, or a verified `facts.operational_issue` on the exact target. That record includes `kind`, `target_id`, `verified`, `reference`, and `observed_at`. The existing approval process still applies. Health problems while a live run is waiting are recorded as `live_campaign_attention` and shown in run status.

The review re-reads selected campaign, ad set and creative settings from Meta. A changed configuration invalidates windows starting on or before the time it was detected. The next clean window starts on the next full account-local day. Configured runs require a baseline for performance decisions and recheck it before a scale proposal and before its first write. Snapshot comparison detects settings changes that are present at readback. An edit reverted between reviews may leave no difference.

When the brand explicitly sets `blocked_pause_after_hours`, the worker prepares a pause proposal if an unresolved blocked campaign is still active after that period and no proposal is pending. The existing approval and verified execution process still applies. Without this policy option, the worker logs attention for an active blocked run.

On a scheduled strategy refresh, configured runs return a `cycle_action` of `continue` or `recreate`. The worker provides `source_data.strategy_history` for comparison.
