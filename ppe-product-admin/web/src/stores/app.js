import { defineStore } from "pinia";
import { computed, ref } from "vue";

export const useAppStore = defineStore("app", () => {
  const sidebarCollapsed = ref(false);
  const mobileMenuVisible = ref(false);

  const sidebarWidth = computed(() => {
    return sidebarCollapsed.value ? "72px" : "236px";
  });

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  function setSidebarCollapsed(value) {
    sidebarCollapsed.value = Boolean(value);
  }

  function toggleMobileMenu() {
    mobileMenuVisible.value = !mobileMenuVisible.value;
  }

  function closeMobileMenu() {
    mobileMenuVisible.value = false;
  }

  return {
    sidebarCollapsed,
    sidebarWidth,
    mobileMenuVisible,
    toggleSidebar,
    setSidebarCollapsed,
    toggleMobileMenu,
    closeMobileMenu
  };
});
