import {
  createRouter,
  createWebHistory
} from "vue-router";

import AdminLayout from "../layouts/AdminLayout.vue";
import Dashboard from "../views/Dashboard.vue";
import ProductList from "../views/ProductList.vue";
import ProductEdit from "../views/ProductEdit.vue";

const routes = [
  {
    path: "/",
    component: AdminLayout,
    redirect: "/dashboard",

    children: [
      {
        path: "dashboard",
        name: "Dashboard",
        component: Dashboard,
        meta: {
          title: "仪表盘",
          icon: "DataAnalysis"
        }
      },

      {
        path: "products",
        name: "ProductList",
        component: ProductList,
        meta: {
          title: "商品管理",
          icon: "Goods"
        }
      },

      {
        path: "products/:id/edit",
        name: "ProductEdit",
        component: ProductEdit,
        meta: {
          title: "编辑商品",
          icon: "Edit"
        }
      }
    ]
  },

  {
    path: "/:pathMatch(.*)*",
    redirect: "/dashboard"
  }
];

const router = createRouter({
  history: createWebHistory(),

  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }

    return false;
  },

  routes
});

router.beforeEach((to) => {
  const title = to.meta?.title
    ? `${to.meta.title} - PPE Product Admin`
    : "PPE Product Admin";

  document.title = title;

  return true;
});

export default router;
