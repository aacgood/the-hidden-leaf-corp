-- Tracks which courses each director has completed
CREATE TABLE director_education (
    id BIGSERIAL PRIMARY KEY,
    torn_user_id BIGINT NOT NULL REFERENCES directors(torn_user_id) ON DELETE CASCADE,
    course_id INT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (torn_user_id, course_id)
);

-- RLS
ALTER TABLE director_education ENABLE ROW LEVEL SECURITY;
