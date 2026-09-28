-- Minimal seed data so example_queries.sql returns real, checkable results.
-- Not a volume test -- just enough of each entity to exercise every relationship.
USE jsb_platform;

INSERT INTO affiliates (affiliate_id, affiliate_code, name, traffic_source) VALUES
  (1,'AFF-001','Windhoek Sports Blog','affiliate'),
  (2,'AFF-002','Direct','organic');

INSERT INTO players (player_id, registered_at_utc, registration_channel, kyc_status, vip_tier, status, traffic_source, affiliate_id, preferred_currency) VALUES
  (1,'2026-08-01 08:00:00','web','verified','gold','active','affiliate',1,'NAD'),
  (2,'2026-08-15 09:30:00','retail','verified','standard','active','organic',2,'NAD'),
  (3,'2026-08-20 12:00:00','app','verified','standard','active','organic',2,'NAD');

INSERT INTO player_identity (player_id, first_name, last_name, date_of_birth, national_id_number, email, phone, address_city, address_country) VALUES
  (1,'Anna','Shikongo','1990-04-12', 'ENC[demo-only]', 'anna.s@example.com','+264811000001','Windhoek','NA'),
  (2,'Johan','Beukes','1985-11-03', 'ENC[demo-only]', 'johan.b@example.com','+264811000002','Windhoek','NA'),
  (3,'Maria','Nangolo','1992-02-27','ENC[demo-only]', 'maria.n@example.com','+264811000003','Swakopmund','NA');

INSERT INTO player_vip_tier_history (player_id, vip_tier, valid_from_utc, valid_to_utc, changed_by) VALUES
  (1,'standard','2026-08-01 08:00:00','2026-09-01 00:00:00','system:tier_rule'),
  (1,'gold','2026-09-01 00:00:00',NULL,'system:tier_rule'),
  (2,'standard','2026-08-15 09:30:00',NULL,'system:tier_rule'),
  (3,'standard','2026-08-20 12:00:00',NULL,'system:tier_rule');

-- Status and KYC over time: player 1 registered unverified and passed KYC the next day.
INSERT INTO player_status_history (player_id, status, kyc_status, reason, valid_from_utc, valid_to_utc, changed_by) VALUES
  (1,'active','pending',NULL,'2026-08-01 08:00:00','2026-08-02 10:00:00','system:registration'),
  (1,'active','verified','KYC documents approved','2026-08-02 10:00:00',NULL,'kyc_team:agent_014'),
  (2,'active','verified',NULL,'2026-08-15 09:30:00',NULL,'system:registration'),
  (3,'active','verified',NULL,'2026-08-20 12:00:00',NULL,'system:registration');

INSERT INTO player_tag_history (player_id, tag, valid_from_utc, valid_to_utc) VALUES
  (1,'high_value','2026-09-01 00:00:00',NULL),
  (3,'bonus_abuse_watch','2026-09-05 00:00:00',NULL);

-- Cache values equal the ledger totals of the wallet_transactions below; the
-- dbt test assert_wallet_cache_matches_ledger fails the build if they drift.
INSERT INTO wallets (wallet_id, player_id, currency, real_balance, bonus_balance) VALUES
  (1,1,'NAD', 890.00, 0.00),
  (2,2,'NAD', 415.00, 0.00),
  (3,3,'NAD', 90.00, 10.00);

INSERT INTO payment_methods (method_id, method_code, rail_family) VALUES
  (1,'EFT_INSTANT','EFT'), (2,'VOUCHER','voucher');

-- Query (d) fixture: player 2 fails once, then succeeds shortly after.
INSERT INTO deposit_attempts (deposit_attempt_id, player_id, method_id, amount, currency, gateway_ref, status, created_at_utc, settled_at_utc) VALUES
  (1,2,1,500.00,'NAD','GW-D0001','failed','2026-09-10 09:00:00',NULL),
  (2,2,1,500.00,'NAD','GW-D0002','success','2026-09-10 09:04:00','2026-09-10 09:05:00'),
  (3,1,1,1000.00,'NAD','GW-D0003','success','2026-09-02 10:00:00','2026-09-02 10:01:00'),
  (4,3,1,100.00,'NAD','GW-D0004','success','2026-09-03 11:00:00','2026-09-03 11:01:00');

INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, related_deposit_attempt_id, idempotency_key, created_at_utc)
VALUES
  (1,2,2,'deposit','real',500.00,'credit',0,500.00,2,'deposit:GW-D0002','2026-09-10 09:05:00'),
  (2,1,1,'deposit','real',1000.00,'credit',0,1000.00,3,'deposit:GW-D0003','2026-09-02 10:01:00'),
  (3,3,3,'deposit','real',100.00,'credit',0,100.00,4,'deposit:GW-D0004','2026-09-03 11:01:00');

