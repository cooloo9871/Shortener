CREATE TABLE IF NOT EXISTS links (
    code        VARCHAR(10) PRIMARY KEY,
    target_url  TEXT        NOT NULL,
    hits        BIGINT      NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
