-- Exercise 1: Payment gateway reconciliation
-- Schema for the two source extracts, loaded as-is (no cleansing on the way in).
-- Tool used: MySQL 8.0

CREATE DATABASE IF NOT EXISTS jsb_assessment CHARACTER SET utf8mb4;
USE jsb_assessment;

DROP TABLE IF EXISTS internal_deposits;
CREATE TABLE internal_deposits (
    deposit_id      VARCHAR(20)     NOT NULL,
    player_id       VARCHAR(20)     NOT NULL,
    created_at      DATETIME        NOT NULL,
    amount          DECIMAL(14,2)   NOT NULL,
    currency        CHAR(3)         NOT NULL,
    method          VARCHAR(30)     NOT NULL,
    gateway_ref     VARCHAR(30)     NOT NULL,
    status          VARCHAR(10)     NOT NULL,   -- SUCCESS | FAILED
    -- normalised reference for matching: upper-case, letters/digits only.
    -- The gateway file is observed to send the same reference with different
    -- punctuation/case (GW-000102, GW000102, gw-000102, ' GW-000102 ').
    gateway_ref_norm VARCHAR(30) GENERATED ALWAYS AS
        (UPPER(REGEXP_REPLACE(gateway_ref, '[^A-Za-z0-9]', ''))) STORED,
    PRIMARY KEY (deposit_id),
    KEY ix_dep_ref_norm (gateway_ref_norm),
    KEY ix_dep_player (player_id)
) ENGINE=InnoDB;

DROP TABLE IF EXISTS gateway_settlement;
CREATE TABLE gateway_settlement (
    row_id          INT AUTO_INCREMENT PRIMARY KEY,  -- surrogate: source has no unique key (dup merchant_ref exists)
    gateway_txn_id  VARCHAR(20)     NOT NULL,
    merchant_ref    VARCHAR(30)     NOT NULL,
    settled_at      DATETIME        NOT NULL,
    gross_amount    DECIMAL(14,2)   NOT NULL,
    fee             DECIMAL(14,2)   NOT NULL,
    net_amount      DECIMAL(14,2)   NOT NULL,
    currency        CHAR(3)         NOT NULL,
    status          VARCHAR(10)     NOT NULL,   -- SETTLED | REVERSED
    merchant_ref_norm VARCHAR(30) GENERATED ALWAYS AS
        (UPPER(REGEXP_REPLACE(merchant_ref, '[^A-Za-z0-9]', ''))) STORED,
    -- The file's genuine duplicates (one txn reported twice) differ in settled_at and are kept, since
    -- reporting them is the point. An identical row twice would mean the file was loaded twice.
    UNIQUE KEY ux_gw_txn_settled (gateway_txn_id, settled_at),
    KEY ix_gw_ref_norm (merchant_ref_norm)
) ENGINE=InnoDB;
