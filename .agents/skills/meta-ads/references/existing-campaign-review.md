# Review a registered paused campaign

Use this step when the workflow matched an existing Meta campaign to the saved Shopify assignment and registered that paused campaign with the same run. Read the strategy, verified product facts, saved policy, and the exact paused ads and ad sets under `source_data.paused_draft`.

1. Match each ad's destination, copy, visuals and placements to the current strategy and approved product evidence. Inspect the actual Meta previews or the matching approved originals when judging creative. Record unsupported outcomes or ambiguous assets by ad name. A campaign may be registered while those checks are still open.
2. Verify Purchase optimization, assigned markets, creative formats and approved placements. Use the budget evidence for the connected Meta account to see how activating the draft would affect exposure.
3. If any check is open, choose `keep_paused` and record the specific follow-up in `findings`. If the draft passes, choose `check_activation`. The lifecycle then requests separate checkout, Purchase tracking, spend control and live Meta verification before it can present an activation proposal.

Use the connected result envelope. The data contains `decision`, `checks` with the booleans `claims`, `packaging`, `rights`, `destination`, `placement`, `copy`, and `brand`, and a `findings` list. Include dated evidence for the draft and the review. Use a passing result to record a completed review with a clear disposition. Retain the registered campaign and its existing ad IDs.
