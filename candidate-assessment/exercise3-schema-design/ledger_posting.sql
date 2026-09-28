-- Exercise 3: the only way money moves. Load after ddl.sql:
--   mysql -u <user> -p jsb_platform < ledger_posting.sql
-- Tested by test_ledger_posting.py (evidence/ledger_posting_test.txt).
--
-- Why a procedure: a balance is only provable if every movement is a ledger row AND the cached balance
-- on wallets changes in the same transaction as that row. Application code is granted EXECUTE on these
-- two procedures, and no INSERT/UPDATE/DELETE on wallet_transactions or wallets.
--
-- post_wallet_txn guarantees, in one transaction:
--   1. Idempotency: the same idempotency_key twice returns the first row's id and posts nothing.
--   2. Serialisation: the wallet row is locked (SELECT ... FOR UPDATE) before reading the balance, so two
--      postings to one wallet can't both read the same balance_before.
--   3. The row carries balance_before and balance_after (CHECK ck_wtxn_balance_math holds them together),
--      and wallets.*_balance is set to balance_after, so the cache can never drift from the ledger.
--   4. No negative balance: a debit larger than the balance is refused (and wallets has a CHECK too).
-- reverse_wallet_txn records a correction: an equal and opposite row pointing at the original, which is
-- never edited. The unique key on reversal_of_wallet_txn_id means a row can be reversed once only.

USE jsb_platform;

DROP PROCEDURE IF EXISTS post_wallet_txn;
DROP PROCEDURE IF EXISTS reverse_wallet_txn;

DELIMITER $$

CREATE PROCEDURE post_wallet_txn(
    IN  p_idempotency_key VARCHAR(150),
    IN  p_wallet_id       BIGINT UNSIGNED,
    IN  p_txn_type        VARCHAR(30),
    IN  p_balance_type    VARCHAR(10),
    IN  p_direction       VARCHAR(10),
    IN  p_amount          DECIMAL(18,4),
    IN  p_related_kind    VARCHAR(20),       -- 'deposit' | 'withdrawal' | 'bet' | 'bonus' | NULL
    IN  p_related_id      BIGINT UNSIGNED,
    IN  p_reason          VARCHAR(255),
    IN  p_created_by      VARCHAR(100),
    IN  p_created_at_utc  DATETIME(6),
    OUT p_wallet_txn_id   BIGINT UNSIGNED)
proc: BEGIN
    DECLARE v_player_id BIGINT UNSIGNED;
    DECLARE v_before DECIMAL(18,4);
    DECLARE v_after  DECIMAL(18,4);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    IF p_txn_type = 'reversal' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'use reverse_wallet_txn for reversals';
    END IF;

    START TRANSACTION;

    -- Lock the wallet first: every posting to this wallet now waits its turn.
    SELECT player_id, IF(p_balance_type = 'real', real_balance, bonus_balance)
      INTO v_player_id, v_before
      FROM wallets WHERE wallet_id = p_wallet_id FOR UPDATE;
    IF v_player_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'unknown wallet';
    END IF;

    -- Replay of an event already posted: return the original row, change nothing.
    SELECT wallet_txn_id INTO p_wallet_txn_id
      FROM wallet_transactions WHERE idempotency_key = p_idempotency_key;
    IF p_wallet_txn_id IS NOT NULL THEN
        COMMIT;
        LEAVE proc;
    END IF;

    SET v_after = v_before + IF(p_direction = 'credit', p_amount, -p_amount);
    IF v_after < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'insufficient balance';
    END IF;

    INSERT INTO wallet_transactions
        (wallet_id, player_id, txn_type, balance_type, amount, direction, balance_before, balance_after,
         related_deposit_attempt_id, related_withdrawal_id, related_bet_id, related_player_bonus_id,
         reason, created_by, idempotency_key, created_at_utc)
    VALUES
        (p_wallet_id, v_player_id, p_txn_type, p_balance_type, p_amount, p_direction, v_before, v_after,
         IF(p_related_kind = 'deposit', p_related_id, NULL), IF(p_related_kind = 'withdrawal', p_related_id, NULL),
         IF(p_related_kind = 'bet', p_related_id, NULL),     IF(p_related_kind = 'bonus', p_related_id, NULL),
         p_reason, COALESCE(p_created_by, 'system'), p_idempotency_key, COALESCE(p_created_at_utc, UTC_TIMESTAMP(6)));
    SET p_wallet_txn_id = LAST_INSERT_ID();

    IF p_balance_type = 'real' THEN
        UPDATE wallets SET real_balance = v_after WHERE wallet_id = p_wallet_id;
    ELSE
        UPDATE wallets SET bonus_balance = v_after WHERE wallet_id = p_wallet_id;
    END IF;

    COMMIT;
