CREATE TABLE IF NOT EXISTS iam_org_units (
    id VARCHAR(64) PRIMARY KEY,
    parent_id VARCHAR(64) NULL,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    unit_type ENUM('department', 'group') NOT NULL,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_iam_org_parent FOREIGN KEY (parent_id) REFERENCES iam_org_units(id)
);

CREATE TABLE IF NOT EXISTS iam_users (
    id CHAR(36) PRIMARY KEY,
    display_name VARCHAR(80) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    INDEX idx_iam_users_status (status)
);

CREATE TABLE IF NOT EXISTS iam_roles (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(255) NULL,
    system_role TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS iam_permissions (
    id VARCHAR(80) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255) NULL
);

CREATE TABLE IF NOT EXISTS iam_user_roles (
    user_id CHAR(36) NOT NULL,
    role_id VARCHAR(64) NOT NULL,
    assigned_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    assigned_by CHAR(36) NULL,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_iam_user_roles_user FOREIGN KEY (user_id) REFERENCES iam_users(id),
    CONSTRAINT fk_iam_user_roles_role FOREIGN KEY (role_id) REFERENCES iam_roles(id)
);

CREATE TABLE IF NOT EXISTS iam_role_permissions (
    role_id VARCHAR(64) NOT NULL,
    permission_id VARCHAR(80) NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_iam_role_permissions_role FOREIGN KEY (role_id) REFERENCES iam_roles(id),
    CONSTRAINT fk_iam_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES iam_permissions(id)
);

CREATE TABLE IF NOT EXISTS iam_user_org_memberships (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    org_unit_id VARCHAR(64) NOT NULL,
    valid_from DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    valid_to DATETIME(3) NULL,
    changed_by CHAR(36) NULL,
    INDEX idx_iam_membership_user_current (user_id, valid_to),
    INDEX idx_iam_membership_org_time (org_unit_id, valid_from, valid_to),
    CONSTRAINT fk_iam_membership_user FOREIGN KEY (user_id) REFERENCES iam_users(id),
    CONSTRAINT fk_iam_membership_org FOREIGN KEY (org_unit_id) REFERENCES iam_org_units(id)
);

CREATE TABLE IF NOT EXISTS iam_otp_challenges (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    purpose VARCHAR(32) NOT NULL DEFAULT 'login',
    code_hash CHAR(64) NOT NULL,
    expires_at DATETIME(3) NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    consumed_at DATETIME(3) NULL,
    requested_ip_hash CHAR(64) NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_iam_otp_user_created (user_id, created_at),
    INDEX idx_iam_otp_expiry (expires_at),
    CONSTRAINT fk_iam_otp_user FOREIGN KEY (user_id) REFERENCES iam_users(id)
);

CREATE TABLE IF NOT EXISTS iam_sessions (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    csrf_token_hash CHAR(64) NOT NULL,
    expires_at DATETIME(3) NOT NULL,
    last_seen_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    revoked_at DATETIME(3) NULL,
    created_ip_hash CHAR(64) NULL,
    user_agent VARCHAR(255) NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_iam_sessions_user_active (user_id, revoked_at, expires_at),
    CONSTRAINT fk_iam_sessions_user FOREIGN KEY (user_id) REFERENCES iam_users(id)
);

CREATE TABLE IF NOT EXISTS iam_audit_logs (
    id CHAR(36) PRIMARY KEY,
    actor_user_id CHAR(36) NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(80) NULL,
    target_id VARCHAR(100) NULL,
    metadata_json JSON NULL,
    ip_hash CHAR(64) NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_iam_audit_actor_time (actor_user_id, created_at),
    INDEX idx_iam_audit_target_time (target_type, target_id, created_at)
);

INSERT IGNORE INTO iam_permissions (id, name, description) VALUES
    ('system.manage', '系统与账号管理', '管理账号、组织、角色和系统配置'),
    ('catalog.manage', '公共资源管理', '维护产品、Logo、模特、场景和模板'),
    ('generation.use', 'AI 生图', '创建、查看和下载 AI 生成结果'),
    ('records.read_all', '读取全部业务记录', '查看其他员工的客户、方案和作图记录'),
    ('records.write_own', '维护本人业务记录', '创建、修改和删除本人业务记录'),
    ('dashboard.view_admin', '管理仪表盘', '查看管理员范围的业务统计');

INSERT IGNORE INTO iam_roles (id, name, description, system_role) VALUES
    ('admin', '管理员', '系统管理角色；最终权限矩阵仍需甲方确认', 1),
    ('sales', '普通员工', '共享读取、本人写入的销售员工角色', 1);

INSERT IGNORE INTO iam_role_permissions (role_id, permission_id) VALUES
    ('admin', 'system.manage'),
    ('admin', 'catalog.manage'),
    ('admin', 'generation.use'),
    ('admin', 'records.read_all'),
    ('admin', 'records.write_own'),
    ('admin', 'dashboard.view_admin'),
    ('sales', 'generation.use'),
    ('sales', 'records.read_all'),
    ('sales', 'records.write_own');

INSERT IGNORE INTO iam_org_units (id, parent_id, code, name, unit_type) VALUES
    ('jingshan-public', NULL, 'jingshan-public', '京山公域销售', 'department'),
    ('jingshan-private', NULL, 'jingshan-private', '京山私域销售', 'department'),
    ('wuhan-alibaba-private', NULL, 'wuhan-alibaba-private', '武汉阿里私域', 'department'),
    ('wuhan-sales', NULL, 'wuhan-sales', '武汉销售部', 'department');

INSERT IGNORE INTO iam_org_units (id, parent_id, code, name, unit_type) VALUES
    ('jingshan-public-presale-1', 'jingshan-public', 'jingshan-public-presale-1', '售前1组', 'group'),
    ('jingshan-public-presale-2', 'jingshan-public', 'jingshan-public-presale-2', '售前2组', 'group'),
    ('jingshan-public-presale-3', 'jingshan-public', 'jingshan-public-presale-3', '售前3组', 'group'),
    ('jingshan-public-presale-4', 'jingshan-public', 'jingshan-public-presale-4', '售前4组', 'group'),
    ('jingshan-public-related-sales', 'jingshan-public', 'jingshan-public-related-sales', '关联销售组', 'group'),
    ('jingshan-public-after-sales', 'jingshan-public', 'jingshan-public-after-sales', '售后组', 'group'),
    ('jingshan-private-1', 'jingshan-private', 'jingshan-private-1', '私域1组', 'group'),
    ('jingshan-private-2', 'jingshan-private', 'jingshan-private-2', '私域2组', 'group'),
    ('jingshan-private-3', 'jingshan-private', 'jingshan-private-3', '私域3组', 'group'),
    ('jingshan-private-4', 'jingshan-private', 'jingshan-private-4', '私域4组', 'group');
