-- Exercise 2: Incremental, restartable API ingestion — MySQL 8.0 schema
USE jsb_assessment;

-- The target table: one row per provider transaction, upserted (never duplicated).
DROP TABLE IF EXISTS transactions;
CREATE TABLE transactions (
    id              VARCHAR(20)     NOT NULL PRIMARY KEY,   -- provider's id, e.g. TX000123
    player_id       VARCHAR(20)     NULL,                   -- provider sometimes sends null
    type            VARCHAR(20)     NOT NULL,
    amount          DECIMAL(14,2)   NOT NULL,
    currency        CHAR(3)         NOT NULL,
    status          VARCHAR(20)     NOT NULL,
    updated_at      DATETIME(0)     NOT NULL,                -- provider's updated_at (UTC)
    source_system   VARCHAR(20)     NOT NULL DEFAULT 'mock_provider',
    ingested_at     DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                     ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_txn_updated (updated_at, id)
) ENGINE=InnoDB;

-- Single-row checkpoint: the opaque cursor to resume from. Updated in the SAME
-- transaction as the batch of rows it applies to, so a kill at any point leaves
-- the checkpoint and the data consistent with each other.
DROP TABLE IF EXISTS ingest_checkpoint;
CREATE TABLE ingest_checkpoint (
    source_system   VARCHAR(20)     NOT NULL PRIMARY KEY,
    next_cursor     VARCHAR(255)    NULL,        -- opaque cursor to send on the next call; NULL = start from the beginning
    last_updated_at VARCHAR(40)     NULL,         -- last updated_at we have fully processed, for visibility/alerting
    last_id         VARCHAR(20)     NULL,
    updated_at      DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;

-- One row per ingestion run: what monitoring reads.
DROP TABLE IF EXISTS ingest_runs;
CREATE TABLE ingest_runs (
    run_id          INT AUTO_INCREMENT PRIMARY KEY,
    source_system   VARCHAR(20)     NOT NULL,
    started_at      DATETIME(6)     NOT NULL,
    finished_at     DATETIME(6)     NULL,
    status          VARCHAR(20)     NOT NULL,      -- RUNNING | COMPLETED | FAILED | INTERRUPTED | ABANDONED
    pages_fetched   INT             NOT NULL DEFAULT 0,
    rows_upserted   INT             NOT NULL DEFAULT 0,   -- valid records processed (new + changed + unchanged)
    rows_new        INT             NOT NULL DEFAULT 0,   -- ids not in the table before
    rows_changed    INT             NOT NULL DEFAULT 0,   -- ids whose updated_at moved forward
    rows_unchanged  INT             NOT NULL DEFAULT 0,   -- re-read with the same updated_at (boundary / in-page repeat)
    rows_rejected   INT             NOT NULL DEFAULT 0,
    rate_limit_hits INT             NOT NULL DEFAULT 0,
    server_error_hits INT           NOT NULL DEFAULT 0,
    final_cursor    VARCHAR(255)    NULL,
    error_message   TEXT            NULL,
    KEY ix_runs_source_status (source_system, status, started_at)   -- stale-run check, abandoned marking
) ENGINE=InnoDB;

-- Bad records are never dropped silently: raw payload + reason, for replay/review.
-- One row per distinct bad payload: seeing the same bad record again (a restart re-reads
-- the boundary page) updates last_seen_run_id instead of adding a duplicate row.
DROP TABLE IF EXISTS ingest_rejects;
CREATE TABLE ingest_rejects (
    reject_id       INT AUTO_INCREMENT PRIMARY KEY,
    run_id          INT             NOT NULL,                -- run that first saw it
    last_seen_run_id INT            NULL,
    record_id       VARCHAR(20)     NULL,
    reason          VARCHAR(255)    NOT NULL,
    raw_payload     JSON            NOT NULL,
    payload_sha256  CHAR(64)        AS (SHA2(raw_payload, 256)) STORED,
    rejected_at     DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY ux_reject_payload (payload_sha256),
    KEY ix_reject_run (run_id),
    KEY ix_reject_record (record_id)
) ENGINE=InnoDB;
