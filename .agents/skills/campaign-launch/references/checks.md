# Activation checkpoint

This is the Campaign Launch skill checkpoint after Campaign Build. The worker reads the saved build receipt, storefront and available Meta placement previews. It also needs checked facts for this product, checkout and Purchase event source. Capture source, test event reference, product ID, variant ID when requested, pixel ID, timestamp and any browser/server deduplication check. Verify real checkout behavior without placing an uncontrolled paid test order.

The preview API confirms a preview can be generated. The operator opens the actual previews for the exact ad IDs in Ads Manager and checks crop, text, URL and CTA while reviewing the proposal. Record that review in the approval reference. The owner approves this exact activation. The executor checks approved objects and creative fingerprints, destination, budget, and remaining hard spend control immediately before applying it. For a new campaign, it activates the children first and the campaign last. Meta configured status and effective delivery are reported separately. A verified activation schedules the first Optimize review.

If media, landing page, settings, scope or spend controls change, resolve the affected evidence before execution. If an activation partially succeeds, reconcile the journal and retain the original proposal until the exact outcome is understood.
