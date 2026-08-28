import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  getCurrentUser,
  loginWithPassword,
  logoutSession,
} from "../api/auth";

export const useAuthStore = defineStore("auth", () => {
  const user = ref(null);
  const initialized = ref(false);
  const loading = ref(false);
  const initializationError = ref("");

  const isAuthenticated = computed(() => Boolean(user.value?.id));
  const isSuperAdministrator = computed(() => (
    Boolean(user.value?.roles?.some((role) => role.id === "admin"))
  ));
  const isAdministrator = computed(() => hasPermission("system.manage"));

  function hasPermission(permission) {
    const isSuperAdministrator = user.value?.roles?.some((role) => role.id === "admin");
    return Boolean(isSuperAdministrator || user.value?.permissions?.includes(permission));
  }

  async function initialize(force = false) {
    if (initialized.value && !force) return user.value;
    loading.value = true;
    initializationError.value = "";
    try {
      const response = await getCurrentUser();
      user.value = response?.data?.user || null;
    } catch (error) {
      user.value = null;
      if (error?.response?.status && error.response.status !== 401) {
        initializationError.value =
          error.response?.data?.message || "身份服务暂不可用";
      }
    } finally {
      initialized.value = true;
      loading.value = false;
    }
    return user.value;
  }

  async function login(phone, password) {
    const response = await loginWithPassword(phone, password);
    user.value = response?.data?.user || null;
    initialized.value = true;
    initializationError.value = "";
    return user.value;
  }

  async function logout() {
    try {
      await logoutSession();
    } finally {
      user.value = null;
      initialized.value = true;
    }
  }

  if (typeof window !== "undefined") {
    window.addEventListener("iam:unauthorized", () => {
      user.value = null;
      initialized.value = true;
    });
  }

  return {
    user,
    loading,
    initialized,
    initializationError,
    isAuthenticated,
    isSuperAdministrator,
    isAdministrator,
    hasPermission,
    initialize,
    login,
    logout
  };
});
