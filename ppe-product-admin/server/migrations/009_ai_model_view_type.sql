ALTER TABLE ai_model_assets
    ADD COLUMN view_type ENUM('front', 'slight_side') NOT NULL DEFAULT 'front' AFTER shot_type;

UPDATE ai_model_assets
SET view_type = 'slight_side'
WHERE LOWER(model_key) REGEXP 'slight[-_ ]?side|three[-_ ]?quarter'
   OR remark LIKE '%微侧%'
   OR remark LIKE '%侧前方%';

CREATE INDEX idx_ai_model_assets_view_type
    ON ai_model_assets (view_type);
