-- WITHDRAWN. Do not use.
-- This script dropped 45 named tables from jsb_assessment with foreign-key checks off.
-- Codex review QA-01 showed that breaks jsb_assessment_pii.player_identity, which
-- referenced jsb_assessment.player from another database.
-- The old builds were instead removed directly on the user's MariaDB by Codex, with a
-- full backup, after checking that no other database referenced them (14 jsb_
-- databases, 205 tables; see CODEX_REVIEW.md).
-- To set up this project on an empty server, run 01_load_submission_tables.sql.
SELECT 'withdrawn: see CODEX_REVIEW.md QA-01' AS note;
