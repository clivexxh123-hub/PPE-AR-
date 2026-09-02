<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";

import request from "../api/request";
import { useAuthStore } from "../stores/auth";
import "../assets/case-library.css";

const router = useRouter();
const authStore = useAuthStore();
const loading = ref(false);
const submitting = ref(false);
const templates = ref([]);
const industry = ref("");
const workScene = ref("");
const createDialogVisible = ref(false);
const customersLoading = ref(false);
const customers = ref([]);
const previewFile = ref(null);
const previewInput = ref(null);
const failedPreviews = ref(new Set());

const emptyCaseForm = () => ({
  customerId: "",
  name: "",
  industry: "",
  workScene: "",
  description: "",
  standardReference: "",
  productKeywords: ""
});
const caseForm = reactive(emptyCaseForm());

const canCreateCase = computed(() => authStore.hasPermission("records.write_own"));
const industries = computed(() => [...new Set(
  templates.value.map(item => item.industry).filter(Boolean)
)]);
const workScenes = computed(() => [...new Set(
  templates.value
    .filter(item => !industry.value || item.industry === industry.value)
    .map(item => item.workScene)
    .filter(Boolean)
)]);
const visibleTemplates = computed(() => templates.value.filter(item => (
  (!industry.value || item.industry === industry.value)
  && (!workScene.value || item.workScene === workScene.value)
)));

async function loadTemplates() {
  loading.value = true;
  try {
    const response = await request.get("/case-templates", { silentError: true });
    templates.value = response.data?.items || [];
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "案例库加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadCustomers() {
  customersLoading.value = true;
  try {
    const response = await request.get("/customers", {
      params: { limit: 500 },
      silentError: true
    });
    customers.value = (response.data?.items || []).filter(item => item.canEdit);
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "客户列表加载失败");
    customers.value = [];
  } finally {
    customersLoading.value = false;
  }
}

function selectIndustry(value) {
  industry.value = value;
  if (workScene.value && !workScenes.value.includes(workScene.value)) workScene.value = "";
}

async function useTemplate(template) {
  await router.push({
    path: "/ai-generator",
    query: { caseTemplateId: template.id }
  });
}

async function openCreateDialog() {
  createDialogVisible.value = true;
  if (!customers.value.length) await loadCustomers();
}

function resetCaseForm() {
  Object.assign(caseForm, emptyCaseForm());
  previewFile.value = null;
  if (previewInput.value) previewInput.value.value = "";
}

function selectPreview(event) {
  const file = event.target.files?.[0] || null;
  if (file && !["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    ElMessage.warning("封面仅支持 PNG、JPEG 或 WEBP 图片");
    event.target.value = "";
    previewFile.value = null;
    return;
  }
  if (file && file.size > 8 * 1024 * 1024) {
    ElMessage.warning("案例封面不能超过 8MB");
    event.target.value = "";
    previewFile.value = null;
    return;
  }
  previewFile.value = file;
}

async function createCase() {
  if (!caseForm.customerId) return ElMessage.warning("请选择案例所属客户");
  if (!caseForm.name.trim()) return ElMessage.warning("请填写案例名称");
  if (!caseForm.industry.trim()) return ElMessage.warning("请填写所属行业");
  if (!caseForm.workScene.trim()) return ElMessage.warning("请填写工种或场景");
  if (!caseForm.description.trim()) return ElMessage.warning("请填写案例说明");
  if (!caseForm.productKeywords.trim()) return ElMessage.warning("请填写案例使用的产品");
  if (!previewFile.value) return ElMessage.warning("请上传一张案例封面图片");

  const form = new FormData();
  Object.entries(caseForm).forEach(([key, value]) => form.append(key, value));
  form.append("preview", previewFile.value);
  submitting.value = true;
  try {
    const response = await request.post("/case-templates", form, { silentError: true });
    industry.value = "";
    workScene.value = "";
    templates.value = [response.data, ...templates.value];
    createDialogVisible.value = false;
    ElMessage.success("客户案例已创建，可直接进入 AI 生成中心使用");
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "案例创建失败");
  } finally {
    submitting.value = false;
  }
}

function markPreviewFailed(templateId) {
  failedPreviews.value = new Set([...failedPreviews.value, templateId]);
}

onMounted(loadTemplates);
</script>

