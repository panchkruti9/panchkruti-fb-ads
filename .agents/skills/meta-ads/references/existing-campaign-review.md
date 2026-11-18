# Review a registered paused campaign

Use this step when the workflow matched an existing Meta campaign to the saved Shopify assignment and registered that paused campaign with the same run. Read the strategy, verified product facts, saved policy, and the exact paused ads and ad sets under `source_data.paused_draft`.

1. Check whether the exact campaign and account have an AGI creation receipt or verified write journal. Record origin as unknown when that evidence is missing. Use the dated Meta delivery history to determine whether the campaign spent or delivered. Treat a name prefix as a search key. Treat an undelivered draft as untested.
2. Verify Purchase optimization, assigned markets, creative formats and approved placements. Use the budget evidence for the connected Meta account to see how activating the draft would affect exposure.
3. Keep sound campaign structure and creative when they fit the strategy. Check the actual visuals, copy, links and placements. Record a concrete change for each correctable issue. Choose `replan` when the paused draft needs replacement creative and the available executor has no supported in-place revision. Carry forward useful evidence and keep the old draft paused. Choose `keep_paused` when a specific missing input prevents either route. A verified draft can use `check_activation` to proceed to the separate activation checks.

Use the connected result envelope. The data contains `decision`, `checks` with the booleans `claims`, `packaging`, `rights`, `destination`, `placement`, `copy`, and `brand`, and a `findings` list. Include dated evidence for the draft and the review. Use a passing result to record a completed review with a clear disposition. Retain the registered campaign and its existing ad IDs.
