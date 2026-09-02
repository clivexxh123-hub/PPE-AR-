import { createRouter, createWebHistory } from "vue-router";

import AdminLayout from "../layouts/AdminLayout.vue";
import { useAuthStore } from "../stores/auth";
import AccountManage from "../views/AccountManage.vue";
import AIGenerator from "../views/AIGenerator.vue";
import Customers from "../views/Customers.vue";
import Dashboard from "../views/Dashboard.vue";
import GenerationRecords from "../views/GenerationRecords.vue";
import Login from "../views/Login.vue";
import ProductEdit from "../views/ProductEdit.vue";
import SolutionLibrary from "../views/SolutionLibrary.vue";
import ProductList from "../views/ProductList.vue";
import ResourceManage from "../views/ResourceManage.vue";

const routes = [
  {
    path: "/login",
    name: "Login",
    component: Login,
    meta: { title: "登录", public: true }
  },
  {
    path: "/",
    component: AdminLayout,
    redirect: "/dashboard",
    meta: { requiresAuth: true },
    children: [
      {
        path: "dashboard",
        name: "Dashboard",
        component: Dashboard,
        meta: { title: "仪表盘", icon: "DataAnalysis" }
      },
      {
        path: "ai-generator",
        name: "AIGenerator",
        component: AIGenerator,
        meta: { title: "AI生成中心", icon: "MagicStick" }
      },
      {
        path: "case-library",
        redirect: (to) => ({
          path: "/product-library",
          query: { ...to.query, tab: "cases" }
        })
      },
      {
        path: "customers",
        name: "Customers",
        component: Customers,
        meta: {
          title: "客户档案",
          icon: "OfficeBuilding",
          permission: "records.read_all"
        }
      },
      {
        path: "generation-records",
        name: "GenerationRecords",
        component: GenerationRecords,
        meta: {
          title: "作图记录",
          icon: "PictureFilled",
          permission: "records.read_all"
        }
      },
      {
        path: "resource",
        name: "ResourceManage",
        component: ResourceManage,
        meta: { title: "资源管理", icon: "Folder", permission: "catalog.manage" }
      },
      {
        path: "product-library",
        name: "ProductLibrary",
        component: SolutionLibrary,
        meta: { title: "产品与案例库", icon: "Box" }
      },
      {
        path: "products",
        name: "ProductList",
        component: ProductList,
        meta: { title: "商品管理", icon: "Goods", permission: "catalog.manage" }
      },
      {
        path: "products/:id/edit",
        name: "ProductEdit",
        component: ProductEdit,
        meta: { title: "编辑商品", icon: "Edit", permission: "catalog.manage" }
      },
      {
        path: "accounts",
        name: "AccountManage",
        component: AccountManage,
        meta: {
          title: "账号管理",
          icon: "UserFilled",
          permission: "system.manage"
        }
      }
    ]
  },
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || false;
  }
});

router.beforeEach(async (to) => {
  document.title = to.meta?.title
    ? `${to.meta.title} - PPE AI Platform`
    : "PPE AI Platform";

  const authStore = useAuthStore();
  if (!authStore.initialized) {
    await authStore.initialize();
  }

  if (to.meta.public) {
    if (to.name === "Login" && authStore.isAuthenticated) return "/dashboard";
    return true;
  }

  if (to.matched.some((record) => record.meta.requiresAuth) && !authStore.isAuthenticated) {
    return {
      name: "Login",
      query: { redirect: to.fullPath }
    };
  }

  const permission = to.meta.permission;
  if (permission && !authStore.hasPermission(permission)) return "/dashboard";
  return true;
});

if (typeof window !== "undefined") {
  window.addEventListener("iam:unauthorized", () => {
    if (router.currentRoute.value.name !== "Login") {
      router.replace({
        name: "Login",
        query: { redirect: router.currentRoute.value.fullPath }
      });
    }
  });
}

export default router;
