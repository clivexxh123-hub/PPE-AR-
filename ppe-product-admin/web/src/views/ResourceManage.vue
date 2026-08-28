<template>
  <div class="resource-page">
    <section class="resource-hero">
      <div>
        <span class="eyebrow">AI RESOURCE LIBRARY</span>
        <h2>资源管理</h2>
        <p>统一维护生成任务使用的 Logo、模特与行业场景。</p>
      </div>

      <div class="resource-total">
        <strong>{{ logos.length + models.length + scenes.length }}</strong>
        <span>项可用资源</span>
      </div>
    </section>

    <nav class="resource-tabs" aria-label="资源类型">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="{ active: activeTab === tab.key }"
        @click="selectTab(tab.key)"
      >
        <span>{{ tab.icon }}</span>
        {{ tab.label }}
        <b>{{ tab.count }}</b>
      </button>
    </nav>

    <section v-if="activeTab === 'logos'" class="resource-panel">
      <div class="panel-heading">
        <div>
          <span class="panel-index">01</span>
          <h3>Logo 资源</h3>
          <p>按地区和企业维护印制 Logo。</p>
        </div>
      </div>

      <div class="resource-workspace">
        <form class="upload-card" @submit.prevent="uploadLogo">
          <h4>添加 Logo</h4>

          <label>
            地区
            <input v-model.trim="logoForm.region" placeholder="例如：北京" />
          </label>

          <label>
            公司名称
            <input v-model.trim="logoForm.company_name" placeholder="例如：国家电网" />
          </label>

          <label>
            备注
            <input v-model.trim="logoForm.remark" placeholder="可选" />
          </label>

          <label class="file-field">
            Logo 图片
            <input type="file" accept="image/*" @change="selectFile('logo', $event)" />
          </label>

          <div v-if="previews.logo" class="upload-preview logo-preview">
            <img :src="previews.logo" alt="Logo 上传预览" />
          </div>

          <button class="primary-button" type="submit" :disabled="uploading.logo">
            {{ uploading.logo ? "正在保存..." : "保存 Logo" }}
          </button>
        </form>

        <div class="library-card">
          <div class="library-heading">
            <div>
              <h4>已有 Logo</h4>
              <p>{{ logos.length }} 项</p>
            </div>
          </div>

          <div v-if="logos.length" class="asset-grid logo-grid">
            <article v-for="item in logos" :key="item.id" class="asset-card">
              <div class="asset-image contain-image">
                <img
                  v-if="item.image"
                  :src="item.image"
                  :alt="item.name"
                  @error="item.image = ''"
                />
                <span v-else>LOGO</span>
              </div>
              <div class="asset-body">
                <span class="asset-tag">{{ item.region || "未分类" }}</span>
                <h5>{{ item.company_name }}</h5>
                <p>{{ item.name }}</p>
              </div>
            </article>
          </div>

          <div v-else class="empty-library">暂时没有 Logo 资源</div>
        </div>
      </div>
    </section>

    <section v-else-if="activeTab === 'models'" class="resource-panel">
      <div class="panel-heading">
        <div>
          <span class="panel-index">02</span>
          <h3>模特资源</h3>
          <p>按全身/半身、正面/微侧身和男性/女性维护无 PPE 模特参考图。</p>
        </div>
      </div>

      <div v-if="!availability.models" class="deployment-note">
        模特接口已在本地代码中完成，部署后即可保存到服务器数据库。
      </div>

      <div class="resource-workspace">
        <form class="upload-card" @submit.prevent="uploadModel">
          <h4>添加模特</h4>

          <label>
            模特名称
            <input v-model.trim="modelForm.model_name" placeholder="例如：男性工装模特 01" />
          </label>

          <label>
            性别分类
            <select v-model="modelForm.gender">
              <option value="male">男性</option>
              <option value="female">女性</option>
              <option value="unisex">通用</option>
            </select>
          </label>

          <label>
            构图分类
            <select v-model="modelForm.shot_type">
              <option value="full_body">全身</option>
              <option value="half_body">半身</option>
            </select>
          </label>

          <label>
            人物视角
            <select v-model="modelForm.view_type">
              <option value="front">正面</option>
              <option value="slight_side">微侧身</option>
            </select>
          </label>

          <label>
            备注
            <input v-model.trim="modelForm.remark" placeholder="姿态、服装等说明" />
          </label>

          <label class="file-field">
            模特图片
            <input type="file" accept="image/*" @change="selectFile('model', $event)" />
          </label>

          <div v-if="previews.model" class="upload-preview portrait-preview">
            <img :src="previews.model" alt="模特上传预览" />
          </div>

          <button class="primary-button" type="submit" :disabled="uploading.model || !availability.models">
            {{ uploading.model ? "正在保存..." : "保存模特" }}
          </button>
        </form>

        <div class="library-card">
          <div class="library-heading">
            <div>
              <h4>已有模特</h4>
              <p>{{ models.length }} 项</p>
            </div>

            <div class="filter-groups">
              <div class="filter-group">
                <span>性别</span>
                <div class="filter-pills">
                  <button
                    v-for="filter in genderFilters"
                    :key="filter.value"
                    type="button"
                    :class="{ active: modelGenderFilter === filter.value }"
                    @click="modelGenderFilter = filter.value"
                  >
                    {{ filter.label }}
                  </button>
                </div>
              </div>

              <div class="filter-group">
                <span>构图</span>
                <div class="filter-pills">
                  <button
                    v-for="filter in shotTypeFilters"
                    :key="filter.value"
                    type="button"
                    :class="{ active: modelShotFilter === filter.value }"
                    @click="modelShotFilter = filter.value"
                  >
                    {{ filter.label }}
                  </button>
                </div>
              </div>

              <div class="filter-group">
                <span>视角</span>
                <div class="filter-pills">
                  <button
                    v-for="filter in viewTypeFilters"
                    :key="filter.value"
                    type="button"
                    :class="{ active: modelViewFilter === filter.value }"
                    @click="modelViewFilter = filter.value"
                  >
                    {{ filter.label }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="filteredModels.length" class="asset-grid model-grid">
            <article v-for="item in filteredModels" :key="item.id" class="asset-card">
              <div class="asset-image portrait-image">
                <img
                  v-if="item.image"
                  :src="item.image"
                  :alt="item.name"
                  @error="item.image = ''"
                />
                <span v-else>模特</span>
              </div>
              <div class="asset-body">
                <div class="asset-tags">
                  <span class="asset-tag">{{ shotTypeLabel(item.shot_type) }}</span>
                  <span class="asset-tag">{{ viewTypeLabel(modelView(item)) }}</span>
                  <span class="asset-tag neutral">{{ genderLabel(item.gender) }}</span>
                </div>
                <h5>{{ item.name }}</h5>
                <p>{{ item.remark || item.image_name || "暂无备注" }}</p>
              </div>
            </article>
          </div>

          <div v-else class="empty-library">暂时没有该分类的模特资源</div>
        </div>
      </div>
    </section>

    <section v-else class="resource-panel">
      <div class="panel-heading">
        <div>
          <span class="panel-index">03</span>
          <h3>行业场景资源</h3>
          <p>按行业标签维护 AI 生成使用的场景参考图。</p>
        </div>
      </div>

      <div v-if="!availability.scenes" class="deployment-note">
        场景接口已在本地代码中完成，部署后即可保存到服务器数据库。
      </div>

      <div class="resource-workspace">
        <form class="upload-card" @submit.prevent="uploadScene">
          <h4>添加行业场景</h4>

          <label>
            场景名称
            <input v-model.trim="sceneForm.scene_name" placeholder="例如：电力检修现场" />
          </label>

          <label>
            行业标签
            <input v-model.trim="sceneForm.industry" placeholder="例如：电力、建筑、制造" />
          </label>

          <label>
            备注
            <input v-model.trim="sceneForm.remark" placeholder="光线、环境等说明" />
          </label>

          <label class="file-field">
            场景图片
            <input type="file" accept="image/*" @change="selectFile('scene', $event)" />
          </label>

          <div v-if="previews.scene" class="upload-preview scene-preview">
            <img :src="previews.scene" alt="场景上传预览" />
          </div>

          <button class="primary-button" type="submit" :disabled="uploading.scene || !availability.scenes">
            {{ uploading.scene ? "正在保存..." : "保存场景" }}
          </button>
        </form>

        <div class="library-card">
          <div class="library-heading">
            <div>
              <h4>已有行业场景</h4>
              <p>{{ scenes.length }} 项</p>
            </div>

            <div v-if="industries.length" class="filter-pills">
              <button
                v-for="industry in industries"
                :key="industry"
                type="button"
                :class="{ active: sceneIndustryFilter === industry }"
                @click="sceneIndustryFilter = industry"
              >
                {{ industry === "all" ? "全部" : industry }}
              </button>
            </div>
          </div>

          <div v-if="filteredScenes.length" class="asset-grid scene-grid">
            <article v-for="item in filteredScenes" :key="item.id" class="asset-card">
              <div class="asset-image landscape-image">
                <img
                  v-if="item.image"
                  :src="item.image"
                  :alt="item.name"
                  @error="item.image = ''"
                />
                <span v-else>场景</span>
              </div>
              <div class="asset-body">
                <span class="asset-tag">{{ item.industry }}</span>
                <h5>{{ item.name }}</h5>
                <p>{{ item.remark || item.image_name || "暂无备注" }}</p>
              </div>
            </article>
          </div>

          <div v-else class="empty-library">暂时没有该行业的场景资源</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import axios from "axios";
import { ElMessage } from "element-plus";
import {
  normalizeImageResource,
  normalizeLogo
} from "../utils/media";
import { modelView } from "../utils/aiCompositions";

const route = useRoute();
const router = useRouter();
const validTabs = ["logos", "models", "scenes"];
const initialTab = validTabs.includes(String(route.query.tab))
  ? String(route.query.tab)
  : "logos";

const activeTab = ref(initialTab);
const logos = ref([]);
const models = ref([]);
const scenes = ref([]);
const modelGenderFilter = ref("all");
const modelShotFilter = ref("all");
const modelViewFilter = ref("all");
const sceneIndustryFilter = ref("all");

const availability = reactive({
  models: true,
  scenes: true
});

const uploading = reactive({
  logo: false,
  model: false,
  scene: false
});

const previews = reactive({
  logo: "",
  model: "",
  scene: ""
});

const logoFile = ref(null);
const modelFile = ref(null);
const sceneFile = ref(null);

const logoForm = reactive({
  region: "",
  company_name: "",
  remark: ""
});

const modelForm = reactive({
  model_name: "",
  gender: "male",
  shot_type: "full_body",
  view_type: "front",
  remark: ""
});

const sceneForm = reactive({
  scene_name: "",
  industry: "",
  remark: ""
});

const tabs = computed(() => [
  { key: "logos", label: "Logo", icon: "◆", count: logos.value.length },
  { key: "models", label: "模特", icon: "◉", count: models.value.length },
  { key: "scenes", label: "行业场景", icon: "▧", count: scenes.value.length }
]);

const genderFilters = [
  { value: "all", label: "全部" },
  { value: "male", label: "男性" },
  { value: "female", label: "女性" },
  { value: "unisex", label: "通用" }
];

const shotTypeFilters = [
  { value: "all", label: "全部" },
  { value: "full_body", label: "全身" },
  { value: "half_body", label: "半身" }
];

const viewTypeFilters = [
  { value: "all", label: "全部" },
  { value: "front", label: "正面" },
  { value: "slight_side", label: "微侧身" }
];

const filteredModels = computed(() => {
  return models.value.filter((item) => {
    const matchesGender =
      modelGenderFilter.value === "all" ||
      item.gender === modelGenderFilter.value;

    const matchesShotType =
      modelShotFilter.value === "all" ||
      (item.shot_type || "full_body") === modelShotFilter.value;

    const matchesViewType =
      modelViewFilter.value === "all" ||
      modelView(item) === modelViewFilter.value;

    return matchesGender && matchesShotType && matchesViewType;
  });
});

const industries = computed(() => [
  "all",
  ...new Set(scenes.value.map((item) => item.industry).filter(Boolean))
]);

const filteredScenes = computed(() => {
  if (sceneIndustryFilter.value === "all") {
    return scenes.value;
  }

  return scenes.value.filter((item) => item.industry === sceneIndustryFilter.value);
});

function genderLabel(value) {
  return {
    male: "男性",
    female: "女性",
    unisex: "通用"
  }[value] || "未分类";
}

function shotTypeLabel(value) {
  return {
    full_body: "全身",
    half_body: "半身"
  }[value] || "全身";
}

function viewTypeLabel(value) {
  return {
    front: "正面",
    slight_side: "微侧身"
  }[value] || "正面";
}

function selectTab(tab) {
  activeTab.value = tab;
  router.replace({
    query: {
      ...route.query,
      tab
    }
  });
}

watch(
  () => route.query.tab,
  (tab) => {
    if (validTabs.includes(String(tab))) {
      activeTab.value = String(tab);
    }
  }
);

function fileRef(type) {
  return {
    logo: logoFile,
    model: modelFile,
    scene: sceneFile
  }[type];
}

function selectFile(type, event) {
  const selected = event.target.files?.[0] || null;
  const target = fileRef(type);
  target.value = selected;

  if (previews[type]) {
    URL.revokeObjectURL(previews[type]);
  }

  previews[type] = selected
    ? URL.createObjectURL(selected)
    : "";
}

function resetFile(type) {
  const target = fileRef(type);
  target.value = null;

  if (previews[type]) {
    URL.revokeObjectURL(previews[type]);
  }

  previews[type] = "";
}

async function loadLogos() {
  const response = await axios.get("/api/logos");
  logos.value = (response.data.list || []).map(normalizeLogo);
}

async function loadModels() {
  try {
    const response = await axios.get("/api/models");
    models.value = (response.data.list || []).map((item) =>
      normalizeImageResource(item, "model_name")
    );
    availability.models = true;
  } catch (error) {
    availability.models = false;
    models.value = [];
  }
}

async function loadScenes() {
  try {
    const response = await axios.get("/api/scenes");
    scenes.value = (response.data.list || []).map((item) =>
      normalizeImageResource(item, "scene_name")
    );
    availability.scenes = true;
  } catch (error) {
    availability.scenes = false;
    scenes.value = [];
  }
}

async function uploadLogo() {
  if (!logoForm.region || !logoForm.company_name || !logoFile.value) {
    ElMessage.warning("请填写地区、公司名称并上传 Logo 图片");
    return;
  }

  const data = new FormData();
  data.append("region", logoForm.region);
  data.append("company_name", logoForm.company_name);
  data.append("remark", logoForm.remark);
  data.append("logo", logoFile.value);

  uploading.logo = true;

  try {
    await axios.post("/api/logos", data);
    Object.assign(logoForm, { region: "", company_name: "", remark: "" });
    resetFile("logo");
    await loadLogos();
    ElMessage.success("Logo 已保存");
  } catch (error) {
    ElMessage.error(error.response?.data?.message || "Logo 保存失败");
  } finally {
    uploading.logo = false;
  }
}

async function uploadModel() {
  if (!modelForm.model_name || !modelForm.gender || !modelForm.shot_type || !modelForm.view_type || !modelFile.value) {
    ElMessage.warning("请填写模特名称、性别、景别、视角并上传图片");
    return;
  }

  const data = new FormData();
  data.append("model_name", modelForm.model_name);
  data.append("gender", modelForm.gender);
  data.append("shot_type", modelForm.shot_type);
  data.append("view_type", modelForm.view_type);
  data.append("remark", modelForm.remark);
  data.append("image", modelFile.value);

  uploading.model = true;

  try {
    await axios.post("/api/models", data);
    Object.assign(modelForm, {
      model_name: "",
      gender: "male",
      shot_type: "full_body",
      view_type: "front",
      remark: ""
    });
    resetFile("model");
    await loadModels();
    ElMessage.success("模特资源已保存");
  } catch (error) {
    ElMessage.error(error.response?.data?.message || "模特资源保存失败");
  } finally {
    uploading.model = false;
  }
}

async function uploadScene() {
  if (!sceneForm.scene_name || !sceneForm.industry || !sceneFile.value) {
    ElMessage.warning("请填写场景名称、行业标签并上传图片");
    return;
  }

  const data = new FormData();
  data.append("scene_name", sceneForm.scene_name);
  data.append("industry", sceneForm.industry);
  data.append("remark", sceneForm.remark);
  data.append("image", sceneFile.value);

  uploading.scene = true;

  try {
    await axios.post("/api/scenes", data);
    Object.assign(sceneForm, { scene_name: "", industry: "", remark: "" });
    resetFile("scene");
    await loadScenes();
    ElMessage.success("行业场景已保存");
  } catch (error) {
    ElMessage.error(error.response?.data?.message || "行业场景保存失败");
  } finally {
    uploading.scene = false;
  }
}

onMounted(async () => {
  await Promise.allSettled([
    loadLogos(),
    loadModels(),
    loadScenes()
  ]);
});
</script>

<style scoped>
.resource-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: #172033;
}

