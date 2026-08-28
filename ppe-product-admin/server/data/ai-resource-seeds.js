const modelSeeds = [
    {
        id: "seed-model-male-front-half",
        model_key: "half_body-male-construction-01",
        model_name: "男性正面半身基础模特",
        gender: "male",
        shot_type: "half_body",
        view_type: "front",
        image_name: "male-halfbody-construction-01.png",
        image_url: "/uploads/models/male-halfbody-construction-01.png",
        remark: "正面站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类，供 PPE 生成使用"
    },
    {
        id: "seed-model-male-side-half",
        model_key: "half_body-male-construction-02",
        model_name: "男性微侧身半身基础模特",
        gender: "male",
        shot_type: "half_body",
        view_type: "slight_side",
        image_name: "male-halfbody-construction-02.png",
        image_url: "/uploads/models/male-halfbody-construction-02.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类"
    },
    {
        id: "seed-model-male-front-full",
        model_key: "full_body-male-front-camera-generated-v1",
        model_name: "男性正面全身基础模特",
        gender: "male",
        shot_type: "full_body",
        view_type: "front",
        image_name: "male-fullbody-front-generated-v1.png",
        image_url: "/uploads/models/male-fullbody-front-generated-v1.png",
        remark: "正面站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    },
    {
        id: "seed-model-male-side-full",
        model_key: "full_body-male-slight-side-generated-v1",
        model_name: "男性微侧身全身基础模特",
        gender: "male",
        shot_type: "full_body",
        view_type: "slight_side",
        image_name: "male-fullbody-slight-side-generated-v1.png",
        image_url: "/uploads/models/male-fullbody-slight-side-generated-v1.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    },
    {
        id: "seed-model-female-front-half",
        model_key: "half_body-female-construction-01",
        model_name: "女性正面半身基础模特",
        gender: "female",
        shot_type: "half_body",
        view_type: "front",
        image_name: "female-halfbody-construction-01.png",
        image_url: "/uploads/models/female-halfbody-construction-01.png",
        remark: "正面站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类，供 PPE 生成使用"
    },
    {
        id: "seed-model-female-side-half",
        model_key: "half_body-female-construction-02",
        model_name: "女性微侧身半身基础模特",
        gender: "female",
        shot_type: "half_body",
        view_type: "slight_side",
        image_name: "female-halfbody-construction-02.png",
        image_url: "/uploads/models/female-halfbody-construction-02.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手；无头盔、背心、手套及鞋类"
    },
    {
        id: "seed-model-female-front-full",
        model_key: "full_body-female-front-camera-generated-v1",
        model_name: "女性正面全身基础模特",
        gender: "female",
        shot_type: "full_body",
        view_type: "front",
        image_name: "female-fullbody-front-generated-v1.png",
        image_url: "/uploads/models/female-fullbody-front-generated-v1.png",
        remark: "正面站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    },
    {
        id: "seed-model-female-side-full",
        model_key: "full_body-female-slight-side-generated-v1",
        model_name: "女性微侧身全身基础模特",
        gender: "female",
        shot_type: "full_body",
        view_type: "slight_side",
        image_name: "female-fullbody-slight-side-generated-v1.png",
        image_url: "/uploads/models/female-fullbody-slight-side-generated-v1.png",
        remark: "约 25° 微侧身站直，纯色衬衫、长裤、裸手、赤脚；无头盔、背心、手套及鞋类"
    }
];

const sceneSeeds = [
    {
        id: "seed-scene-construction-01",
        scene_key: "建筑-城市混凝土工地",
        scene_name: "城市混凝土建筑工地",
        industry: "建筑",
        image_name: "construction-site-concrete-01.png",
        image_url: "/uploads/scenes/construction-site-concrete-01.png",
        remark: "白天、塔吊、混凝土主体结构，适合合成半身工装模特"
    },
    {
        id: "seed-scene-construction-02",
        scene_key: "建筑-城市钢结构工地",
        scene_name: "城市钢结构建筑工地",
        industry: "建筑",
        image_name: "construction-site-steel-02.png",
        image_url: "/uploads/scenes/construction-site-steel-02.png",
        remark: "白天、塔吊、钢结构主体，预留模特合成区域"
    }
];

module.exports = {
    modelSeeds,
    sceneSeeds
};
