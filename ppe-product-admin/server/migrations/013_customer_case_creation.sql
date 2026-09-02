SET NAMES utf8mb4;

ALTER TABLE business_case_templates
    ADD COLUMN source_type ENUM('standard', 'customer') NOT NULL DEFAULT 'standard' AFTER tenant_id,
    ADD COLUMN customer_id CHAR(36) NULL AFTER source_type,
    ADD COLUMN customer_name_at_create VARCHAR(120) NULL AFTER customer_id,
    ADD COLUMN created_by_user_id CHAR(36) NULL AFTER customer_name_at_create,
    ADD COLUMN created_by_user_name_at_create VARCHAR(80) NULL AFTER created_by_user_id,
    DROP INDEX uk_case_templates_name_version,
    ADD INDEX idx_case_templates_name_version (tenant_id, name, version_no),
    ADD INDEX idx_case_templates_customer_time (customer_id, created_at),
    ADD INDEX idx_case_templates_creator_time (created_by_user_id, created_at),
    ADD CONSTRAINT fk_case_templates_customer
        FOREIGN KEY (customer_id) REFERENCES business_customers(id);

UPDATE business_case_templates
SET preview_url = '/case-previews/construction-general.png'
WHERE id = 'construction-general-v1' AND tenant_id = 'shoudun-ppe';

UPDATE business_case_templates
SET preview_url = '/case-previews/construction-electric.png'
WHERE id = 'construction-electric-v1' AND tenant_id = 'shoudun-ppe';

UPDATE business_case_templates
SET preview_url = '/case-previews/construction-confined-space.png'
WHERE id = 'construction-confined-space-v1' AND tenant_id = 'shoudun-ppe';
