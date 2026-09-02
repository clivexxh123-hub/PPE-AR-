<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import CaseLibrary from "./CaseLibrary.vue";
import ProductLibrary from "./ProductLibrary.vue";
import "../assets/solution-library.css";

const route = useRoute();
const router = useRouter();

const activeTab = computed(() => (route.query.tab === "cases" ? "cases" : "products"));

function selectTab(tab) {
  const query = { ...route.query };
  if (tab === "cases") query.tab = "cases";
  else delete query.tab;
  router.replace({ path: "/product-library", query });
}
</script>

<template>
  <section class="solution-library">
    <nav class="solution-library-tabs" aria-label="产品与案例库" role="tablist">
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'products'"
        :class="{ active: activeTab === 'products' }"
        @click="selectTab('products')"
      >
        <span class="solution-library-tab-icon">▦</span>
        <span>
          <strong>产品库</strong>
          <small>产品数字资产与 SKU</small>
        </span>
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'cases'"
        :class="{ active: activeTab === 'cases' }"
        @click="selectTab('cases')"
      >
        <span class="solution-library-tab-icon">◇</span>
        <span>
          <strong>行业案例</strong>
          <small>标准方案与生成模板</small>
        </span>
      </button>
    </nav>

    <div class="solution-library-content">
      <ProductLibrary v-if="activeTab === 'products'" />
      <CaseLibrary v-else />
    </div>
  </section>
</template>
