-- ============================================================
--  Function: update_company_investments_from_transaction
--  Purpose: Auto-update totals in company_investments when
--           confirmed transactions are inserted or updated
-- ============================================================

CREATE OR REPLACE FUNCTION update_company_investments_from_transaction()
RETURNS TRIGGER AS $$
BEGIN
    -- Only process confirmed transactions
    IF NEW.status <> 'confirmed' THEN
        RETURN NEW;
    END IF;

    UPDATE company_investments
    SET 
        total_invested = COALESCE((
            SELECT SUM(amount)
            FROM company_investment_transactions
            WHERE investment_id = NEW.investment_id
              AND transaction_type = 'investment'
              AND status = 'confirmed'
        ), 0),
        total_returned = COALESCE((
            SELECT SUM(amount)
            FROM company_investment_transactions
            WHERE investment_id = NEW.investment_id
              AND transaction_type = 'return'
              AND status = 'confirmed'
        ), 0),
        updated_at = NOW()
    WHERE id = NEW.investment_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_company_investments 
    ON company_investment_transactions;

CREATE TRIGGER trg_update_company_investments
AFTER INSERT OR UPDATE
ON company_investment_transactions
FOR EACH ROW
EXECUTE FUNCTION update_company_investments_from_transaction();
