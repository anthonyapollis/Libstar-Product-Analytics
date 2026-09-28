-- Type 2 dimension: exactly the SCD pattern used for player_vip_tier_history
-- in the operational schema, carried through to the reporting layer so a fact
-- can be joined to "the tier that was true when the event happened", not just
-- today's tier. See design_notes.md, "From operational design to a reporting model".
select
    player_id,
    vip_tier,
    valid_from_utc,
    coalesce(valid_to_utc, '9999-12-31') as valid_to_utc,
    is_current
from {{ ref('stg_player_vip_tier_history') }}
