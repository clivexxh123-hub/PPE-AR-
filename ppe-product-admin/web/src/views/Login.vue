<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const phone = ref("");
const password = ref("");
const loggingIn = ref(false);
const errorMessage = ref("");

const canLogin = computed(() => /^1[3-9]\d{9}$/.test(phone.value) && password.value.length >= 8);
const visibleError = computed(() => errorMessage.value || authStore.initializationError || "");

async function submitLogin() {
  if (!canLogin.value) return;
  loggingIn.value = true;
  errorMessage.value = "";
  try {
    await authStore.login(phone.value, password.value);
    const redirect = typeof route.query.redirect === "string" && route.query.redirect.startsWith("/")
      ? route.query.redirect
      : "/dashboard";
    await router.replace(redirect);
  } catch (error) {
    errorMessage.value = error?.response?.data?.message || "登录失败";
  } finally {
    loggingIn.value = false;
  }
}

</script>

<template>
  <main class="iam-login-page">
    <section class="iam-login-intro">
      <span class="iam-kicker">SHOUDUN PPE VISUAL SYSTEM</span>
      <h1>PPE平台</h1>
      <p>销售、产品资料、客户方案和 AI 生成记录统一进入受控工作台。</p>
      <div class="iam-security-note">
        <el-icon><Lock /></el-icon>
        <span>手机号密码登录 · 权限校验 · 操作审计</span>
      </div>
    </section>

    <section class="iam-login-panel">
      <div class="iam-login-card">
        <div class="iam-login-brand">P</div>
        <h2>登录工作台</h2>
        <p>仅已录入系统的员工手机号可以登录</p>

        <label class="iam-field">
          <span>手机号码</span>
          <el-input v-model="phone" maxlength="11" placeholder="请输入11位手机号" inputmode="numeric" />
        </label>

        <label class="iam-field">
          <span>登录密码</span>
          <el-input
            v-model="password"
            type="password"
            maxlength="72"
            placeholder="请输入登录密码"
            autocomplete="current-password"
            show-password
            @keyup.enter="submitLogin"
          />
        </label>

        <div v-if="visibleError" class="iam-login-error">{{ visibleError }}</div>

        <el-button
          type="primary"
          class="iam-login-submit"
          :disabled="!canLogin"
          :loading="loggingIn"
          @click="submitLogin"
        >
          进入系统
        </el-button>
      </div>
    </section>
  </main>
</template>
