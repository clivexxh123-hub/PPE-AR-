SET NAMES utf8mb4;

UPDATE business_case_templates
SET
    name = '建筑普通作业标准方案',
    industry = '建筑',
    work_scene = '普通作业',
    description = '面向建筑工地日常巡检、物料搬运和现场协同的基础 PPE 视觉方案。',
    standard_reference = '标准依据待甲方合规负责人复核',
    selection_json = '{"productKeywords":["安全帽","反光衣"],"sceneKeywords":["建筑","工地"],"modelFilters":{"shotType":"full_body","view":"front","gender":"all"}}',
    print_rules_json = '{"logoTreatment":"preserve_brand_color","safeAreaRequired":true,"lockedAspectRatio":true}'
WHERE id = 'construction-general-v1' AND tenant_id = 'shoudun-ppe';

UPDATE business_case_templates
SET
    name = '建筑电工作业标准方案',
    industry = '建筑',
    work_scene = '电工作业',
    description = '面向临时用电、设备接线和电气巡检场景的 PPE 视觉方案。',
    standard_reference = '标准依据待甲方合规负责人复核',
    selection_json = '{"productKeywords":["安全帽","反光衣","劳保鞋"],"sceneKeywords":["电工","建筑"],"modelFilters":{"shotType":"full_body","view":"front","gender":"all"}}',
    print_rules_json = '{"logoTreatment":"preserve_brand_color","safeAreaRequired":true,"lockedAspectRatio":true}'
WHERE id = 'construction-electric-v1' AND tenant_id = 'shoudun-ppe';

UPDATE business_case_templates
SET
    name = '建筑有限空间作业方案',
    industry = '建筑',
    work_scene = '有限空间',
    description = '面向有限空间进入前检查和现场监护展示的 PPE 视觉方案。',
    standard_reference = '标准依据待甲方合规负责人复核',
    selection_json = '{"productKeywords":["安全帽","反光衣","手套"],"sceneKeywords":["有限空间","建筑"],"modelFilters":{"shotType":"full_body","view":"front","gender":"all"}}',
    print_rules_json = '{"logoTreatment":"preserve_brand_color","safeAreaRequired":true,"lockedAspectRatio":true}'
WHERE id = 'construction-confined-space-v1' AND tenant_id = 'shoudun-ppe';