<template>
  <section class="case-library-page">
    <header class="case-library-hero">
      <div>
        <span>VISUAL SOLUTION LIBRARY</span>
        <h2>行业案例库</h2>
        <p>查看实际场景效果，选择标准方案或客户案例后进入 AI 生成中心继续修改。</p>
      </div>
      <div class="case-library-hero-actions">
        <div class="case-library-summary">
          <strong>{{ visibleTemplates.length }}</strong>
          <span>个可用案例</span>
        </div>
        <button
          v-if="canCreateCase"
          type="button"
          class="case-library-create"
          @click="openCreateDialog"
        >
          <span>＋</span>
          新建客户案例
        </button>
      </div>
    </header>

    <div class="case-library-filters">
      <div>
        <span>行业</span>
        <button :class="{ active: !industry }" @click="selectIndustry('')">全部</button>
        <button
          v-for="item in industries"
          :key="item"
          :class="{ active: industry === item }"
          @click="selectIndustry(item)"
        >
          {{ item }}
        </button>
      </div>
      <div>
        <span>工种 / 场景</span>
        <button :class="{ active: !workScene }" @click="workScene = ''">全部</button>
        <button
          v-for="item in workScenes"
          :key="item"
          :class="{ active: workScene === item }"
          @click="workScene = item"
        >
          {{ item }}
        </button>
      </div>
    </div>

    <div v-loading="loading" class="case-library-grid">
      <el-empty v-if="!loading && !visibleTemplates.length" description="暂无符合条件的可视案例" />
      <article v-for="template in visibleTemplates" :key="template.id" class="case-template-card">
        <figure class="case-template-preview">
          <div class="case-template-image-fallback" aria-hidden="true">
            {{ template.workScene === '电工作业' ? '⚡' : template.workScene === '有限空间' ? '◉' : '⌂' }}
          </div>
          <img
            v-if="template.previewUrl && !failedPreviews.has(template.id)"
            :src="template.previewUrl"
            :alt="`${template.name}场景预览`"
            loading="lazy"
            @error="markPreviewFailed(template.id)"
          />
          <span class="case-template-source" :class="{ customer: template.sourceType === 'customer' }">
            {{ template.sourceType === 'customer' ? '客户案例' : '标准案例' }}
          </span>
          <small>V{{ template.versionNo }}</small>
        </figure>

        <div class="case-template-body">
          <div class="case-template-topline">
            <span>{{ template.industry }} · {{ template.workScene }}</span>
            <em v-if="template.customerName">{{ template.customerName }}</em>
          </div>
          <h3>{{ template.name }}</h3>
          <p>{{ template.description }}</p>
          <div class="case-template-tags">
            <span v-for="keyword in template.selection?.productKeywords || []" :key="keyword">
              {{ keyword }}
            </span>
          </div>
          <div class="case-template-standard" :class="{ pending: template.standardReviewStatus !== 'reviewed' }">
            <b>{{ template.standardReviewStatus === 'reviewed' ? '标准已复核' : '标准待复核' }}</b>
            <span>{{ template.standardReference || '未填写标准依据' }}</span>
          </div>
          <button class="case-template-use" type="button" @click="useTemplate(template)">
            使用案例并进入 AI 生成中心
            <span>→</span>
          </button>
        </div>
      </article>
    </div>

    <el-dialog
      v-model="createDialogVisible"
      width="min(640px, calc(100vw - 32px))"
      title="新建客户案例"
      destroy-on-close
      @closed="resetCaseForm"
    >
      <div class="case-create-intro">
        案例创建后仅该客户负责人和管理员可见，并可直接作为 AI 生成模板使用。
      </div>
      <div class="case-create-form">
        <label class="case-create-field case-create-wide">
          <span>所属客户 <b>*</b></span>
          <el-select
            v-model="caseForm.customerId"
            filterable
            :loading="customersLoading"
            placeholder="选择本人负责的客户"
            style="width: 100%"
          >
            <el-option
              v-for="customer in customers"
              :key="customer.id"
              :label="customer.companyShortName || customer.customerName"
              :value="customer.id"
            />
          </el-select>
          <small v-if="!customersLoading && !customers.length">
            暂无可管理客户，请先到“客户档案”新建客户。
          </small>
        </label>

        <label class="case-create-field case-create-wide">
          <span>案例名称 <b>*</b></span>
          <el-input v-model="caseForm.name" maxlength="160" placeholder="例如：广东项目夏季施工案例" />
        </label>

        <label class="case-create-field">
          <span>所属行业 <b>*</b></span>
          <el-input v-model="caseForm.industry" maxlength="100" placeholder="例如：建筑" />
        </label>
        <label class="case-create-field">
          <span>工种 / 场景 <b>*</b></span>
          <el-input v-model="caseForm.workScene" maxlength="120" placeholder="例如：室外施工" />
        </label>

        <label class="case-create-field case-create-wide">
          <span>使用产品 <b>*</b></span>
          <el-input
            v-model="caseForm.productKeywords"
            maxlength="300"
            placeholder="安全帽、反光衣、劳保鞋（使用逗号分隔）"
          />
        </label>

        <label class="case-create-field case-create-wide">
          <span>案例说明 <b>*</b></span>
          <el-input
            v-model="caseForm.description"
            type="textarea"
            :rows="3"
            maxlength="600"
            show-word-limit
            placeholder="说明案例用途、施工环境和希望呈现的效果"
          />
        </label>

        <label class="case-create-field case-create-wide">
          <span>标准依据</span>
          <el-input
            v-model="caseForm.standardReference"
            maxlength="255"
            placeholder="可选，创建后默认标记为待复核"
          />
        </label>

        <div class="case-create-field case-create-wide">
          <span>案例封面 <b>*</b></span>
          <input
            ref="previewInput"
            class="case-cover-input"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="selectPreview"
          />
          <button class="case-cover-picker" type="button" @click="previewInput?.click()">
            <span>▧</span>
            <strong>{{ previewFile?.name || '选择案例场景图片' }}</strong>
            <small>PNG、JPEG 或 WEBP，最大 8MB</small>
          </button>
        </div>
      </div>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createCase">
          创建并发布案例
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