.resource-hero,
.resource-panel {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 24px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.05);
}

.resource-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28px 32px;
  background: linear-gradient(135deg, #ffffff 0%, #f4f7ff 100%);
}

.eyebrow {
  color: #3157ff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.resource-hero h2 {
  margin: 7px 0 4px;
  font-size: 28px;
}

.resource-hero p,
.panel-heading p,
.library-heading p {
  margin: 0;
  color: #7b879d;
}

.resource-total {
  min-width: 132px;
  padding: 18px 22px;
  border: 1px solid #dfe7ff;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.8);
  text-align: center;
}

.resource-total strong,
.resource-total span {
  display: block;
}

.resource-total strong {
  color: #3157ff;
  font-size: 28px;
}

.resource-total span {
  margin-top: 3px;
  color: #7b879d;
  font-size: 12px;
}

.resource-tabs {
  display: flex;
  gap: 10px;
  padding: 7px;
  width: max-content;
  max-width: 100%;
  border: 1px solid #e4e9f1;
  border-radius: 16px;
  background: #fff;
}

.resource-tabs button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 16px;
  border: 0;
  border-radius: 11px;
  background: transparent;
  color: #657188;
  font-weight: 700;
  cursor: pointer;
}

.resource-tabs button.active {
  background: #172033;
  color: #fff;
}

