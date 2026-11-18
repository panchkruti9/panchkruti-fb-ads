# Meta Ads lifecycle

One request starts Research → Strategy Development → Create. After the approved launch, the worker schedules monitoring, optimization and scale evaluation. When a result calls for a replacement, the worker gives the next Strategy Development step the previous strategy, campaign, outcomes and decision evidence.

- [Orchestrator](.agents/skills/meta-ads/SKILL.md) and [27 lifecycle skills](docs/skills.md)
- [Shared policy](docs/policy.md), [worker contracts](docs/contracts.md), [operating knowledge](docs/strategy-knowledge.md) and [activation checks](docs/activation.md)

## Fill in the brand and product

Users provide the product and campaign decisions in chat. Use connected sources to fill the underlying files. Keep IDs in private connection records. A missing publishing identity only blocks building, and an approver is needed when authorizing a write.

In a fresh copy, ask the agent to set up your brand with its name and website. The agent can initialize private files with `python -m ads init "BRAND NAME"` and fill them from available connected sources. It asks about missing business decisions and saves the verified details for later campaigns. The [brand profile](examples/brand-profile.json) and [product request](examples/product-request.json) are synthetic references.

| File | Required fields | Conditional or optional fields |
|---|---|---|
| Brand profile | `brand_id`, `brand_name`, `website`, `shopify_shop`, `account_id`, and `policy`. Use the exact HTTPS storefront origin and connected Shopify Admin domain. | `instagram_id` and the Facebook Page and pixel IDs are internal values. The builder can resolve them from a verified reference ad in the connected account. |
| Brand policy | `currency`, `minor_per_unit`, daily minimum and maximum, monthly maximum, `approval_hours`, approved Drive root, stage and excluded folder names, `formats`, `placements`, `claim_rules`, `operators`, `owners`, and `owner_approval_actions`. | Use an empty `claim_rules` list if the brand has no additional rules. Activation and budget changes always need explicit owner approval. |
| Product request | `product_id` (numeric Shopify ID as a string), `product_name`, verified product `landing_page`, two-letter `countries`, `objective` (`website_sales`), and `brief`. | `test_budget_minor` if explicitly set, `variant_id` with matching `?variant=` URL, `offer` (price, currency, dates and terms when applicable), `success_metric` (`paid_orders` by default, or `first_time_buyers`), `target_cost_minor`, fixed `daily_budget_minor`, narrower `formats` or `placements`, custom campaign `name`, verified `facts`, and `review_policy`. |

Enter money as integer minor currency units with the scale required by the currency. An optional test budget limits planned daily allocation multiplied by the strategy review window. Live budget protections are checked separately against the account-wide daily and monthly policy. Use the policy and request for approval and spend authority.

The campaign builder supports website Purchase with single-image, MP4 video and Story creative. Choose any permitted subset of Facebook or Instagram Feed, Stories and Reels. The Reels recipe requires video. Stories use Story placements. Catalogue, carousel and other objectives need a new build recipe. The worker verifies the requested URL against the chosen Shopify product and uses only the requested variant when scoped to one. [Build contract](docs/contracts.md)

## Start a run

Say **Start manage ads** to start or continue the full lifecycle for the saved brand’s assigned products. The agent runs `python -m ads manage --now`. A single saved brand is selected automatically. To assign several products, save their filenames in `assignments.json` beside the private `brand.json`. With one product saved as `product.json`, the list is optional. A specific product or action in your request narrows the scope.

From this workspace, using Python 3.11+, an authenticated Codex CLI and ffprobe/ffmpeg for media inspection:

```powershell
python -m ads validate-request PRODUCT.json --brand BRAND.json
python -m ads run PRODUCT.json --brand BRAND.json --now
python -m ads status RUN_ID
python -m ads proposal RUN_ID
python -m ads events RUN_ID
```

The run saves a snapshot of the brand policy and product request. If the owner sets `blocked_pause_after_hours` in the brand policy, an overdue blocked campaign gets a pause proposal under the existing approval rules. Verified financial evidence is used during scaling evaluation. Keep one database per credential deployment. Existing runs and old five-field requests can use a private legacy profile when one exists. Fresh copies start with no brand settings.

## Connect and automate

Set credentials privately on the worker and operator hosts. Use the same repository and database path for both processes. The default is `.state/ads.sqlite3`, and `META_ADS_STATE_DB` or `--db` can select a different path.

| Process | Configuration |
|---|---|
| Worker | `META_AD_ACCOUNT_ID`, `META_API_VERSION`, `META_READ_TOKEN`, `SHOPIFY_SHOP`, `SHOPIFY_API_VERSION`, `SHOPIFY_READ_TOKEN` with product and order access, and Drive read access. |
| Operator | Same Meta account and version, Drive read access, `META_WRITE_TOKEN` and a protected random `META_ADS_OPERATOR_KEY` of at least 32 characters. Reconciliation also uses the read token. |
| Host | Authenticated Codex CLI, optionally `META_ADS_CODEX_EXEC`. Install tzdata where Python cannot load the account's time zone. |

For unattended Drive access configure `DRIVE_OAUTH_CLIENT_ID`, `DRIVE_OAUTH_CLIENT_SECRET` and `DRIVE_OAUTH_REFRESH_TOKEN` with refreshable read access. A short test can use `DRIVE_READ_TOKEN`. Confirm scope with `python -m ads source account --brand BRAND.json`, `python -m ads source product PRODUCT_ID --brand BRAND.json`, or `python -m ads source drive --brand BRAND.json`.

Keep `python -m ads worker --watch` running or schedule `python -m ads worker`. Schedule a separate protected operator task running `python -m ads dispatch` to apply approved work and verify readback. Once both jobs are active, the lifecycle continues independently of chat until it reaches an approval or a recorded blocker.

## Review approvals and logs

The operator records the decision on the exact proposal. Supply the policy-listed owner identity where required.

```powershell
python -m ads approve RUN_ID PROPOSAL_ID --operator OPERATOR --reference DECISION_REFERENCE
python -m ads approve RUN_ID ACTIVATION_ID --operator OPERATOR --owner OWNER --reference DECISION_REFERENCE
python -m ads events RUN_ID
```

Add `--execute` to dispatch immediately from the operator process. Build creates paused objects. Activation requires verified checkout, Purchase tracking, previews and spend control. Use `python -m ads facts RUN_ID FACTS.json` to add verified evidence and `python -m ads resume RUN_ID` after fixing a blocker. Use `result RUN_ID STEP` to read the current step output and `events RUN_ID` to read prior strategy cycles and historical decisions.

Read back before retrying an uncertain Meta write. Use `python -m ads reconcile RUN_ID OPERATION_LABEL` to verify a known object or update. When the operator independently confirms non-execution, `--absent --reference EVIDENCE` records that finding. Renew expired partial approvals against the original proposal with `--renew` and the required exact authorizations.

Use `python -m unittest discover -s tests -v` for offline checks.
