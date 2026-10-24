-- Run once against the existing portfolio_chatbot database before deploying
-- this version. Existing project rows are assigned source_type = 'manual'.
ALTER TABLE projects
    ADD COLUMN category VARCHAR(50) NULL,
    ADD COLUMN github_url VARCHAR(500) NULL,
    ADD COLUMN deployed_url VARCHAR(500) NULL,
    ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'manual';

CREATE UNIQUE INDEX uq_projects_profile_github_url
    ON projects (profile_id, github_url);
