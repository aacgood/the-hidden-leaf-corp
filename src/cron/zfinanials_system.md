https://chatgpt.com/c/68e7426a-c110-8321-8c0a-08c3407afa59
Perfect — here’s a quick, high-level overview tying everything together.

🗃️ Database Tables
1. company_financials

Daily snapshots of company performance.
Purpose: Source-of-truth for all profit/loss calculations.

| Column       | Type   | Description                                           |
| ------------ | ------ | ----------------------------------------------------- |
| id           | SERIAL | Primary key                                           |
| company_id   | INT    | Torn company ID                                       |
| capture_date | DATE   | The day this record applies to                        |
| revenue      | BIGINT | From newsfeed or `sold_worth` sum                     |
| stock_cost   | BIGINT | Sum of `(on_order * cost)`                            |
| wages        | BIGINT | Sum of `employees.wage`                               |
| advertising  | BIGINT | Daily advertising budget                              |
| profit       | BIGINT | Derived: `revenue - stock_cost - wages - advertising` |

2. company_donations

Tracks capital injections and repayments by donors.

| Column     | Type      | Description                               |
| ---------- | --------- | ----------------------------------------- |
| id         | SERIAL    | Primary key                               |
| company_id | INT       | Related company                           |
| donor_id   | BIGINT    | Torn player ID of donor                   |
| amount     | BIGINT    | Positive = donation, Negative = repayment |
| timestamp  | TIMESTAMP | When the donation/reimbursement occurred  |
| note       | TEXT      | Optional comment                          |

3. company_profit_settlements

Aggregated profit statements per donor per period.

| Column         | Type      | Description                                 |
| -------------- | --------- | ------------------------------------------- |
| id             | SERIAL    | Primary key                                 |
| company_id     | INT       | Related company                             |
| donor_id       | BIGINT    | Donor/owner                                 |
| start_date     | DATE      | Period start                                |
| end_date       | DATE      | Period end                                  |
| profit_amount  | BIGINT    | Aggregated profit from `company_financials` |
| points_awarded | INT       | Optional reward points (e.g. profit ÷ 100k) |
| settled        | BOOLEAN   | Whether the payout/acknowledgement occurred |
| created_at     | TIMESTAMP | When this summary was generated             |


🤖 Discord Slash Commands
| Command                               | Purpose                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| `/company summary`                    | Show today’s revenue, costs, profit.                               |
| `/company donor add <donor> <amount>` | Record a new donation or repayment.                                |
| `/company donors`                     | List all donors and their balances.                                |
| `/company profit monthly`             | Generate or view monthly profit summary.                           |
| `/company bill send <month>`          | Send the “monthly bill” to all donors via DM or post in a channel. |
| `/company financials graph [period]`  | (optional) Graph daily profit/loss trends.                         |

🔄 Workflow Summary
Daily

Lambda Job:

Calls Torn endpoints (news, employees, stock, detailed).

Calculates revenue, stock_cost, wages, advertising, and profit.

Inserts/updates company_financials for today.

Ongoing

Manual or automatic donation tracking:

Use /company donor add to log capital injections or repayments.

Monthly (or Weekly)

Profit Settlement Script:

Aggregates all profit from company_financials within the period.

For each donor (usually 1), creates an entry in company_profit_settlements.

Calculates optional points_awarded.

Posts a summary via /company bill send.

Optional Repayment:

Director “pays” profits back via in-game transaction.

Logged as a negative amount in company_donations.

Marks corresponding company_profit_settlements.settled = TRUE.

🧭 TL;DR Summary
Layer	Purpose
company_financials	Daily data capture (operational P&L)
company_donations	Capital inflows/outflows (funding ledger)
company_profit_settlements	Periodic summary for billing & points
Discord Commands	Manage donors, view performance, generate bills
Lambda Jobs	Automate daily imports and monthly rollups

Would you like me to include a fourth table — company_donor_balances — that automatically keeps a running balance (donations minus repayments minus profits returned)? It’s optional but makes reporting simpler.