CREATE TABLE IF NOT EXISTS iam_password_credentials (
    user_id CHAR(36) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    password_changed_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    failed_attempts INT NOT NULL DEFAULT 0,
    locked_until DATETIME(3) NULL,
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_iam_password_user FOREIGN KEY (user_id) REFERENCES iam_users(id) ON DELETE CASCADE
);

UPDATE iam_roles
SET name='普通账号',
    description='基础业务操作、读取全员记录、仅维护本人业务数据；不做小组数据隔离'
WHERE id='sales';

INSERT IGNORE INTO iam_role_permissions (role_id, permission_id) VALUES
    ('sales', 'generation.use'),
    ('sales', 'records.read_all'),
    ('sales', 'records.write_own');

INSERT INTO iam_org_units (id, parent_id, code, name, unit_type, active) VALUES
    ('jingshan-public', NULL, 'jingshan-public', '京山公域销售', 'department', 1),
    ('jingshan-private', NULL, 'jingshan-private', '京山私域销售', 'department', 1),
    ('wuhan-alibaba-private', NULL, 'wuhan-alibaba-private', '武汉阿里私域', 'department', 1),
    ('wuhan-sales', NULL, 'wuhan-sales', '武汉销售部', 'department', 1),
    ('platform-management', NULL, 'platform-management', '平台管理', 'department', 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), active=VALUES(active);

INSERT INTO iam_org_units (id, parent_id, code, name, unit_type, active) VALUES
    ('jingshan-public-presale-1', 'jingshan-public', 'jingshan-public-presale-1', '售前1组', 'group', 1),
    ('jingshan-public-presale-2', 'jingshan-public', 'jingshan-public-presale-2', '售前2组', 'group', 1),
    ('jingshan-public-presale-3', 'jingshan-public', 'jingshan-public-presale-3', '售前3组', 'group', 1),
    ('jingshan-public-presale-4', 'jingshan-public', 'jingshan-public-presale-4', '售前4组', 'group', 1),
    ('jingshan-public-related-sales', 'jingshan-public', 'jingshan-public-related-sales', '关联销售组', 'group', 1),
    ('jingshan-public-after-sales', 'jingshan-public', 'jingshan-public-after-sales', '售后组', 'group', 1),
    ('jingshan-private-1', 'jingshan-private', 'jingshan-private-1', '私域1组', 'group', 1),
    ('jingshan-private-2', 'jingshan-private', 'jingshan-private-2', '私域2组', 'group', 1),
    ('jingshan-private-3', 'jingshan-private', 'jingshan-private-3', '私域3组', 'group', 1),
    ('jingshan-private-4', 'jingshan-private', 'jingshan-private-4', '私域4组', 'group', 1)
ON DUPLICATE KEY UPDATE parent_id=VALUES(parent_id), name=VALUES(name), active=VALUES(active);
