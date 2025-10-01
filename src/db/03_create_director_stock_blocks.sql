-- Tracks which stock blocks a director currently holds
CREATE TABLE director_stock_blocks (
    id BIGSERIAL PRIMARY KEY,
    torn_user_id BIGINT REFERENCES directors(torn_user_id) ON DELETE CASCADE,
    block_name TEXT NOT NULL,
    has_block BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (torn_user_id, block_name)
);

-- RLS
ALTER TABLE director_stock_blocks ENABLE ROW LEVEL SECURITY;