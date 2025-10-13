-- ============================================================
-- Function: update_company_donations_from_transaction
-- ============================================================
CREATE OR REPLACE FUNCTION update_company_donations_from_transaction()
RETURNS TRIGGER AS $$
DECLARE
    master_row company_donations%ROWTYPE;
BEGIN
    -- Only process confirmed transactions
    IF NEW.status <> 'confirmed' THEN
        RETURN NEW;
    END IF;

    -- Try to find the master donation row
    SELECT *
    INTO master_row
    FROM company_donations
    WHERE id = NEW.donation_id;

    -- If master row does not exist, auto-create
    IF NOT FOUND THEN
        INSERT INTO company_donations (id, company_id, donator_id, donator_name, created_at)
        SELECT NEW.donation_id, cd.company_id, NEW.initiated_by::BIGINT, NEW.initiated_by::TEXT, NOW()
        FROM company cd
        WHERE cd.company_id = (SELECT company_id FROM company_donations WHERE id = NEW.donation_id)
        RETURNING * INTO master_row;

        -- Fallback if SELECT fails
        IF NOT FOUND THEN
            RAISE NOTICE 'Master donation row missing and cannot be auto-created.';
            RETURN NEW;
        END IF;
    END IF;

    -- Update totals
    UPDATE company_donations
    SET amount_donated = COALESCE(
            (SELECT SUM(amount)
             FROM company_donation_transactions
             WHERE donation_id = master_row.id
               AND transaction_type = 'donation'
               AND status = 'confirmed'), 0),
        amount_repaid = COALESCE(
            (SELECT SUM(amount)
             FROM company_donation_transactions
             WHERE donation_id = master_row.id
               AND transaction_type = 'repayment'
               AND status = 'confirmed'), 0),
        updated_at = NOW()
    WHERE id = master_row.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- Trigger
-- ============================================================
DROP TRIGGER IF EXISTS trg_update_company_donations ON company_donation_transactions;

CREATE TRIGGER trg_update_company_donations
AFTER INSERT OR UPDATE ON company_donation_transactions
FOR EACH ROW
EXECUTE FUNCTION update_company_donations_from_transaction();
