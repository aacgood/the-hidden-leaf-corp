# README

## Testing locally

From the project parent folder (where template.yaml resides)

### Populate Director Education Cron

```sh
sam local invoke PopulateDirectorEducationCron --event src/cron/sample_event.json
```

### Populate Director Stock Blocks Cron

```sh
sam local invoke PopulateDirectorStockBlocksCron --event src/cron/sample_event.json
```

### Populate Employees

```sh
sam local invoke PopulateEmployeesCron --event src/cron/sample_event.json
```

### Populate Company

```sh
sam local invoke PopulateCompanyCron --event src/cron/sample_event.json
```

### Populate Company Stock

Purpose: Read TORN API and get the stock figures as a point in time and update the db
Filename: `src/cron/populate_company_stock.py`
Table: `company_stock_daily`

```sh
sam local invoke PopulateCompanyStockCron --event src/cron/sample_event.json
```

### Populate Company Financials

Purpose: Read TORN API and get the stock figures as a point in time and update the db
Filename: `src/cron/populate_company_financials.py`
Table: `company_financials`

```sh
sam local invoke PopulateCompanyFinancialsCron --event src/cron/sample_event.json
```

### Daily Report Employees

```sh
sam local invoke DailyReportEmployeesCron --event src/cron/sample_event.json
```

### Daily Report Stock

```sh
sam local invoke DailyReportStockCron --event src/cron/sample_event.json
```

### Daily Report Company (Long Form)

```sh
sam local invoke DailyReportCompanyLongCron --event src/cron/sample_event.json
```

### Weekly Report Company Aggregated (Long Form)

```sh
sam local invoke WeeklyReportCompanyLongCron --event src/cron/sample_event.json
```

### Weekly Report Company Invetments Aggregated (Long Form)

```sh
sam local invoke WeeklyReportCompanyInvestmentsLongCron --event src/cron/sample_event.json
```

### Daily Report All Employees (Long Form)

```sh
sam local invoke DailyReportAllEmployeesLongCron --event src/cron/sample_event.json
```

### Weekly Report Directors Stock Blocks (Long Form)

```sh
sam local invoke WeeklyReportDirectorsStockBlocksLongCron --event src/cron/sample_event.json
```


### Weekly Company Info Post Updater 

```sh
sam local invoke WeeklyCompanyInfoPostUpdaterCron --event src/cron/sample_event.json
```

## SAM Deployment

These are setup as a cron at 17:00 UTC.