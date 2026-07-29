<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAppStore } from "../stores/app";

const route = useRoute();
const router = useRouter();
const appStore = useAppStore();

const menuItems = [
  {
    path: "/dashboard",
    title: "仪表盘",
    icon: "DataAnalysis"
  },

  {
    path: "/products",
    title: "商品管理",
    icon: "Goods"
  }
];

const currentTitle = computed(() => {
  return route.meta?.title || "PPE Product Admin";
});

function navigate(path) {
  router.push(path);
  appStore.closeMobileMenu();
}
</script>

<template>
  <div class="admin-layout">
    <aside
      class="admin-sidebar"
      :class="{
        collapsed: appStore.sidebarCollapsed,
        'mobile-visible': appStore.mobileMenuVisible
      }"
      :style="{
        width: appStore.sidebarWidth
      }"
    >
      <div class="sidebar-brand">
        <div class="brand-logo">
          P
        </div>

        <div
          v-show="!appStore.sidebarCollapsed"
          class="brand-text"
        >
          <strong>PPE Admin</strong>
          <span>PRODUCT SYSTEM</span>
        </div>
      </div>

      <div class="sidebar-scroll">
        <div
          v-show="!appStore.sidebarCollapsed"
          class="menu-group-title"
        >
          工作台
        </div>

        <nav class="sidebar-menu">
          <button
            v-for="item in menuItems"
            :key="item.path"
            type="button"
            class="sidebar-menu-item"
            :class="{
              active: route.path === item.path
            }"
            @click="navigate(item.path)"
          >
            <el-icon :size="19">
              <component :is="item.icon" />
            </el-icon>

            <span
              v-show="!appStore.sidebarCollapsed"
              class="menu-item-text"
            >
              {{ item.title }}
            </span>
          </button>
        </nav>

        <div
          v-show="!appStore.sidebarCollapsed"
          class="menu-group-title secondary"
        >
          系统功能
        </div>

        <nav class="sidebar-menu">
          <button
            type="button"
            class="sidebar-menu-item disabled"
          >
            <el-icon :size="19">
              <Refresh />
            </el-icon>

            <span
              v-show="!appStore.sidebarCollapsed"
              class="menu-item-text"
            >
              ERP 同步
            </span>

            <span
              v-show="!appStore.sidebarCollapsed"
              class="coming-soon"
            >
              后续
            </span>
          </button>

          <button
            type="button"
            class="sidebar-menu-item disabled"
          >
            <el-icon :size="19">
              <Setting />
            </el-icon>

            <span
              v-show="!appStore.sidebarCollapsed"
              class="menu-item-text"
            >
              系统设置
            </span>

            <span
              v-show="!appStore.sidebarCollapsed"
              class="coming-soon"
            >
              后续
            </span>
          </button>
        </nav>
      </div>

      <div class="sidebar-footer">
        <div class="system-status">
          <span class="system-status-dot"></span>

          <div
            v-show="!appStore.sidebarCollapsed"
            class="system-status-text"
          >
            <strong>系统运行正常</strong>
            <span>API PORT 9530</span>
          </div>
        </div>
      </div>
    </aside>

    <div
      v-if="appStore.mobileMenuVisible"
      class="mobile-overlay"
      @click="appStore.closeMobileMenu"
    ></div>

    <section
      class="admin-main"
      :style="{
        marginLeft: appStore.sidebarWidth
      }"
    >
      <header class="admin-header">
        <div class="header-left">
          <el-button
            text
            class="sidebar-toggle desktop-toggle"
            @click="appStore.toggleSidebar"
          >
            <el-icon :size="21">
              <Fold
                v-if="!appStore.sidebarCollapsed"
              />

              <Expand v-else />
            </el-icon>
          </el-button>

          <el-button
            text
            class="sidebar-toggle mobile-toggle"
            @click="appStore.toggleMobileMenu"
          >
            <el-icon :size="21">
              <Menu />
            </el-icon>
          </el-button>

          <div class="page-title-area">
            <h1>{{ currentTitle }}</h1>

            <el-breadcrumb separator="/">
              <el-breadcrumb-item>
                PPE商品管理
              </el-breadcrumb-item>

              <el-breadcrumb-item>
                {{ currentTitle }}
              </el-breadcrumb-item>
            </el-breadcrumb>
          </div>
        </div>

        <div class="header-right">
          <div class="api-status">
            <span class="api-status-dot"></span>
            API 服务正常
          </div>

          <el-divider direction="vertical" />

          <div class="admin-user">
            <div class="admin-avatar">
              A
            </div>

            <div class="admin-user-info">
              <strong>管理员</strong>
              <span>Administrator</span>
            </div>
          </div>
        </div>
      </header>

      <main class="admin-content">
        <router-view />
      </main>
    </section>
  </div>
</template>
