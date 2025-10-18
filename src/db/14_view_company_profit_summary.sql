CREATE VIEW company_profit_summary AS
SELECT
    company_id,
    SUM(total_invested) AS total_invested,
    SUM(total_returned) AS total_returned,
    SUM(total_returned) - SUM(total_invested) AS company_profit
FROM company_investments
GROUP BY company_id;