-- Bonus: registration bonus for player 3 (active, partly wagered) and for player 2 (forfeited
-- unwagered when they withdrew before meeting the rollover: removed from the bonus balance, so it cost nothing).
INSERT INTO bonus_campaigns (campaign_id, name, campaign_type, trigger_rule, audience_rule, rollover_multiple, min_odds, expiry_days, valid_from_utc) VALUES
  (1,'Registration Bonus','registration','first_deposit','all_new_players',3.00,1.500,30,'2026-01-01 00:00:00');

INSERT INTO player_bonuses (player_bonus_id, player_id, campaign_id, granted_amount, rollover_required, rollover_progress, status, granted_at_utc, expires_at_utc, resolved_at_utc) VALUES
  (1,3,1,50.00,150.00,50.00,'active','2026-09-03 11:05:00','2026-10-03 11:05:00',NULL),
  (2,2,1,25.00,75.00,0.00,'forfeited','2026-09-15 09:05:00','2026-10-15 09:05:00','2026-09-20 10:00:00');

INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, related_player_bonus_id, idempotency_key, created_at_utc)
VALUES
  (4,3,3,'bonus_credit','bonus',50.00,'credit',0,50.00,1,'bonus_grant:1','2026-09-03 11:05:00');

-- Sportsbook: player 1 places a single, wins.
INSERT INTO sports_events (event_id, sport, league, home_team, away_team, starts_at_utc) VALUES
  (1,'Football','Namibia Premier League','Blue Waters','African Stars','2026-09-05 15:00:00');

-- Bet 2 is paid entirely from player 3's bonus balance (grant 1); bets can also split real + bonus.
INSERT INTO bets (bet_id, request_id, player_id, product, channel, stake_real_amount, stake_bonus_amount, player_bonus_id, status, payout_amount, placed_at_utc, settled_at_utc) VALUES
  (1,'REQ-BET-0001',1,'sportsbook','web',200.00,0.00,NULL,'won',360.00,'2026-09-05 14:00:00','2026-09-05 17:00:00'),
  (2,'REQ-BET-0002',3,'sportsbook','app',0.00,20.00,1,'lost',0.00,'2026-09-06 10:00:00','2026-09-06 12:00:00');

INSERT INTO sports_bet_details (bet_id, bet_class, total_odds, leg_count, min_odds_rule_applied) VALUES
  (1,'single',1.800,1,NULL),
  (2,'single',2.000,1,1.500);

INSERT INTO bet_legs (bet_id, event_id, market, selection, odds, leg_result) VALUES
  (1,1,'match_winner','Blue Waters',1.800,'won'),
  (2,1,'match_winner','African Stars',2.000,'lost');

INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, related_bet_id, idempotency_key, created_at_utc)
VALUES
  (5,1,1,'bet_stake','real',200.00,'debit',1000.00,800.00,1,'bet_stake:1','2026-09-05 14:00:00'),
  (6,1,1,'bet_win','real',360.00,'credit',800.00,1160.00,1,'bet_win:1','2026-09-05 17:00:00'),
  (7,3,3,'bet_stake','bonus',20.00,'debit',50.00,30.00,2,'bet_stake:2','2026-09-06 10:00:00');

INSERT INTO bonus_rollover_events (player_bonus_id, bet_id, contribution_amount, created_at_utc) VALUES
  (1,2,20.00,'2026-09-06 12:00:00');

-- Casino: player 1 plays a round.
INSERT INTO game_providers (provider_id, name) VALUES (1,'Pragmatic Play');
INSERT INTO games (game_id, provider_id, name, category, rtp_theoretical) VALUES (1,1,'Gates of Olympus','slots',96.500);
INSERT INTO bets (bet_id, request_id, player_id, product, channel, stake_real_amount, stake_bonus_amount, status, payout_amount, placed_at_utc, settled_at_utc) VALUES
  (3,'REQ-BET-0003',1,'casino','app',50.00,0.00,'won',80.00,'2026-09-07 20:00:00','2026-09-07 20:00:05');
INSERT INTO casino_round_details (bet_id, game_id, provider_round_ref) VALUES (3,1,'PP-ROUND-000123');
INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, related_bet_id, idempotency_key, created_at_utc)
VALUES
  (8,1,1,'bet_stake','real',50.00,'debit',1160.00,1110.00,3,'bet_stake:3','2026-09-07 20:00:00'),
  (9,1,1,'bet_win','real',80.00,'credit',1110.00,1190.00,3,'bet_win:3','2026-09-07 20:00:05');

-- Retail: player 2 places a bet at a location.
INSERT INTO retail_locations (location_id, name, address_city) VALUES (1,'JSB Retail - Independence Ave','Windhoek');
INSERT INTO devices (device_id, fingerprint, device_type) VALUES (1,'POS-TERM-0007','pos_terminal');
INSERT INTO bets (bet_id, request_id, player_id, product, channel, stake_real_amount, stake_bonus_amount, status, payout_amount, placed_at_utc, settled_at_utc) VALUES
  (4,'REQ-BET-0004',2,'retail','retail',100.00,0.00,'lost',0.00,'2026-09-11 13:00:00','2026-09-11 16:00:00');
