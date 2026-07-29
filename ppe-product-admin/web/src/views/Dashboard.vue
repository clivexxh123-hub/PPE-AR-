<script setup>
import { onMounted, ref } from "vue";

import {
  getCategories,
  getProducts
} from "../api/product";

const loading = ref(false);

const statistics = ref({
  totalProducts: 0,
  uploadedProducts: 0,
  pendingProducts: 0,
  categoryCount: 0
});

const recentProducts = ref([]);

async function loadDashboard() {
  loading.value = true;

  try {
    const [
      productResponse,
      uploadedResponse,
      categoryResponse
    ] = await Promise.all([
      getProducts({
        page: 1,
        size: 6,
        status: 1
      }),

      getProducts({
        page: 1,
        size: 1,
        status: 1,
        has_files: 1
      }),

      getCategories()
    ]);

    const totalProducts = Number(
      productResponse?.total || 0
    );

    const uploadedProducts = Number(
      uploadedResponse?.total || 0
    );

    statistics.value = {
      totalProducts,
      uploadedProducts,
      pendingProducts: Math.max(
        0,
        totalProducts - uploadedProducts
      ),
      categoryCount:
        categoryResponse?.data?.length || 0
    };

    recentProducts.value =
      productResponse?.list || [];
  } finally {
    loading.value = false;
  }
}

function formatDate(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", {
    hour12: false
  });
}

onMounted(() => {
  loadDashboard();
});
</script>

<template>
  <div
    v-loading="loading"
    class="dashboard-page"
  >
    <section class="welcome-card">
      <div>
        <span class="welcome-label">
          PPE PRODUCT MANAGEMENT
        </span>

        <h2>商品资料管理中心</h2>

        <p>
          管理商品分类、商品基础信息、颜色以及商品图片文件。
        </p>
      </div>

      <div class="welcome-decoration">
        <el-icon :size="72">
          <Goods />
        </el-icon>
      </div>
    </section>

    <section class="stat-grid">
      <article class="stat-card">
        <div class="stat-icon blue">
          <el-icon :size="24">
            <Goods />
          </el-icon>
        </div>

        <div class="stat-content">
          <span>商品总数</span>
          <strong>
            {{ statistics.totalProducts.toLocaleString() }}
          </strong>
          <small>已聚合商品目录</small>
        </div>
      </article>

      <article class="stat-card">
        <div class="stat-icon green">
          <el-icon :size="24">
            <Picture />
          </el-icon>
        </div>

        <div class="stat-content">
          <span>已有文件</span>
          <strong>
            {{ statistics.uploadedProducts.toLocaleString() }}
          </strong>
          <small>已上传商品文件</small>
        </div>
      </article>

      <article class="stat-card">
        <div class="stat-icon orange">
          <el-icon :size="24">
            <Warning />
          </el-icon>
        </div>

        <div class="stat-content">
          <span>待补充文件</span>
          <strong>
            {{ statistics.pendingProducts.toLocaleString() }}
          </strong>
          <small>尚未上传商品图片</small>
        </div>
      </article>

      <article class="stat-card">
        <div class="stat-icon purple">
          <el-icon :size="24">
            <Collection />
          </el-icon>
        </div>

        <div class="stat-content">
          <span>二级分类</span>
          <strong>
            {{ statistics.categoryCount.toLocaleString() }}
          </strong>
          <small>当前有效分类</small>
        </div>
      </article>
    </section>

    <section class="dashboard-grid">
      <el-card
        shadow="never"
        class="dashboard-card recent-card"
      >
        <template #header>
          <div class="card-header">
            <div>
              <h3>最近商品</h3>
              <p>最新录入或更新的商品记录</p>
            </div>

            <router-link
              to="/products"
              class="header-link"
            >
              查看全部
              <el-icon>
                <ArrowRight />
              </el-icon>
            </router-link>
          </div>
        </template>

        <el-table
          :data="recentProducts"
          stripe
          style="width: 100%"
        >
          <el-table-column
            prop="goods_no"
            label="商品编号"
            width="150"
          />

          <el-table-column
            prop="product_name"
            label="商品名称"
            min-width="240"
            show-overflow-tooltip
          />

          <el-table-column
            prop="category_level_3"
            label="三级分类"
            width="140"
          />

          <el-table-column
            label="文件"
            width="90"
            align="center"
          >
            <template #default="{ row }">
              <el-tag
                v-if="row.has_files"
                type="success"
                effect="light"
              >
                已上传
              </el-tag>

              <el-tag
                v-else
                type="info"
                effect="plain"
              >
                未上传
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column
            label="更新时间"
            width="180"
          >
            <template #default="{ row }">
              {{ formatDate(row.updated_at) }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card
        shadow="never"
        class="dashboard-card quick-card"
      >
        <template #header>
          <div class="card-header">
            <div>
              <h3>快速入口</h3>
              <p>常用商品管理功能</p>
            </div>
          </div>
        </template>

        <div class="quick-actions">
          <router-link
            to="/products"
            class="quick-action"
          >
            <div class="quick-action-icon">
              <el-icon :size="22">
                <Search />
              </el-icon>
            </div>

            <div>
              <strong>查询商品</strong>
              <span>搜索商品及分类</span>
            </div>

            <el-icon class="quick-arrow">
              <ArrowRight />
            </el-icon>
          </router-link>

          <router-link
            to="/products"
            class="quick-action"
          >
            <div class="quick-action-icon">
              <el-icon :size="22">
                <Edit />
              </el-icon>
            </div>

            <div>
              <strong>编辑商品</strong>
              <span>维护商品基础资料</span>
            </div>

            <el-icon class="quick-arrow">
              <ArrowRight />
            </el-icon>
          </router-link>

          <router-link
            to="/products"
            class="quick-action"
          >
            <div class="quick-action-icon">
              <el-icon :size="22">
                <Upload />
              </el-icon>
            </div>

            <div>
              <strong>上传文件</strong>
              <span>补充商品图片文件</span>
            </div>

            <el-icon class="quick-arrow">
              <ArrowRight />
            </el-icon>
          </router-link>
        </div>
      </el-card>
    </section>
  </div>
</template>
