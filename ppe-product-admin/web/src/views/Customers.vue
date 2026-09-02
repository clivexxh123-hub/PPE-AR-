<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Search } from "@element-plus/icons-vue";

import request from "../api/request";
import { useAuthStore } from "../stores/auth";
import "../assets/customers.css";

const authStore = useAuthStore();
const loading = ref(false);
const saving = ref(false);
const customers = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 50;
const search = ref("");
const mineOnly = ref(false);
const dialogVisible = ref(false);
const editingCustomer = ref(null);
const historyVisible = ref(false);
const historyLoading = ref(false);
const historyCustomer = ref(null);
const generationArchives = ref([]);

const emptyForm = () => ({
  customerName: "",
  companyShortName: "",
  industry: "",
  remarkId: "",
  notes: ""
});

const form = reactive(emptyForm());
const canCreate = computed(() => authStore.hasPermission("records.write_own"));
const archivePreview = computed(() => form.remarkId
  .replace(/[<>:"/\\|?*+\u0000-\u001f]/g, "_")
  .replace(/\s+/g, " ")
  .replace(/[. ]+$/g, "")
  .trim()
  .slice(0, 80));
const dialogTitle = computed(() => editingCustomer.value ? "编辑客户档案" : "新建客户档案");

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("zh-CN", { hour12: false });
}

function resetForm(customer = null) {
  Object.assign(form, emptyForm(), customer ? {
    customerName: customer.customerName || "",
    companyShortName: customer.companyShortName || "",
    industry: customer.industry || "",
    remarkId: customer.remarkId || "",
    notes: customer.notes || ""
  } : {});
}

function openCreate() {
  editingCustomer.value = null;
  resetForm();
  dialogVisible.value = true;
}

function openEdit(customer) {
  if (!customer.canEdit) {
    ElMessage.warning("普通员工只能修改本人客户档案");
    return;
  }
  editingCustomer.value = customer;
  resetForm(customer);
  dialogVisible.value = true;
}

async function loadCustomers() {
  loading.value = true;
  try {
    const response = await request.get("/customers", {
      params: {
        limit: pageSize,
        offset: (page.value - 1) * pageSize,
        search: search.value.trim() || undefined,
        mine: mineOnly.value ? "true" : undefined
      },
      silentError: true
    });
    customers.value = response.data?.items || [];
    total.value = Number(response.data?.total || 0);
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "客户档案加载失败");
  } finally {
    loading.value = false;
  }
}

function runSearch() {
  page.value = 1;
  loadCustomers();
}

async function saveCustomer() {
  if (!form.customerName.trim()) {
    ElMessage.warning("请填写客户ID");
    return;
  }
  if (!form.remarkId.trim()) {
    ElMessage.warning("请填写淘宝ID或订单号");
    return;
  }
  saving.value = true;
  const payload = Object.fromEntries(
    Object.entries(form).map(([key, value]) => [key, value.trim()])
  );
  try {
    if (editingCustomer.value) {
      await request.patch(
        `/customers/${encodeURIComponent(editingCustomer.value.id)}`,
        payload,
        { silentError: true }
      );
      ElMessage.success("客户档案和归档名已更新");
    } else {
      await request.post("/customers", payload, { silentError: true });
      ElMessage.success("客户档案已创建");
    }
    dialogVisible.value = false;
    page.value = 1;
    await loadCustomers();
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "客户档案保存失败");
  } finally {
    saving.value = false;
  }
}