INSERT INTO retail_bet_details (bet_id, location_id, device_id, ticket_number) VALUES (4,1,1,'TCK-000456');
INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, related_bet_id, idempotency_key, created_at_utc)
VALUES
  (10,2,2,'bet_stake','real',100.00,'debit',500.00,400.00,4,'bet_stake:4','2026-09-11 13:00:00');

-- A correction, recorded the only way the ledger allows: append, never edit.
-- An agent keyed a 50.00 goodwill credit instead of 15.00 (row 11). Row 12 reverses it in full,
-- pointing at it; row 13 posts the right amount. Player 2's balance is 450.00 between 09:00 and
-- 09:30, which is what query (c) returns for that moment, and 415.00 afterwards.
INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, reversal_of_wallet_txn_id, reason, created_by, idempotency_key, created_at_utc)
VALUES
  (11,2,2,'manual_adjustment','real',50.00,'credit',400.00,450.00,NULL,'Goodwill credit: delayed withdrawal (ticket OPS-2291)','ops:agent_007','manual:OPS-2291','2026-09-12 09:00:00'),
  (12,2,2,'reversal','real',50.00,'debit',450.00,400.00,11,'Keyed 50.00 instead of 15.00 (ticket OPS-2291)','ops:supervisor_002','reversal:11','2026-09-12 09:30:00'),
  (13,2,2,'manual_adjustment','real',15.00,'credit',400.00,415.00,NULL,'Goodwill credit: delayed withdrawal, corrected (ticket OPS-2291)','ops:supervisor_002','manual:OPS-2291:v2','2026-09-12 09:31:00');

-- Player 2's bonus: granted, then forfeited unwagered (the whole bonus balance is removed).
INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, related_player_bonus_id, idempotency_key, created_at_utc)
VALUES
  (14,2,2,'bonus_credit','bonus',25.00,'credit',0,25.00,2,'bonus_grant:2','2026-09-15 09:05:00'),
  (15,2,2,'bonus_debit','bonus',25.00,'debit',25.00,0,2,'bonus_forfeit:2','2026-09-20 10:00:00');

-- Casino: player 1 loses a 300.00 round.
INSERT INTO bets (bet_id, request_id, player_id, product, channel, stake_real_amount, stake_bonus_amount, status, payout_amount, placed_at_utc, settled_at_utc) VALUES
  (5,'REQ-BET-0005',1,'casino','app',300.00,0.00,'lost',0.00,'2026-09-08 21:00:00','2026-09-08 21:00:04');
INSERT INTO casino_round_details (bet_id, game_id, provider_round_ref) VALUES (5,1,'PP-ROUND-000124');

-- Sportsbook accumulator: two legs, paid 10.00 from real money and 20.00 from player 3's bonus.
-- One leg loses, so the bet loses. The 30.00 stake counts towards the bonus rollover (odds >= 1.5).
INSERT INTO sports_events (event_id, sport, league, home_team, away_team, starts_at_utc) VALUES
  (2,'Football','Namibia Premier League','Tigers','Black Africa','2026-09-13 15:00:00'),
  (3,'Football','Namibia Premier League','Orlando Pirates','Civics','2026-09-13 17:00:00');
INSERT INTO bets (bet_id, request_id, player_id, product, channel, stake_real_amount, stake_bonus_amount, player_bonus_id, status, payout_amount, placed_at_utc, settled_at_utc) VALUES
  (6,'REQ-BET-0006',3,'sportsbook','app',10.00,20.00,1,'lost',0.00,'2026-09-13 12:00:00','2026-09-13 19:00:00');
INSERT INTO sports_bet_details (bet_id, bet_class, total_odds, leg_count, min_odds_rule_applied) VALUES
  (6,'accumulator',3.990,2,1.500);
INSERT INTO bet_legs (bet_id, event_id, market, selection, odds, leg_result) VALUES
  (6,2,'match_winner','Tigers',1.900,'won'),
  (6,3,'match_winner','Civics',2.100,'lost');
INSERT INTO bonus_rollover_events (player_bonus_id, bet_id, contribution_amount, created_at_utc) VALUES
  (1,6,30.00,'2026-09-13 19:00:00');

INSERT INTO wallet_transactions
  (wallet_txn_id, wallet_id, player_id, txn_type, balance_type, amount, direction,
   balance_before, balance_after, related_bet_id, idempotency_key, created_at_utc)
VALUES
  (16,1,1,'bet_stake','real',300.00,'debit',1190.00,890.00,5,'bet_stake:5','2026-09-08 21:00:00'),
  (17,3,3,'bet_stake','real',10.00,'debit',100.00,90.00,6,'bet_stake:6:real','2026-09-13 12:00:00'),
  (18,3,3,'bet_stake','bonus',20.00,'debit',30.00,10.00,6,'bet_stake:6:bonus','2026-09-13 12:00:00');
