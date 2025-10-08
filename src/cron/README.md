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

### Daily Company Stock

```sh
sam local invoke DailyCompanyStockCron --event src/cron/sample_event.json
```

### Daily Report Employees

```sh
sam local invoke DailyReportEmployeesCron --event src/cron/sample_event.json
```

### Daily Report Stock

```sh
sam local invoke DailyReportStockCron --event src/cron/sample_event.json
```



## SAM Deployment

These are setup as a cron at 17:00 UTC.