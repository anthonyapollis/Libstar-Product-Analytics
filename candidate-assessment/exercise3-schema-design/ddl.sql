-- Exercise 3: Database design for players, wallets, bets and bonuses
-- Tool: MySQL 8.0 (InnoDB, utf8mb4)
--
-- Design principles (justified in design_notes.md):
--   * Money: DECIMAL(18,4) everywhere. Never FLOAT/DOUBLE for anything that touches a balance.
--   * Time: DATETIME(6), always UTC, named *_at_utc where ambiguity is possible. TIMESTAMP is
--     avoided because MySQL silently converts it using the session/server time zone, which is
--     exactly the kind of silent, hard-to-audit behaviour a finance-grade schema should not have.
--   * PII lives only in player_identity, separated from behavioural/analytical data (players).
--   * The wallet ledger (wallet_transactions) is append-only and is the only source of truth for
--     balances; wallets.*_balance is a materialised, recomputable cache, never edited directly.
--   * History that must be provable at a point in time (VIP tier, tags) uses SCD Type 2, not
--     UPDATE-in-place.
--   * One header table (bets) plus one detail table per product, so a sports leg, a casino round
--     and a retail slip are not forced into one over-wide table (see design_notes.md, "grain").

CREATE DATABASE IF NOT EXISTS jsb_platform CHARACTER SET utf8mb4;
USE jsb_platform;

SET FOREIGN_KEY_CHECKS = 0;

