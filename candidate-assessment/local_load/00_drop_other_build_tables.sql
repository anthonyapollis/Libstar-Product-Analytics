-- Remove the 45 tables another build left in jsb_assessment.
-- Drops ONLY the names listed below (taken from your own table listing), whether each is a
-- table or a view. This submission's tables are not in the list, and nothing outside
-- jsb_assessment is touched. Run it once, then run 01_load_submission_tables.sql.
-- Optional backup first (XAMPP):
--   C:\xampp\mysql\bin\mysqldump.exe -u root jsb_assessment > jsb_assessment_backup.sql
USE jsb_assessment;
SET SESSION group_concat_max_len = 100000;
SET FOREIGN_KEY_CHECKS = 0;

DROP TEMPORARY TABLE IF EXISTS other_build_objects;
CREATE TEMPORARY TABLE other_build_objects AS
SELECT table_name AS name, table_type AS kind
FROM information_schema.tables
WHERE table_schema = 'jsb_assessment'
  AND table_name IN (
    'affiliate',
    'api_quarantine',
    'api_raw_versions',
    'api_transactions',
    'bet',
    'bet_funding',
    'bet_settlement',
    'bonus_grant',
    'bonus_outcome_event',
    'bonus_progress_event',
    'campaign',
    'campaign_version',
    'casino_round',
    'dim_campaign',
    'dim_player_history',
    'dim_product',
    'fct_reconciliation',
    'fct_revenue',
    'game',
    'ingestion_pages',
    'ingestion_runs',
    'ingestion_state',
    'journal',
    'journal_entry',
    'ledger_account',
    'mart_api_activity',
    'mart_monthly_ngr',
    'payment_attempt',
    'payment_status_event',
    'player',
    'player_state_history',
    'player_tag_history',
    'provider',
    'raw_gateway_settlement',
    'raw_internal_deposits',
    'reference_candidate_links',
    'retail_device',
    'retail_location',
    'revenue_event',
    'sports_leg',
    'sports_leg_result',
    'stg_api_transactions',
    'stg_gateway_settlement',
    'stg_internal_deposits',
    'tag'
  );

-- What will be dropped
SELECT kind, COUNT(*) AS objects FROM other_build_objects GROUP BY kind;

SET @views = (SELECT GROUP_CONCAT(CONCAT('`', name, '`')) FROM other_build_objects WHERE kind = 'VIEW');
SET @sql = IF(@views IS NULL, 'DO 0', CONCAT('DROP VIEW IF EXISTS ', @views));
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @tables = (SELECT GROUP_CONCAT(CONCAT('`', name, '`')) FROM other_build_objects WHERE kind <> 'VIEW');
SET @sql = IF(@tables IS NULL, 'DO 0', CONCAT('DROP TABLE IF EXISTS ', @tables));
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET FOREIGN_KEY_CHECKS = 1;
DROP TEMPORARY TABLE other_build_objects;

-- What is left in jsb_assessment (after the load script: this submission's tables only)
SELECT table_name, table_type FROM information_schema.tables
WHERE table_schema = 'jsb_assessment' ORDER BY table_name;
