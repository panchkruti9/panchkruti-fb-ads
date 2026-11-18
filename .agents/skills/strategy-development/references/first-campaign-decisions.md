# Make the first campaign useful

Use this guidance when purchase history, reviews, or prior delivery are sparse. A new account can still support a useful first strategy. Build an explicit buying hypothesis from what is available, then use the campaign to learn which part of that hypothesis holds.

## Find the buyer and the buying reason

Start with the exact product page, price, contents, directions, shipping coverage, existing artwork and alternatives a shopper can buy. Read relevant public product reviews, questions and brand-owned social content where available. Record each source and its market. A competitor's claim or review describes that competitor's product and customers.

Use that research to propose a few plausible buying situations. A useful situation combines what the shopper wants, what they use today, what might make them change, and what could prevent a purchase. Label observed statements and inferred motivations explicitly. Empty order history is evidence about order coverage. It gives little information about demand.

For example, a two-item skincare set could appeal to someone choosing their first targeted routine, someone replacing one disappointing item, or someone comparing the convenience and total cost of a set against separate products. These are candidate hypotheses. Research price, instructions and alternatives to determine which is most credible for the specific offer.

For each candidate, record the need, likely objection, reason the offer might answer it, source or inference, and a creative angle. Choose the strongest buying reason for the first test. Keep the alternatives in the strategy so the next cycle has a direction if the first message fails.

Use the existing Customer Research output fields. Put labelled candidate buyer situations in `segments`, inferred or observed needs in `motivations`, purchase friction in `objections`, and the proposed test in `hypotheses`. Keep missing historical coverage in `coverage`.

## Translate the buyer into delivery

The strategy's buyer description explains the message. Audience Planning separately chooses the controls Meta will receive. A buyer interested in a skin-care result can be addressed through product messaging without assuming Meta can identify their skin condition.

| Available evidence | Starting delivery choice | What to explain |
|---|---|---|
| Few sales and no verified usable warm audience | Broad prospecting within the confirmed market, using the permitted placements | Why the offer and creative can identify interested buyers, and why a narrower restriction would help or hurt |
| Verified website or engagement audience with usable delivery and budget | Consider a distinct warm ad set if there is a message or allocation to test | Audience definition, recency, product relevance, overlap, and expected exposure |
| Verified product-view or cart audience | Consider BOFU messaging that answers the purchase objection | Exact audience, purchaser exclusion where appropriate, offer, and destination |
| Usable lookalike with a relevant, verified seed | Consider a prospecting comparison when spend can support it | Seed quality, market, overlap, and how the result will be compared |

Choose interests or lookalikes when they answer a specific test and the executor supports them. The current executor supports broad delivery and saved Custom Audience inclusion/exclusion. An unsupported audience option remains a proposed future test while the supported campaign proceeds.

In Audience Planning, explain both the selected audience and the alternatives deferred. When using the builder's `audience` field, save the scope in `targeting_requirements.adset_audiences` by exact ad set name. Carry it through Creative Validation to the builder. Read back the saved targeting and any expansion controls before launch.

## Connect the funnel to the message

TOFU makes a shopper recognize the product's relevance. MOFU answers an objection or helps compare options. BOFU makes the purchase decision clear. Choose stage and message from the buying situation and available creative.

These jobs can share one Sales campaign and one ad set. Separate delivery makes sense when a useful audience, budget allocation or test distinguishes it. Three folder names alone supply no reason to split spend three ways.

For a small first campaign, select a manageable set of materially different ideas where artwork and spend allow. For example, show a product-use situation in one concept and answer a purchase objection in another. State which idea is being tested if only one can be prepared. A font or headline-length change supplies a weaker comparison than a different buying reason. Preserve acceptable existing brand artwork.

## Budget, timing and decisions

Use the owner's saved spend limits. Use available product costs and contribution to understand an affordable purchase cost. When those costs are missing, prepare the campaign within the authorized allocation and identify the economic uncertainty. A provisional CPA scenario can help estimate test volume, provided it stays labelled as a scenario and is kept outside the verified executable CPA ceiling.

Estimate how much exposure each proposed split can receive. At a hypothetical 300 daily allocation and an assumed CPA of 600, the expected rate would be half an order per day. Two equally funded ad sets would each receive an expected quarter order per day. Those assumptions explain a tradeoff. They supply no account benchmark or promise.

Use `criteria` to record a justified reporting window, lag, minimum evidence, cost ceiling where supplied, and recheck interval. A daily health check can investigate broken delivery or checkout before a complete conversion window exists. Explain the selected conversion window using expected exposure and reporting lag. A fixed 3-, 7-, or 14-day calendar rule cannot establish a winner on its own. Missing history or a Learning label alone supplies no reason to change the Purchase objective.

| What the first observations show | What to investigate or do |
|---|---|
| Little delivery or a platform issue | Check status, budget, audience availability, bids and account issues |
| Clicks with few landing-page arrivals | Check URL loading, redirects, placement traffic and measurement |
| Arrivals with little product or checkout activity | Inspect message match, page clarity, price, offer and purchase friction |
| Checkout starts without completed payments | Check shipping, payment, stock and checkout errors |
| Few purchases and little exposure | Continue the planned hypothesis within its spending authority and set the next review |
| Mature results that contradict the hypothesis | Record the failed buying reason and choose the next supported hypothesis |
| Consistent purchases and verified positive contribution | Evaluate scaling under the existing budget and approval policy |

The existing workflow validates which actions the evidence supports. Keep the diagnosis and next action in the strategy even when a particular performance decision needs a later review.

## Save a decision the next skill can use

Write the chosen buyer, buying reason, offer, message, delivery audience, budget reasoning and next test in the existing strategy fields. For each important choice, explain what evidence led to it and what observation would change it. The next skill should be able to explain the same campaign without reconstructing the whole research session.

This is applied planning guidance. Meta's primary guidance supports simplifying account structure, diversifying creative by concept and motivator, improving data quality and validating results. The audience and budget decisions still depend on the particular account.

- [Meta Performance 5](https://www.facebookblueprint.com/student/path/253157-performance-5)
- [Meta creative diversification](https://www.facebookblueprint.com/student/path/253130-increase-campaign-performance-with-diversified-creative)
- [Meta targeting fields](https://developers.facebook.com/docs/graph-api/reference/targeting/)
