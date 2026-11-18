# Meta Ads lifecycle

One request starts Research → Strategy Development → Create. After the approved launch, the connected agent continues monitoring, optimization and scale evaluation on its schedule. When a result calls for a replacement, the next Strategy Development step receives the previous strategy, campaign, outcomes and decision evidence.

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

Say **Start manage ads** to start or continue the full lifecycle for the saved brand’s assigned products. The agent runs `python -m ads manage --connected` and uses the existing Shopify and Drive plugins. A single saved brand is selected automatically. To assign several products, save their filenames in `assignments.json` beside the private `brand.json`. With one product saved as `product.json`, the list is optional. A specific product or action in your request narrows the scope.

From this workspace, use Python 3.11+ and ffprobe/ffmpeg for local media inspection:

```powershell
python -m ads validate-request PRODUCT.json --brand BRAND.json
python -m ads run PRODUCT.json --brand BRAND.json --connected
python -m ads status RUN_ID
python -m ads proposal RUN_ID
python -m ads events RUN_ID
```

The run saves a snapshot of the brand policy and product request. If the owner sets `blocked_pause_after_hours` in the brand policy, an overdue blocked campaign gets a pause proposal under the existing approval rules. Verified financial evidence is used during scaling evaluation. Keep one database per credential deployment. Existing runs and old five-field requests can use a private legacy profile when one exists. Fresh copies start with no brand settings.

## Connect and automate

Use one scheduled connected agent to read Shopify and Drive and resume due lifecycle steps. Follow the [connected step contract](docs/contracts.md#connected-agent-steps). Use the same private database and media directory for the agent, Meta worker and protected operator. The default database is `.state/ads.sqlite3`, and `META_ADS_STATE_DB` or `--db` can select a different path.

| Process | Configuration |
|---|---|
| Connected agent | Shopify Admin product and order reads and approved Drive media reads through its plugins. |
| Meta worker | `META_AD_ACCOUNT_ID`, `META_API_VERSION` and `META_READ_TOKEN` in the process that performs Meta reads. Install tzdata where Python cannot load the account's time zone. |
| Protected Meta operator | Same Meta account and version, `META_WRITE_TOKEN`, and a protected random `META_ADS_OPERATOR_KEY` of at least 32 characters. Reconciliation uses the read token. The agent supplies current approved Drive originals for builds. |

GitHub Actions secrets are available inside Actions jobs. A local Meta worker uses its own process environment. A GitHub-hosted Meta worker needs private access to the same run state and approved media. The existing GitHub reporting workflow is a separate job.

When the connected agent requests a Meta-only step, call `python -m ads worker --run RUN_ID` on the configured Meta host. For approved work, the protected operator runs `python -m ads dispatch` and verifies readback. A host with direct Shopify and Drive API connections can still explicitly use the legacy `--now` mode for its existing runs.

### Catch up after the agent is offline

The [Meta catch-up workflow](.github/workflows/meta-catchup.yml) reads the approved Meta account once a day. It collects recent daily Insights and delivery health for managed campaigns, and encrypts the snapshots before uploading them. Configure the workflow with the existing Meta access secret, the account ID in the `META_CATCHUP_ACCOUNT_ID` secret, and the public recipient certificate in the `META_CATCHUP_CERT` repository variable. Keep the matching private key, certificate and `config.json` in `.state/meta-catchup/` beside the state database. The configuration contains the GitHub `repo` in owner/repository form. Generate the key pair once with `python -c "from pathlib import Path; from ads.meta_catchup import setup; setup(Path('.state/meta-catchup'))"`. Keep the key in private storage.

On wake, the connected agent runs its usual `manage --connected` entry point. The agent imports completed snapshots, records unseen observations for the saved campaign, and runs the next review when due. Meta and Shopify windows must use the same dates. The recent snapshot can supply account research or review evidence when direct Meta reads are unavailable. Any later budget validation, proposal, or execution still uses the live Meta checks and existing approvals. Local catch-up requires authenticated GitHub CLI and OpenSSL. Use `python -m ads meta-sync` to check catch-up independently.

The snapshot includes account-wide funding and paused campaign readback. At campaign strategy, the lifecycle can register an existing paused draft when the exact account, campaign, Shopify product and variant agree. The saved campaign then enters draft review before separate activation checks and approval.

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
