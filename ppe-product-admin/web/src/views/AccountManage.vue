<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createIamUser,
  getIamOrgUnits,
  getIamRoles,
  getIamUsers,
  updateIamUser
} from "../api/auth";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const loading = ref(false);
const saving = ref(false);
const users = ref([]);
const orgUnits = ref([]);
const roles = ref([]);
const dialogVisible = ref(false);
const editingUserId = ref("");

const form = reactive({
  displayName: "",
  phone: "",
  password: "",
  confirmPassword: "",
  orgUnitCode: "",
  roleId: "sales",
  status: "active"
});

const departmentOrder = [
  "jingshan-public",
  "jingshan-private",
  "wuhan-alibaba-private",
  "wuhan-sales",
  "platform-management"
];
const orgOptions = computed(() => orgUnits.value
  .filter((unit) => unit.active && unit.unitType === "department")
  .sort((left, right) => {
    const leftIndex = departmentOrder.indexOf(left.code);
    const rightIndex = departmentOrder.indexOf(right.code);
    return (leftIndex < 0 ? 999 : leftIndex) - (rightIndex < 0 ? 999 : rightIndex);
  })
  .map((department) => {
    const children = orgUnits.value.filter((unit) => unit.active && unit.parentId === department.id);
    return {
      ...department,
      options: children.length ? children : [department]
    };
  }));
const dialogTitle = computed(() => editingUserId.value ? "编辑员工账号" : "新增员工账号");

function unwrap(response) {
  if (Array.isArray(response?.data)) return response.data;
  return Array.isArray(response?.data?.data) ? response.data.data : [];
}

function memberCount(unit) {
  return users.value.filter((user) => user.orgUnit?.id === unit.id).length;
}

function resetForm() {
  editingUserId.value = "";
  form.displayName = "";
  form.phone = "";
  form.password = "";
  form.confirmPassword = "";
  form.orgUnitCode = "";
  form.roleId = "sales";
  form.status = "active";
}

function primaryRoleId(user) {
  if (user.roles?.some((role) => role.id === "admin")) return "admin";
  return user.roles?.[0]?.id || "sales";
}

function openCreate() {
  resetForm();
  dialogVisible.value = true;
}

function openEdit(user) {
  editingUserId.value = user.id;
  form.displayName = user.displayName;
  form.phone = user.phone;
  form.password = "";
  form.confirmPassword = "";
  form.orgUnitCode = user.orgUnit?.code || "";
  form.roleId = primaryRoleId(user);
  form.status = user.status;
  dialogVisible.value = true;
}

function userOrgLabel(user) {
  if (!user.orgUnit) return "未分组";
  return user.department ? `${user.department.name} / ${user.orgUnit.name}` : user.orgUnit.name;
}

function statusLabel(status) {
  return status === "active" ? "启用" : "停用";
}

function validateForm() {
  if (!form.displayName.trim()) return "请输入员工姓名";
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) return "请输入有效的11位手机号";
  if (!editingUserId.value && !form.password) return "新增账号必须设置登录密码";
  if (form.password) {
    if (form.password.length < 8 || form.password.length > 72) return "密码长度必须为8至72位";
    if (!/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)) return "密码必须同时包含字母和数字";
    if (form.password !== form.confirmPassword) return "两次输入的密码不一致";
  }
  if (!form.orgUnitCode) return "请选择所属部门或小组";
  if (!form.roleId) return "请选择一个系统角色";
  return "";
}

async function loadData() {
  loading.value = true;
  try {
    const [userResponse, orgResponse, roleResponse] = await Promise.all([
      getIamUsers(),
      getIamOrgUnits(),
      getIamRoles()
    ]);
    users.value = unwrap(userResponse);
    orgUnits.value = unwrap(orgResponse);
    roles.value = unwrap(roleResponse);
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "账号数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function saveUser() {
  const errorMessage = validateForm();
  if (errorMessage) {
    ElMessage.warning(errorMessage);
    return;
  }

  const payload = {
    displayName: form.displayName.trim(),
    phone: form.phone.trim(),
    orgUnitCode: form.orgUnitCode,
    roleIds: [form.roleId],
    status: form.status
  };
  if (form.password) payload.password = form.password;

  saving.value = true;
  try {
    if (editingUserId.value) {
      await updateIamUser(editingUserId.value, payload);
      ElMessage.success("员工账号已更新，调组前的历史记录仍归原小组");
    } else {
      await createIamUser(payload);
      ElMessage.success("员工账号已创建");
    }
    dialogVisible.value = false;
    await loadData();
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "账号保存失败");
  } finally {
    saving.value = false;
  }
}

