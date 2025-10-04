CREATE TABLE discord_company_channels (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL,
    channel_name TEXT NOT NULL, 
    discord_channel_id BIGINT NOT NULL,
    UNIQUE (company_id, channel_name)
);


ALTER TABLE discord_company_channels ENABLE ROW LEVEL SECURITY;

-- company_id → ties the channel to the Torn company.
-- channel_name → purely descriptive at this time
-- discord_channel_id → the actual Discord channel ID where messages will go.
-- UNIQUE (company_id, channel_type) ensures only one channel per type per company.