.resource-tabs b {
  min-width: 21px;
  padding: 2px 6px;
  border-radius: 999px;
  background: #edf1f8;
  color: #657188;
  font-size: 11px;
}

.resource-panel {
  padding: 28px;
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 22px;
}

.panel-heading h3 {
  display: inline-block;
  margin: 0 0 5px 12px;
  font-size: 22px;
}

.panel-index {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #edf1ff;
  color: #3157ff;
  font-size: 12px;
  font-weight: 900;
}

.panel-heading p {
  margin-left: 50px;
  font-size: 13px;
}

.deployment-note {
  margin: -4px 0 18px;
  padding: 12px 16px;
  border: 1px solid #f1d999;
  border-radius: 12px;
  background: #fff9e9;
  color: #8a6417;
  font-size: 13px;
}

.resource-workspace {
  display: grid;
  grid-template-columns: minmax(250px, 300px) minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}

.upload-card,
.library-card {
  border: 1px solid #e6ebf2;
  border-radius: 18px;
  background: #fbfcfe;
}

.upload-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
}

.upload-card h4,
.library-heading h4 {
  margin: 0;
  font-size: 17px;
}

.upload-card label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: #566177;
  font-size: 12px;
  font-weight: 700;
}

.upload-card input,
.upload-card select {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid #dce2ec;
  border-radius: 10px;
  background: #fff;
  color: #172033;
  outline: none;
}

