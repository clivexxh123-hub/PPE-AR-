<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";

import request from "../api/request";
import { useAuthStore } from "../stores/auth";
import "../assets/business-records.css";

const router = useRouter();
const authStore = useAuthStore();
const loading = ref(false);
const records = ref([]);
const status = ref("");
const deletingJobId = ref("");

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "preparing", label: "准备素材" },
  { value: "queued", label: "排队中" },
  { value: "running", label: "生成中" },
  { value: "succeeded", label: "已完成" },
  { value: "failed", label: "失败" }
];

function statusLabel(value) {
  return statusOptions.find((item) => item.value === value)?.label || value || "未知";
}

function statusType(value) {
  return { succeeded: "success", failed: "danger", running: "warning" }[value] || "info";
}

function compositionLabel(composition) {
  if (!composition) return "未记录";
  const view = composition.view === "slight_side" ? "微侧身" : "正面";
  const framing = composition.framing === "full_body" ? "全身" : "半身";
  return `${view} · ${framing}`;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

async function loadRecords() {
  loading.value = true;
  try {
    const response = await request.get("/ai/generation-records", {
      params: { limit: 200, status: status.value || undefined }
    });
    records.value = response.data || [];
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "作图记录加载失败");
  } finally {
    loading.value = false;
  }
}

async function openResult(record) {
  try {
    const response = await request.get(`/ai/generations/${encodeURIComponent(record.jobId)}`);
    const resultUrl = response.data?.resultUrl;
    if (!resultUrl) {
      ElMessage.warning("该任务暂时没有可查看的结果");
      return;
    }
    window.open(resultUrl, "_blank", "noopener,noreferrer");
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "结果读取失败");
  }
}

async function openRevision(record) {
  if (!record?.canEdit || record.status !== "succeeded") return;
  await router.push({
    path: "/ai-generator",
    query: { sourceJobId: record.jobId }
  });
}

async function deleteRecord(record) {
  if (!authStore.isSuperAdministrator || !record?.jobId || deletingJobId.value) return;
  try {
    await ElMessageBox.confirm(
      "删除后该记录将不再显示；为保证审计和客户归档完整性，底层历史信息仍会安全保留。",
      "确认删除作图记录？",
      {
        confirmButtonText: "确认删除",
        cancelButtonText: "取消",
        type: "warning"
      }
    );
    deletingJobId.value = record.jobId;
    await request.delete(`/ai/generation-records/${encodeURIComponent(record.jobId)}`, {
      silentError: true
    });
    ElMessage.success("作图记录已删除");
    await loadRecords();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error?.response?.data?.message || "作图记录删除失败");
  } finally {
    deletingJobId.value = "";
  }
}

onMounted(loadRecords);
</script>

<template>
  <section class="business-records-page">
    <header class="business-records-header">
      <div>
        <span>GENERATION AUDIT</span>
        <h2>作图记录</h2>
        <p>普通员工可查看全员记录；员工调组不会改变历史部门和小组归属。</p>
      </div>
      <div class="business-records-actions">
        <el-select v-model="status" style="width: 130px" @change="loadRecords">
          <el-option
            v-for="option in statusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button :loading="loading" @click="loadRecords">刷新</el-button>
      </div>
    </header>

    <div class="business-records-table-card">
      <el-table v-loading="loading" :data="records" row-key="jobId">
        <el-table-column label="生成时间" min-width="165">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="员工 / 历史归属" min-width="220">
          <template #default="{ row }">
            <div class="record-owner-cell">
              <strong>{{ row.user?.displayName || "未知员工" }}</strong>
              <span>{{ row.department?.name || "未分部门" }} / {{ row.orgUnit?.name || "未分组" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="产品" min-width="190">
          <template #default="{ row }">
            <div class="record-owner-cell">
              <strong>{{ row.product?.name }}</strong>
              <span>{{ row.product?.code || "无产品编号" }}</span>
              <span v-if="row.parameters?.sourceJobId" class="record-revision-mark">修改版本</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="构图" min-width="130">
          <template #default="{ row }">{{ compositionLabel(row.composition) }}</template>
        </el-table-column>
        <el-table-column label="模特 / 场景" min-width="190">
          <template #default="{ row }">
            <div class="record-owner-cell">
              <strong>{{ row.model?.name || "未记录模特" }}</strong>
              <span>{{ row.scene?.name || "未记录场景" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }} {{ row.progress }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="205" fixed="right">
          <template #default="{ row }">
            <div class="record-operation-cell">
              <el-button
                link
                type="primary"
                :disabled="row.status !== 'succeeded'"
                @click="openResult(row)"
              >
                查看结果
              </el-button>
              <el-button
                link
                type="success"
                :disabled="!row.canEdit"
                @click="openRevision(row)"
              >
                修改
              </el-button>
              <el-button
                v-if="authStore.isSuperAdministrator"
                link
                type="danger"
                :loading="deletingJobId === row.jobId"
                :disabled="Boolean(deletingJobId)"
                @click="deleteRecord(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

  </section>
</template>