END proc$$

CREATE PROCEDURE reverse_wallet_txn(
    IN  p_original_id    BIGINT UNSIGNED,
    IN  p_reason         VARCHAR(255),
    IN  p_created_by     VARCHAR(100),
    IN  p_created_at_utc DATETIME(6),
    OUT p_wallet_txn_id  BIGINT UNSIGNED)
proc: BEGIN
    DECLARE v_wallet_id BIGINT UNSIGNED;
    DECLARE v_player_id BIGINT UNSIGNED;
    DECLARE v_type VARCHAR(30);
    DECLARE v_balance_type VARCHAR(10);
    DECLARE v_direction VARCHAR(10);
    DECLARE v_amount DECIMAL(18,4);
    DECLARE v_before DECIMAL(18,4);
    DECLARE v_after  DECIMAL(18,4);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    IF p_reason IS NULL OR p_reason = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'a reversal needs a reason';
    END IF;

    START TRANSACTION;

    SELECT wallet_id, player_id, txn_type, balance_type, direction, amount
      INTO v_wallet_id, v_player_id, v_type, v_balance_type, v_direction, v_amount
      FROM wallet_transactions WHERE wallet_txn_id = p_original_id;
    IF v_wallet_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'unknown wallet transaction';
    END IF;
    IF v_type = 'reversal' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'a reversal is not reversed: post a new movement instead';
    END IF;

    SELECT IF(v_balance_type = 'real', real_balance, bonus_balance) INTO v_before
      FROM wallets WHERE wallet_id = v_wallet_id FOR UPDATE;

    -- Already reversed: return that reversal (idempotent), post nothing.
    SELECT wallet_txn_id INTO p_wallet_txn_id
      FROM wallet_transactions WHERE reversal_of_wallet_txn_id = p_original_id;
    IF p_wallet_txn_id IS NOT NULL THEN
        COMMIT;
        LEAVE proc;
    END IF;

    SET v_after = v_before + IF(v_direction = 'credit', -v_amount, v_amount);   -- the opposite direction
    IF v_after < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'insufficient balance to reverse';
    END IF;

    INSERT INTO wallet_transactions
        (wallet_id, player_id, txn_type, balance_type, amount, direction, balance_before, balance_after,
         reversal_of_wallet_txn_id, reason, created_by, idempotency_key, created_at_utc)
    VALUES
        (v_wallet_id, v_player_id, 'reversal', v_balance_type, v_amount,
         IF(v_direction = 'credit', 'debit', 'credit'), v_before, v_after,
         p_original_id, p_reason, COALESCE(p_created_by, 'system'), CONCAT('reversal:', p_original_id),
         COALESCE(p_created_at_utc, UTC_TIMESTAMP(6)));
    SET p_wallet_txn_id = LAST_INSERT_ID();

    IF v_balance_type = 'real' THEN
        UPDATE wallets SET real_balance = v_after WHERE wallet_id = v_wallet_id;
    ELSE
        UPDATE wallets SET bonus_balance = v_after WHERE wallet_id = v_wallet_id;
    END IF;

    COMMIT;
END proc$$

DELIMITER ;