async function toggleStatus(user) {
  const nextStatus = user.status === "active" ? "disabled" : "active";
  const action = nextStatus === "active" ? "启用" : "停用";
  try {
    await ElMessageBox.confirm(
      `${action}“${user.displayName}”的账号？${nextStatus === "disabled" ? "该员工现有会话将立即失效。" : ""}`,
      `${action}账号`,
      { type: nextStatus === "disabled" ? "warning" : "info" }
    );
    await updateIamUser(user.id, {
      displayName: user.displayName,
      phone: user.phone,
      orgUnitCode: user.orgUnit?.code,
      roleIds: [primaryRoleId(user)],
      status: nextStatus
    });
    ElMessage.success(`账号已${action}`);
    await loadData();
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      ElMessage.error(error?.response?.data?.message || `${action}失败`);
    }
  }
}

onMounted(loadData);
</script>

<template>
  <section class="iam-account-page">
    <header class="iam-account-toolbar">
      <div>
        <span class="iam-section-kicker">权限与组织</span>
        <h2>员工账号管理</h2>
        <p>姓名、手机号、密码和组织分组保持统一管理；所有变更都会写入审计日志。</p>
      </div>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新增员工
      </el-button>
    </header>

    <div class="iam-permission-baseline">
      <el-icon><InfoFilled /></el-icon>
      <span>权限基线：超级管理员拥有全权限；普通账号可执行基础业务操作、查看全员记录，但只能修改本人数据，不做小组数据隔离。</span>
    </div>

    <section class="iam-org-overview">
      <div class="iam-org-overview-header">
        <div>
          <span class="iam-section-kicker">PERSONNEL GROUPS</span>
          <h3>人员分组</h3>
        </div>
        <small>共 {{ orgOptions.length }} 个部门，分组用于账号归属和历史审计</small>
      </div>
      <div class="iam-org-grid">
        <article v-for="department in orgOptions" :key="department.id" class="iam-org-card">
          <div class="iam-org-card-title">
            <strong>{{ department.name }}</strong>
            <span>{{ department.options.length }} 个可选归属</span>
          </div>
          <div class="iam-org-unit-list">
            <span v-for="unit in department.options" :key="unit.id" class="iam-org-unit">
              {{ unit.id === department.id ? "部门直属" : unit.name }}
              <small>{{ memberCount(unit) }} 人</small>
            </span>
          </div>
        </article>
      </div>
    </section>

    <div class="iam-account-table-card">
      <el-table v-loading="loading" :data="users" row-key="id">
        <el-table-column label="员工" min-width="150">
          <template #default="{ row }">
            <div class="iam-user-cell">
              <span class="iam-table-avatar">{{ row.displayName?.slice(0, 1) || "员" }}</span>
              <strong>{{ row.displayName }}</strong>
              <small v-if="row.id === authStore.user?.id">当前账号</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" min-width="130" />
        <el-table-column label="部门 / 小组" min-width="210">
          <template #default="{ row }">{{ userOrgLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="角色" min-width="150">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role.id" size="small" effect="plain">
              {{ role.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              :type="row.status === 'active' ? 'danger' : 'success'"
              :disabled="row.id === authStore.user?.id && row.status === 'active'"
              @click="toggleStatus(row)"
            >
              {{ row.status === "active" ? "停用" : "启用" }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" destroy-on-close>
      <el-form label-position="top" class="iam-account-form">
        <div class="iam-form-grid">
          <el-form-item label="员工姓名">
            <el-input v-model="form.displayName" maxlength="64" placeholder="请输入姓名" />
          </el-form-item>
          <el-form-item label="手机号码">
            <el-input v-model="form.phone" maxlength="11" inputmode="numeric" placeholder="用于手机号+密码登录" />
          </el-form-item>
        </div>
        <div class="iam-form-grid">
          <el-form-item :label="editingUserId ? '设置新密码（可选）' : '登录密码'">
            <el-input
              v-model="form.password"
              type="password"
              maxlength="72"
              autocomplete="new-password"
              show-password
              :placeholder="editingUserId ? '不修改请留空' : '8至72位，包含字母和数字'"
            />
          </el-form-item>
          <el-form-item label="确认密码">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              maxlength="72"
              autocomplete="new-password"
              show-password
              :disabled="!form.password"
              placeholder="请再次输入密码"
            />
          </el-form-item>
        </div>
        <el-form-item label="所属部门 / 小组">
          <el-select v-model="form.orgUnitCode" filterable placeholder="请选择组织">
            <el-option-group
              v-for="department in orgOptions"
              :key="department.id"
              :label="department.name"
            >
              <el-option
                v-for="unit in department.options"
                :key="unit.id"
                :label="unit.id === department.id ? department.name : unit.name"
                :value="unit.code"
              />
            </el-option-group>
          </el-select>
          <small class="iam-form-help">分组用于人员归属和审计，不限制普通账号查看其他小组的业务记录。</small>
        </el-form-item>
        <el-form-item label="系统角色">
          <el-radio-group v-model="form.roleId">
            <el-radio v-for="role in roles" :key="role.id" :value="role.id">
              {{ role.name }}
            </el-radio>
          </el-radio-group>
          <small class="iam-form-help">每个账号只能选择一个系统角色。</small>
        </el-form-item>
        <el-form-item label="账号状态">
          <el-radio-group v-model="form.status">
            <el-radio value="active">启用</el-radio>
            <el-radio value="disabled">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