-- ===========================================================================
-- PLAYERS
-- ===========================================================================
DROP TABLE IF EXISTS affiliates;
CREATE TABLE affiliates (
    affiliate_id    INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    affiliate_code  VARCHAR(30)     NOT NULL UNIQUE,
    name            VARCHAR(120)    NOT NULL,
    traffic_source  VARCHAR(50)     NOT NULL,   -- e.g. 'organic', 'affiliate', 'referral', 'retail_walk_in'
    created_at_utc  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS players;
CREATE TABLE players (
    player_id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    -- Behavioural / operational attributes only. No name, DOB, ID number, address here.
    registered_at_utc DATETIME(6)   NOT NULL,
    kyc_status      ENUM('not_started','pending','verified','rejected') NOT NULL DEFAULT 'not_started',
    vip_tier        VARCHAR(20)     NOT NULL DEFAULT 'standard',  -- current value; history in player_vip_tier_history
    status          ENUM('active','blocked','self_excluded','closed') NOT NULL DEFAULT 'active',
    status_reason   VARCHAR(255)    NULL,
    traffic_source  VARCHAR(50)     NOT NULL,
    affiliate_id    INT UNSIGNED    NULL,
    preferred_currency CHAR(3)      NOT NULL DEFAULT 'NAD',
    created_at_utc  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at_utc  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_players_affiliate FOREIGN KEY (affiliate_id) REFERENCES affiliates(affiliate_id),
    KEY ix_players_status (status),
    KEY ix_players_vip_tier (vip_tier)
) ENGINE=InnoDB;

-- Restricted tier: PII lives here only. In production: column-level encryption
-- (e.g. AES at the application layer, or MySQL column encryption via a KMS-backed
-- key) on id_number/dob/address, a dedicated low-privilege DB user for this table
-- only, and every SELECT against it logged (see design_notes.md).
DROP TABLE IF EXISTS player_identity;
CREATE TABLE player_identity (
    player_id       BIGINT UNSIGNED PRIMARY KEY,
    first_name      VARCHAR(100)    NOT NULL,
    last_name       VARCHAR(100)    NOT NULL,
    date_of_birth   DATE            NOT NULL,
    national_id_number VARBINARY(255) NOT NULL,   -- application-layer encrypted
    email           VARCHAR(255)    NOT NULL,
    phone           VARCHAR(30)     NOT NULL,
    address_line1   VARCHAR(255)    NULL,
    address_city    VARCHAR(100)    NULL,
    address_country CHAR(2)         NOT NULL,     -- ISO 3166-1 alpha-2
    updated_at_utc  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_identity_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    UNIQUE KEY uq_identity_email (email)
) ENGINE=InnoDB;

-- SCD2: VIP tier history. players.vip_tier is the current value (fast to read);
-- this table is what "what was the tier on 3 June" queries against.
DROP TABLE IF EXISTS player_vip_tier_history;
CREATE TABLE player_vip_tier_history (
    player_id       BIGINT UNSIGNED NOT NULL,
    vip_tier        VARCHAR(20)     NOT NULL,
    valid_from_utc  DATETIME(6)     NOT NULL,
    valid_to_utc    DATETIME(6)     NULL,          -- NULL = current
    changed_by      VARCHAR(100)    NOT NULL,       -- system rule name or staff user
    PRIMARY KEY (player_id, valid_from_utc),
    CONSTRAINT fk_viphist_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    KEY ix_viphist_current (player_id, valid_to_utc)
) ENGINE=InnoDB;

-- SCD2: tags (multi-valued, e.g. 'bonus_abuse_watch', 'high_value', 'self_excluded_nudge').
DROP TABLE IF EXISTS player_tag_history;
CREATE TABLE player_tag_history (
    tag_history_id  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_id       BIGINT UNSIGNED NOT NULL,
    tag             VARCHAR(50)     NOT NULL,
    valid_from_utc  DATETIME(6)     NOT NULL,
    valid_to_utc    DATETIME(6)     NULL,
    CONSTRAINT fk_taghist_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    KEY ix_taghist_current (player_id, tag, valid_to_utc)
) ENGINE=InnoDB;

-- ===========================================================================
-- WALLETS & THE LEDGER
-- ===========================================================================
DROP TABLE IF EXISTS wallets;
CREATE TABLE wallets (
    wallet_id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_id       BIGINT UNSIGNED NOT NULL,
    currency        CHAR(3)         NOT NULL DEFAULT 'NAD',
    -- Materialised cache of wallet_transactions, recomputable at any time.
    -- Never written directly by application code -- only by the ledger-posting
    -- procedure, in the same transaction as the ledger row (see design_notes.md).
    real_balance    DECIMAL(18,4)   NOT NULL DEFAULT 0,
    bonus_balance   DECIMAL(18,4)   NOT NULL DEFAULT 0,
    updated_at_utc  DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_wallet_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    UNIQUE KEY uq_wallet_player_currency (player_id, currency),
    CONSTRAINT ck_wallet_nonneg CHECK (real_balance >= 0 AND bonus_balance >= 0)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS wallet_transactions;
CREATE TABLE wallet_transactions (
    wallet_txn_id   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    wallet_id       BIGINT UNSIGNED NOT NULL,
    player_id       BIGINT UNSIGNED NOT NULL,       -- denormalised for query convenience; always = wallets.player_id
    txn_type        ENUM('deposit','withdrawal','bet_stake','bet_win','bonus_credit',
                         'bonus_debit','refund','reversal','manual_adjustment') NOT NULL,
    balance_type    ENUM('real','bonus')            NOT NULL,
    amount          DECIMAL(18,4)   NOT NULL,        -- always positive; sign is implied by txn_type
    direction       ENUM('credit','debit')          NOT NULL,
    balance_before  DECIMAL(18,4)   NOT NULL,
    balance_after   DECIMAL(18,4)   NOT NULL,
    -- Lineage back to the event that caused this movement. Exactly one of these
    -- is populated per row, enforced in the posting procedure, not by CHECK
    -- (MySQL CHECK cannot easily express "exactly one of N columns").
    related_deposit_attempt_id BIGINT UNSIGNED NULL,
    related_withdrawal_id      BIGINT UNSIGNED NULL,
    related_bet_id             BIGINT UNSIGNED NULL,
    related_player_bonus_id    BIGINT UNSIGNED NULL,
    reversal_of_wallet_txn_id  BIGINT UNSIGNED NULL,  -- set when this row reverses an earlier one
    -- Deterministic idempotency key: source_system + source_event_id (or a hash
    -- of immutable business fields for internally-generated events). Loads are
    -- upserts against this key -- replaying an event is always safe.
    idempotency_key VARCHAR(150)    NOT NULL,
    source_system   VARCHAR(30)     NOT NULL DEFAULT 'platform',
    status          ENUM('posted','reversed') NOT NULL DEFAULT 'posted',
    created_at_utc  DATETIME(6)     NOT NULL,
    ingested_at_utc DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_wtxn_wallet FOREIGN KEY (wallet_id) REFERENCES wallets(wallet_id),
    CONSTRAINT fk_wtxn_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    CONSTRAINT fk_wtxn_reversal FOREIGN KEY (reversal_of_wallet_txn_id) REFERENCES wallet_transactions(wallet_txn_id),
    UNIQUE KEY uq_wtxn_idempotency (idempotency_key),
    KEY ix_wtxn_wallet_time (wallet_id, created_at_utc),
    KEY ix_wtxn_player_time (player_id, created_at_utc),
    KEY ix_wtxn_bet (related_bet_id),
    KEY ix_wtxn_bonus (related_player_bonus_id)
) ENGINE=InnoDB;

-- ===========================================================================
-- PAYMENTS (feeds the wallet ledger; also what Exercise 1's reconciliation reads)
-- ===========================================================================
DROP TABLE IF EXISTS payment_methods;
CREATE TABLE payment_methods (
    method_id       INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    method_code     VARCHAR(30)     NOT NULL UNIQUE,   -- e.g. 'EFT_INSTANT', 'VOUCHER', 'MOBILE_MONEY'
    rail_family     VARCHAR(30)     NOT NULL           -- e.g. 'EFT', 'card', 'voucher', 'mobile_money'
) ENGINE=InnoDB;

DROP TABLE IF EXISTS deposit_attempts;
CREATE TABLE deposit_attempts (
    deposit_attempt_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_id       BIGINT UNSIGNED NOT NULL,
    method_id       INT UNSIGNED    NOT NULL,
    amount          DECIMAL(18,4)   NOT NULL,
    currency        CHAR(3)         NOT NULL,
    gateway_ref     VARCHAR(50)     NOT NULL,
    status          ENUM('initiated','success','failed') NOT NULL,
    created_at_utc  DATETIME(6)     NOT NULL,
    settled_at_utc  DATETIME(6)     NULL,
    CONSTRAINT fk_deposit_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    CONSTRAINT fk_deposit_method FOREIGN KEY (method_id) REFERENCES payment_methods(method_id),
    KEY ix_deposit_player_time (player_id, created_at_utc),
    KEY ix_deposit_gateway_ref (gateway_ref)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS withdrawal_requests;
CREATE TABLE withdrawal_requests (
    withdrawal_id   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_id       BIGINT UNSIGNED NOT NULL,
    method_id       INT UNSIGNED    NOT NULL,
    amount          DECIMAL(18,4)   NOT NULL,
    currency        CHAR(3)         NOT NULL,
    status          ENUM('requested','approved','paid','failed','cancelled') NOT NULL,
    requested_at_utc DATETIME(6)    NOT NULL,
    paid_at_utc     DATETIME(6)     NULL,
    CONSTRAINT fk_withdrawal_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    CONSTRAINT fk_withdrawal_method FOREIGN KEY (method_id) REFERENCES payment_methods(method_id),
    KEY ix_withdrawal_player_time (player_id, requested_at_utc)
) ENGINE=InnoDB;

-- ===========================================================================
-- BETS: one header, one detail table per product (see "grain" in design_notes.md)
-- ===========================================================================
DROP TABLE IF EXISTS bets;
CREATE TABLE bets (
    bet_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_id       BIGINT UNSIGNED NOT NULL,
    product         ENUM('sportsbook','casino','retail') NOT NULL,
    channel         ENUM('web','app','retail') NOT NULL,
    stake_real_amount  DECIMAL(18,4) NOT NULL DEFAULT 0,
    stake_bonus_amount DECIMAL(18,4) NOT NULL DEFAULT 0,
    total_stake     DECIMAL(18,4)   GENERATED ALWAYS AS (stake_real_amount + stake_bonus_amount) STORED,
    status          ENUM('open','won','lost','void','cashed_out') NOT NULL DEFAULT 'open',
    payout_amount   DECIMAL(18,4)   NOT NULL DEFAULT 0,
    placed_at_utc   DATETIME(6)     NOT NULL,
    settled_at_utc  DATETIME(6)     NULL,
    CONSTRAINT fk_bets_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    CONSTRAINT ck_bets_stake_nonneg CHECK (stake_real_amount >= 0 AND stake_bonus_amount >= 0),
    KEY ix_bets_player_time (player_id, placed_at_utc),
    KEY ix_bets_product_time (product, placed_at_utc, status)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS sports_events;
CREATE TABLE sports_events (
    event_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sport            VARCHAR(50)    NOT NULL,
    league           VARCHAR(100)   NOT NULL,
    home_team        VARCHAR(100)   NOT NULL,
    away_team        VARCHAR(100)   NOT NULL,
    starts_at_utc    DATETIME(6)    NOT NULL
) ENGINE=InnoDB;

DROP TABLE IF EXISTS sports_bet_details;
CREATE TABLE sports_bet_details (
    bet_id          BIGINT UNSIGNED PRIMARY KEY,
    bet_class       ENUM('single','accumulator') NOT NULL,
    total_odds      DECIMAL(10,3)   NOT NULL,
    leg_count       SMALLINT UNSIGNED NOT NULL,
    min_odds_rule_applied DECIMAL(10,3) NULL,  -- captured for bonus-rollover audit (min odds rule)
    CONSTRAINT fk_sportsdet_bet FOREIGN KEY (bet_id) REFERENCES bets(bet_id)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS bet_legs;
CREATE TABLE bet_legs (
    leg_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    bet_id          BIGINT UNSIGNED NOT NULL,
    event_id        BIGINT UNSIGNED NOT NULL,
    market          VARCHAR(100)    NOT NULL,   -- e.g. 'match_winner', 'over_under_2.5'
    selection       VARCHAR(100)    NOT NULL,
    odds            DECIMAL(10,3)   NOT NULL,
    leg_result      ENUM('pending','won','lost','void') NOT NULL DEFAULT 'pending',
    CONSTRAINT fk_leg_bet FOREIGN KEY (bet_id) REFERENCES bets(bet_id),
    CONSTRAINT fk_leg_event FOREIGN KEY (event_id) REFERENCES sports_events(event_id),
    KEY ix_leg_bet (bet_id)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS game_providers;
CREATE TABLE game_providers (
    provider_id     INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE
) ENGINE=InnoDB;

DROP TABLE IF EXISTS games;
CREATE TABLE games (
    game_id         INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    provider_id     INT UNSIGNED    NOT NULL,
    name            VARCHAR(150)    NOT NULL,
    category        VARCHAR(50)     NOT NULL,   -- 'slots','table','live_dealer',...
    rtp_theoretical DECIMAL(6,3)    NOT NULL,   -- % as configured by the provider
    CONSTRAINT fk_games_provider FOREIGN KEY (provider_id) REFERENCES game_providers(provider_id)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS casino_round_details;
CREATE TABLE casino_round_details (
    bet_id          BIGINT UNSIGNED PRIMARY KEY,
    game_id         INT UNSIGNED    NOT NULL,
    provider_round_ref VARCHAR(100) NOT NULL,   -- provider's own round id, for their-side reconciliation
    CONSTRAINT fk_casinodet_bet FOREIGN KEY (bet_id) REFERENCES bets(bet_id),
    CONSTRAINT fk_casinodet_game FOREIGN KEY (game_id) REFERENCES games(game_id),
    UNIQUE KEY uq_casino_provider_round (game_id, provider_round_ref)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS retail_locations;
CREATE TABLE retail_locations (
    location_id     INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150)    NOT NULL,
    address_city    VARCHAR(100)    NOT NULL
) ENGINE=InnoDB;

DROP TABLE IF EXISTS devices;
CREATE TABLE devices (
    device_id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fingerprint     VARCHAR(255)    NOT NULL UNIQUE,
    device_type     VARCHAR(30)     NOT NULL   -- 'pos_terminal','mobile','desktop'
) ENGINE=InnoDB;

DROP TABLE IF EXISTS retail_bet_details;
CREATE TABLE retail_bet_details (
    bet_id          BIGINT UNSIGNED PRIMARY KEY,
    location_id     INT UNSIGNED    NOT NULL,
    device_id       BIGINT UNSIGNED NOT NULL,
    ticket_number   VARCHAR(50)     NOT NULL,
    CONSTRAINT fk_retaildet_bet FOREIGN KEY (bet_id) REFERENCES bets(bet_id),
    CONSTRAINT fk_retaildet_loc FOREIGN KEY (location_id) REFERENCES retail_locations(location_id),
    CONSTRAINT fk_retaildet_device FOREIGN KEY (device_id) REFERENCES devices(device_id),
    UNIQUE KEY uq_retail_ticket (location_id, ticket_number)
) ENGINE=InnoDB;

-- ===========================================================================
-- BONUSES
-- ===========================================================================
DROP TABLE IF EXISTS bonus_campaigns;
CREATE TABLE bonus_campaigns (
    campaign_id     INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150)    NOT NULL,
    campaign_type   ENUM('registration','deposit_match','cashback','free_spins','other') NOT NULL,
    trigger_rule    VARCHAR(255)    NOT NULL,       -- e.g. 'first_deposit', 'weekly_net_loss>0'
    audience_rule   VARCHAR(255)    NOT NULL,       -- e.g. 'all', 'vip_tier=gold'
    rollover_multiple DECIMAL(6,2)  NOT NULL,
    min_odds        DECIMAL(10,3)   NULL,
    max_stake_while_active DECIMAL(18,4) NULL,
    expiry_days     INT UNSIGNED    NOT NULL,
    valid_from_utc  DATETIME(6)     NOT NULL,
    valid_to_utc    DATETIME(6)     NULL,
    terms_json      JSON            NULL
) ENGINE=InnoDB;

DROP TABLE IF EXISTS player_bonuses;
CREATE TABLE player_bonuses (
    player_bonus_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_id       BIGINT UNSIGNED NOT NULL,
    campaign_id     INT UNSIGNED    NOT NULL,
    granted_amount  DECIMAL(18,4)   NOT NULL,
    rollover_required DECIMAL(18,4) NOT NULL,        -- granted_amount * campaign.rollover_multiple at grant time
    rollover_progress DECIMAL(18,4) NOT NULL DEFAULT 0,  -- cache; recomputable from bonus_rollover_events
    status          ENUM('active','completed','expired','forfeited') NOT NULL DEFAULT 'active',
    granted_at_utc  DATETIME(6)     NOT NULL,
    expires_at_utc  DATETIME(6)     NOT NULL,
    resolved_at_utc DATETIME(6)     NULL,
    CONSTRAINT fk_pbonus_player FOREIGN KEY (player_id) REFERENCES players(player_id),
    CONSTRAINT fk_pbonus_campaign FOREIGN KEY (campaign_id) REFERENCES bonus_campaigns(campaign_id),
    KEY ix_pbonus_player_status (player_id, status)
) ENGINE=InnoDB;

-- Every qualifying bet's contribution to rollover, event-sourced so
-- rollover_progress above is always recomputable and auditable, never just a
-- trusted running counter.
DROP TABLE IF EXISTS bonus_rollover_events;
CREATE TABLE bonus_rollover_events (
    rollover_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    player_bonus_id BIGINT UNSIGNED NOT NULL,
    bet_id          BIGINT UNSIGNED NOT NULL,
    contribution_amount DECIMAL(18,4) NOT NULL,
    created_at_utc  DATETIME(6)     NOT NULL,
    CONSTRAINT fk_rollover_pbonus FOREIGN KEY (player_bonus_id) REFERENCES player_bonuses(player_bonus_id),
    CONSTRAINT fk_rollover_bet FOREIGN KEY (bet_id) REFERENCES bets(bet_id),
    UNIQUE KEY uq_rollover_bet_bonus (player_bonus_id, bet_id)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;

-- Now that wallet_transactions exists, wire the FKs that were forward references.
ALTER TABLE wallet_transactions
    ADD CONSTRAINT fk_wtxn_deposit FOREIGN KEY (related_deposit_attempt_id) REFERENCES deposit_attempts(deposit_attempt_id),
    ADD CONSTRAINT fk_wtxn_withdrawal FOREIGN KEY (related_withdrawal_id) REFERENCES withdrawal_requests(withdrawal_id),
    ADD CONSTRAINT fk_wtxn_bet FOREIGN KEY (related_bet_id) REFERENCES bets(bet_id),
    ADD CONSTRAINT fk_wtxn_bonus FOREIGN KEY (related_player_bonus_id) REFERENCES player_bonuses(player_bonus_id);
