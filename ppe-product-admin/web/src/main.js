import { createApp } from "vue";
import { createPinia } from "pinia";

import ElementPlus from "element-plus";
import "element-plus/dist/index.css";

import * as ElementPlusIconsVue from "@element-plus/icons-vue";

import App from "./App.vue";
import router from "./router";
import "./assets/iam.css";
import "./style.css";

const app = createApp(App);
const pinia = createPinia();

for (const [key, component] of Object.entries(
  ElementPlusIconsVue
)) {
  app.component(key, component);
}

app.use(pinia);
app.use(router);
app.use(ElementPlus);










/* CATEGORY_DEFAULT_ACTION_FIX_V3 */

/*
 * 分类点击后页面跳到顶部，常见原因：
 *
 * 1. 分类使用 <a href="#">
 * 2. 分类按钮位于 form 内，button 默认执行 submit
 * 3. 分类组件内部存在会改变 URL hash 的链接
 *
 * preventDefault 只阻止浏览器默认跳转，
 * 不会阻止 Vue 的 @click、@node-click 等事件。
 */
if (typeof window !== "undefined") {
  const categorySelector = [
    ".el-tree-node__content",
    ".el-tree-node__label",
    ".el-cascader-node",
    ".el-cascader-node__label",
    ".el-menu-item",
    ".el-sub-menu__title",
    ".category-item",
    ".category-node",
    ".category-menu-item",
    ".category-list",
    ".category-tree",
    "[data-category]",
    "[data-category-id]",
    "[data-category-level]"
  ].join(",");

  document.addEventListener(
    "click",
    (event) => {
      const target = event.target;

      if (!(target instanceof Element)) {
        return;
      }

      const categoryElement =
        target.closest(categorySelector);

      if (!categoryElement) {
        return;
      }

      const anchor = target.closest("a");

      if (anchor) {
        const href = (
          anchor.getAttribute("href") || ""
        ).trim();

        if (
          href === "" ||
          href === "#" ||
          href.startsWith("#") ||
          href.toLowerCase().startsWith(
            "javascript:"
          )
        ) {
          event.preventDefault();
        }
      }

      const button = target.closest("button");

      if (
        button &&
        button.closest("form") &&
        (
          !button.hasAttribute("type") ||
          button.getAttribute("type") === "submit"
        )
      ) {
        event.preventDefault();
      }
    },
    true
  );

  /*
   * 阻止分类区域内按 Enter 导致表单提交。
   */
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key !== "Enter") {
        return;
      }

      const target = event.target;

      if (!(target instanceof Element)) {
        return;
      }

      if (
        target.closest(categorySelector) &&
        target.closest("form")
      ) {
        event.preventDefault();
      }
    },
    true
  );
}

/* END CATEGORY_DEFAULT_ACTION_FIX_V3 */


app.mount("#app");