async function removeCustomer(customer) {
  if (!customer.canDelete) {
    ElMessage.warning("普通员工只能删除本人客户档案");
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确认删除“${customer.customerName}”吗？系统将做软删除并保留审计记录。`,
      "删除客户档案",
      { type: "warning", confirmButtonText: "确认删除", cancelButtonText: "取消" }
    );
    await request.delete(`/customers/${encodeURIComponent(customer.id)}`, { silentError: true });
    ElMessage.success("客户档案已删除，审计记录仍保留");
    if (customers.value.length === 1 && page.value > 1) page.value -= 1;
    await loadCustomers();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error?.response?.data?.message || "客户档案删除失败");
  }
}

function compositionLabel(composition) {
  if (!composition) return "未记录构图";
  const view = composition.view === "slight_side" ? "微侧身" : "正面";
  const framing = composition.framing === "full_body" ? "全身" : "半身";
  return `${view} · ${framing}`;
}

function statusLabel(status) {
  return {
    preparing: "准备中",
    queued: "排队中",
    running: "生成中",
    succeeded: "已完成",
    failed: "失败"
  }[status] || "未知";
}

async function openHistory(customer) {
  historyCustomer.value = customer;
  historyVisible.value = true;
  historyLoading.value = true;
  generationArchives.value = [];
  try {
    const response = await request.get(
      `/customers/${encodeURIComponent(customer.id)}/generation-records`,
      { params: { limit: 200 }, silentError: true }
    );
    generationArchives.value = response.data || [];
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "客户历史作图加载失败");
  } finally {
    historyLoading.value = false;
  }
}

onMounted(loadCustomers);
</script>

<template>
  <section class="customers-page">
    <header class="customers-header">
      <div>
        <span>CUSTOMER ARCHIVE</span>
        <h2>客户档案</h2>
        <p>全员可查看；普通员工只能维护本人数据，历史部门与小组按创建时归属保存。</p>
      </div>
      <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">
        新建客户
      </el-button>
    </header>

    <div class="customers-toolbar">
      <el-input
        v-model="search"
        clearable
        placeholder="搜索客户ID、淘宝ID、订单号、归档名或备注"
        :prefix-icon="Search"
        @keyup.enter="runSearch"
        @clear="runSearch"
      />
      <el-checkbox v-model="mineOnly" @change="runSearch">仅看我的客户</el-checkbox>
      <el-button :loading="loading" @click="runSearch">查询</el-button>
      <span class="customers-total">共 {{ total }} 个未删除档案</span>
    </div>

    <div class="customers-table-card">
      <el-table v-loading="loading" :data="customers" row-key="id">
        <el-table-column label="客户ID" min-width="210">
          <template #default="{ row }">
            <div class="customer-primary-cell">
              <strong>{{ row.customerName }}</strong>
              <span>{{ row.companyShortName || "未填写客户简称" }} · {{ row.industry || "未分类行业" }}</span>
              <small>{{ row.notes || "无备注" }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="淘宝ID / 订单号（归档名）" min-width="300">
          <template #default="{ row }">
            <div class="customer-archive-cell">
              <code>{{ row.archiveName }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="作图记录" min-width="170">
          <template #default="{ row }">
            <div class="customer-record-count">
              <strong>{{ row.generationRecordCount || 0 }} 条</strong>
              <span>最近：{{ formatTime(row.latestGenerationAt) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="165">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <template v-if="row.canEdit || row.canDelete">
              <el-button v-if="row.canEdit" link type="primary" @click="openEdit(row)">修改</el-button>
              <el-button v-if="row.canDelete" link type="danger" @click="removeCustomer(row)">删除</el-button>
            </template>
            <span v-else class="customer-readonly">不可编辑</span>
            <el-button link type="primary" @click="openHistory(row)">历史作图</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="total > pageSize" class="customers-pagination">
        <el-pagination
          v-model:current-page="page"
          background
          layout="prev, pager, next, total"
          :page-size="pageSize"
          :total="total"
          @current-change="loadCustomers"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="min(640px, 94vw)" destroy-on-close>
      <el-form class="customer-form" label-position="top" @submit.prevent="saveCustomer">
        <div class="customer-form-grid">
          <el-form-item label="客户ID（必填）">
            <el-input v-model="form.customerName" maxlength="120" show-word-limit />
          </el-form-item>
          <el-form-item label="淘宝ID或订单号（必填，作为归档名）">
            <el-input v-model="form.remarkId" maxlength="100" show-word-limit />
          </el-form-item>
          <el-form-item label="客户简称（用于作图记录名称）">
            <el-input v-model="form.companyShortName" maxlength="80" placeholder="例如：广东建工" />
          </el-form-item>
          <el-form-item label="所属行业">
            <el-input v-model="form.industry" maxlength="100" placeholder="例如：建筑" />
          </el-form-item>
        </div>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" maxlength="4000" show-word-limit />
        </el-form-item>
      </el-form>

      <div class="customer-naming-preview" :class="{ warning: !archivePreview }">
        <el-icon><InfoFilled /></el-icon>
        <span v-if="archivePreview">归档名：{{ archivePreview }}</span>
        <span v-else>请填写淘宝ID或订单号，保存后将直接作为归档名。</span>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCustomer">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="historyVisible"
      :title="`${historyCustomer?.customerName || '客户'} · 历史作图`"
      size="min(760px, 94vw)"
    >
      <div v-loading="historyLoading" class="customer-history-list">
        <el-empty
          v-if="!historyLoading && !generationArchives.length"
          description="该客户尚无作图记录"
        />
        <article v-for="record in generationArchives" :key="record.jobId" class="customer-history-card">
          <el-image
            v-if="record.resultUrl"
            :src="record.resultUrl"
            :preview-src-list="[record.resultUrl]"
            fit="cover"
            preview-teleported
          />
          <div v-else class="customer-history-status" :class="`status-${record.status}`">
            {{ statusLabel(record.status) }}
          </div>
          <div>
            <strong>{{ record.displayName || record.product?.name || "未记录产品" }}</strong>
            <span>{{ compositionLabel(record.composition) }}</span>
            <span>{{ record.scene?.name || "未记录场景" }} · {{ record.model?.name || "未记录模特" }}</span>
            <small>
              {{ record.user?.displayName || "未知员工" }}创建 · {{ formatTime(record.createdAt) }}
            </small>
          </div>
          <el-link v-if="record.resultUrl" :href="record.resultUrl" target="_blank" type="primary">查看结果</el-link>
        </article>
      </div>
    </el-drawer>
  </section>
</template>
