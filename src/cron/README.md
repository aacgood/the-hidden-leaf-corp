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