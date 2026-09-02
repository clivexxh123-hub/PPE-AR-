UPDATE iam_roles
SET name='超级管理员',
    description='平台全权限角色；可管理现有及后续新增功能'
WHERE id='admin';

INSERT INTO iam_org_units (id, parent_id, code, name, unit_type, active)
VALUES ('platform-management', NULL, 'platform-management', '平台管理', 'department', 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), active=VALUES(active);
