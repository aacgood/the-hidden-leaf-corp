sam local start-api
ngrok http 3000

```
cd src/discord_bot
pip install -r requirements.txt -t .
```

## Testing Locally

Install localstack (for SQS)

```sh
pip install localstack awscli-local
```

Setup the test environment:

Terminal 1:

```sh
docker run --rm -it -p 4566:4566 -p 4510-4559:4510-4559 localstack/localstack # "local" aws services on http://localhost:4566
```

Terminal 2:

```sh
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name register-queue
aws --endpoint-url=http://localhost:4566 sqs list-queues
sam build --use-container
sam local start-api --env-vars env.json
```

Terminal 3:

```sh
ngrok http 3000 # Use the output of this to feed into discord interactions url
```

# Database tables

Notes: 
- Once we have the director API Key most of these will be cron jobs behind the scenes.
- Dates will need to be in UTC (ie: TCT)
- Need error handling, what happens if the API call times out, how do we retry? message to discord?
- recruitment table to keep track?

## directors

Directors will supply their limited API keys via discord, stored in supabase

- torn_id    	(from profile: company.ID)
- director_name
- company_id 	(from profile: company.director)
- API_KEY	(supplied via discord slash command)
- education	(from users endpoint.  
			Business related courses: [1,2,3,4,5,6,7,8,9,10,11,12,13,22,28,88,100]
			Stock related: SYS, TCP, MSG, TGP, YAZ
- equity
- voting_rights


## distributions

historical required

- date
- amount


## employees

Hows the best way of dealing with this? point in time? or keep historical?

- torn_id	(populated from directors API Key)
- employee_name
- company_id 	(from profile endpoint)
- manual_labor	(from employees: company_employees.<ID>.manual_labor)
- intelligence	(from employees: company_employees.<ID>.intelligence)
- endurance	(from employees: company_employees.<ID>.endurance)
- addiction	(from employees: company_employees.<ID>.effectiveness.addiction)
- effectiveness (from employees: company_employees.<ID>.effectiveness.total)
- inactivity	(will need to see that in the logs)
- demerit	[26/09/2025, 10/10/2025,] > maybe its own table?


## revenue (per company)

What TCT does the game calculate this?

Will need to track over time

- date
- company_id		(from detailed: company_detailed.ID)
- daily_income		(from profile: company.daily_income)
- wages			    (from employees: a sum of company_employees.<ID>.wage)
- stock			    (from stock: a sum (company_stock.<NAME>.cost * on_order))
- advertising		(from detailed: company_detailed.advertising_budget)
- profit            (income - wages - stock - advertising)


## companies (from detailed endpoint)

Point in time?
Maybe the value forms part of the equity for buy in?

- company_id
- company_size
- staffroom_size
- storage_size
- storage_space
- current stars
- value
- positions available -> triggers auto post to positions-vacant channel?

## Resolutions

- id
- title
- text
- director_id
- votes_for
- votes_against
- resolution

## enterprise?

Maybe this is where we store buy in amounts by director and keep equity/voting rights calculated daily?


# Slash commands

`/ping`      > test connectivity
`/register`  > lets a director register their api key to the db
`/employee strike_add:name` > adds a strike against the specified employee
`/employee strike_remove:name` > Removes a strike against the specified employee
`/employee detail:name` > provides current company, job role, work stats, addiction levels, strikes