.upload-card input:focus,
.upload-card select:focus {
  border-color: #3157ff;
  box-shadow: 0 0 0 3px rgba(49, 87, 255, 0.1);
}

.file-field input {
  height: auto;
  padding: 9px;
}

.upload-preview {
  overflow: hidden;
  display: grid;
  place-items: center;
  height: 155px;
  border: 1px dashed #cad4e4;
  border-radius: 12px;
  background: #fff;
}

.upload-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.logo-preview img {
  padding: 14px;
  object-fit: contain;
}

.portrait-preview {
  height: 210px;
}

.primary-button {
  height: 42px;
  border: 0;
  border-radius: 11px;
  background: #3157ff;
  color: #fff;
  font-weight: 800;
  cursor: pointer;
}

.primary-button:disabled {
  background: #aeb8cf;
  cursor: not-allowed;
}

.library-card {
  min-width: 0;
  padding: 20px;
}

.library-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.library-heading p {
  margin-top: 4px;
  font-size: 12px;
}

.filter-pills {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.filter-groups {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 7px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-group > span {
  color: #8a95a8;
  font-size: 11px;
  font-weight: 700;
}

.filter-pills button {
  padding: 6px 10px;
  border: 1px solid #dfe5ee;
  border-radius: 999px;
  background: #fff;
  color: #6d788e;
  font-size: 12px;
  cursor: pointer;
}

.filter-pills button.active {
  border-color: #3157ff;
  background: #edf1ff;
  color: #3157ff;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 14px;
}

.asset-card {
  overflow: hidden;
  border: 1px solid #e2e7ef;
  border-radius: 15px;
  background: #fff;
}

.asset-image {
  display: grid;
  place-items: center;
  height: 150px;
  background: #f1f4f8;
  color: #9aa6ba;
  font-weight: 800;
}

.asset-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.contain-image img {
  padding: 16px;
  object-fit: contain;
  background: #fff;
}

.portrait-image {
  height: 220px;
}

.landscape-image {
  height: 135px;
}

.asset-body {
  padding: 14px;
}

.asset-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 999px;
  background: #edf1ff;
  color: #3157ff;
  font-size: 10px;
  font-weight: 800;
}

.asset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.asset-tag.neutral {
  background: #eef1f5;
  color: #626d80;
}

.asset-body h5 {
  margin: 9px 0 5px;
  font-size: 14px;
}

.asset-body p {
  overflow: hidden;
  margin: 0;
  color: #7b879d;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-library {
  display: grid;
  place-items: center;
  min-height: 220px;
  border: 1px dashed #dce3ed;
  border-radius: 14px;
  color: #9aa6ba;
}

@media (max-width: 980px) {
  .resource-workspace {
    grid-template-columns: 1fr;
  }

  .upload-card {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .upload-card h4,
  .upload-preview,
  .primary-button {
    grid-column: 1 / -1;
  }
}

@media (max-width: 640px) {
  .resource-hero {
    align-items: flex-start;
    padding: 22px;
  }

  .resource-total {
    display: none;
  }

  .resource-tabs {
    width: 100%;
  }

  .resource-tabs button {
    flex: 1;
    justify-content: center;
    padding: 10px 8px;
  }

  .resource-panel {
    padding: 20px;
  }

  .upload-card {
    display: flex;
  }

  .library-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .filter-pills {
    justify-content: flex-start;
  }
}
</style>
