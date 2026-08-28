CREATE TABLE IF NOT EXISTS business_generation_record_deletions (
    job_id VARCHAR(128) PRIMARY KEY,
    deleted_by_user_id CHAR(36) NOT NULL,
    deleted_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_generation_record_deletions_actor_time (deleted_by_user_id, deleted_at),
    CONSTRAINT fk_generation_record_deletion_job
        FOREIGN KEY (job_id) REFERENCES business_generation_records(job_id),
    CONSTRAINT fk_generation_record_deletion_actor
        FOREIGN KEY (deleted_by_user_id) REFERENCES iam_users(id)
);
