-- Grain: one row per accepted wager, whatever the product. Do not join in
-- product-specific detail (legs, game, location) here -- that would change the
-- grain. Product detail is joined at the fact/mart layer, one fact per product
-- if a consumer needs that detail, keeping fact_bet itself at "one bet" grain.
select
    bet_id,
    player_id,
    product,
    channel,
    stake_real_amount,
    stake_bonus_amount,
    total_stake,
    status,
    payout_amount,
    (total_stake - payout_amount) as ggr_contribution,
    placed_at_utc,
    settled_at_utc
from {{ source('jsb_platform', 'bets') }}
