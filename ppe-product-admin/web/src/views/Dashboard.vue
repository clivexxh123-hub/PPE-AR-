<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { getDashboardStatistics } from "../api/dashboard";
import { getCategories, getProducts } from "../api/product";

const loading = ref(false);
const businessLoading = ref(false);
const periodDays = ref(30);
const catalogStatistics = ref({
  totalProducts: 0,
  uploadedProducts: 0,
  pendingProducts: 0,
  categoryCount: 0
});
const recentProducts = ref([]);

const emptyBusinessStatistics = () => ({
  range: { days: 30, startDate: "", endDate: "" },
  summary: {
    totalImages: 0,
    servicedCustomerDays: 0,
    singleProductImages: 0,
    singleProductShare: 0,
    multiProductImages: 0,
    multiProductShare: 0
  },
  daily: [],
  employeeRanking: [],
  groupRanking: [],
  productRanking: []
});

const businessStatistics = ref(emptyBusinessStatistics());
const todayStatistics = computed(() => (
  businessStatistics.value.daily.at(-1) || { customerCount: 0, imageCount: 0 }
));
const visibleDaily = computed(() => businessStatistics.value.daily.slice(-14).reverse());
const maxDailyImages = computed(() => Math.max(
  1,
  ...businessStatistics.value.daily.map((item) => Number(item.imageCount || 0))
));

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("zh-CN", { hour12: false });
}

function formatDay(value) {
  if (!value) return "-";
  const [, month, day] = String(value).split("-");
  return `${Number(month)}月${Number(day)}日`;
}

function rankWidth(value, rows, field = "imageCount") {
  const maximum = Math.max(1, ...rows.map((row) => Number(row[field] || 0)));
  return `${Math.max(4, (Number(value || 0) / maximum) * 100)}%`;
}

function dailyBarWidth(value) {
  return `${Math.max(2, (Number(value || 0) / maxDailyImages.value) * 100)}%`;
}

async function loadBusinessStatistics() {
  businessLoading.value = true;
  try {
    const response = await getDashboardStatistics(periodDays.value, { silentError: true });
    businessStatistics.value = response?.data || emptyBusinessStatistics();
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "业务统计加载失败");
  } finally {
    businessLoading.value = false;
  }
}

async function loadDashboard() {
  loading.value = true;
  try {
    const [productResponse, uploadedResponse, categoryResponse] = await Promise.all([
      getProducts({ page: 1, size: 6, status: 1 }, { silentError: true }),
      getProducts({ page: 1, size: 1, status: 1, has_files: 1 }, { silentError: true }),
      getCategories({ silentError: true }),
      loadBusinessStatistics()
    ]);
    const totalProducts = Number(productResponse?.total || 0);
    const uploadedProducts = Number(uploadedResponse?.total || 0);
    catalogStatistics.value = {
      totalProducts,
      uploadedProducts,
      pendingProducts: Math.max(0, totalProducts - uploadedProducts),
      categoryCount: categoryResponse?.data?.length || 0
    };
    recentProducts.value = productResponse?.list || [];
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || "仪表盘加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(loadDashboard);
</script>

<template>
  <div v-loading="loading" class="dashboard-page business-dashboard">
    <section class="welcome-card business-welcome-card">
      <div>
        <span class="welcome-label">BUSINESS DATA CENTER</span>
        <h2>业务数据仪表盘</h2>
        <p>汇总客户服务、员工与小组作图效率，以及产品选择情况。</p>
      </div>
      <div class="business-period-control">
        <span>统计周期</span>
        <el-select v-model="periodDays" :loading="businessLoading" @change="loadBusinessStatistics">
          <el-option label="最近7天" :value="7" />
          <el-option label="最近30天" :value="30" />
          <el-option label="最近90天" :value="90" />
        </el-select>
        <el-button :loading="businessLoading" @click="loadBusinessStatistics">刷新</el-button>
      </div>
    </section>

    <section class="dashboard-section-heading">
      <div><span>整体数据</span><h3>每日客户与作图概览</h3></div>
      <small>{{ businessStatistics.range.startDate }} 至 {{ businessStatistics.range.endDate }}</small>
    </section>

    <section class="stat-grid business-stat-grid">
      <article class="stat-card">
        <div class="stat-icon blue"><el-icon :size="24"><User /></el-icon></div>
        <div class="stat-content"><span>今日服务客户</span><strong>{{ todayStatistics.customerCount.toLocaleString() }}</strong><small>以客户归档作图记录去重</small></div>
      </article>
      <article class="stat-card">
        <div class="stat-icon green"><el-icon :size="24"><Picture /></el-icon></div>
        <div class="stat-content"><span>今日作图数量</span><strong>{{ todayStatistics.imageCount.toLocaleString() }}</strong><small>仅统计成功且未删除记录</small></div>
      </article>
      <article class="stat-card">
        <div class="stat-icon purple"><el-icon :size="24"><Goods /></el-icon></div>
        <div class="stat-content"><span>单品作图</span><strong>{{ businessStatistics.summary.singleProductImages.toLocaleString() }}</strong><small>占周期作图 {{ businessStatistics.summary.singleProductShare }}%</small></div>
      </article>
      <article class="stat-card">
        <div class="stat-icon orange"><el-icon :size="24"><Connection /></el-icon></div>
        <div class="stat-content"><span>多品连带作图</span><strong>{{ businessStatistics.summary.multiProductImages.toLocaleString() }}</strong><small>占周期作图 {{ businessStatistics.summary.multiProductShare }}%</small></div>
      </article>
    </section>

    <el-card shadow="never" class="dashboard-card dashboard-daily-card" v-loading="businessLoading">
      <template #header><div class="card-header"><div><h3>每日数据</h3><p>显示最近14天服务客户人数与总作图数量</p></div></div></template>
      <el-table :data="visibleDaily" max-height="520">
        <el-table-column label="日期" width="120"><template #default="{ row }">{{ formatDay(row.date) }}</template></el-table-column>
        <el-table-column prop="customerCount" label="服务客户人数" width="150" align="center" />
        <el-table-column prop="imageCount" label="总作图数量" width="130" align="center" />
        <el-table-column label="作图趋势" min-width="260"><template #default="{ row }"><div class="dashboard-bar-track"><span :style="{ width: dailyBarWidth(row.imageCount) }" /></div></template></el-table-column>
      </el-table>
    </el-card>

    <section class="dashboard-section-heading">
      <div><span>员工维度</span><h3>人员与小组作图排名</h3></div>
    </section>

    <section class="dashboard-ranking-grid" v-loading="businessLoading">
      <el-card shadow="never" class="dashboard-card">
        <template #header><div class="card-header"><div><h3>员工 Top 10</h3><p>按成功作图数量从高到低</p></div></div></template>
        <div v-if="businessStatistics.employeeRanking.length" class="dashboard-rank-list">
          <article v-for="(row, index) in businessStatistics.employeeRanking" :key="row.userId">
            <span class="dashboard-rank-number">{{ index + 1 }}</span>
            <div class="dashboard-rank-body">
              <div><strong>{{ row.name }}</strong><small>{{ row.departmentName ? `${row.departmentName} / ` : "" }}{{ row.orgUnitName }}</small></div>
              <div class="dashboard-bar-track"><span :style="{ width: rankWidth(row.imageCount, businessStatistics.employeeRanking) }" /></div>
            </div>
            <b>{{ row.imageCount }}</b>
          </article>
        </div>
        <el-empty v-else description="当前周期暂无员工作图数据" />
      </el-card>

      <el-card shadow="never" class="dashboard-card">
        <template #header><div class="card-header"><div><h3>小组作图排名</h3><p>采用作图发生时的历史小组归属</p></div></div></template>
        <div v-if="businessStatistics.groupRanking.length" class="dashboard-rank-list">
          <article v-for="(row, index) in businessStatistics.groupRanking" :key="row.orgUnitId || row.name">
            <span class="dashboard-rank-number">{{ index + 1 }}</span>
            <div class="dashboard-rank-body">
              <div><strong>{{ row.name }}</strong><small>{{ row.departmentName || "未分部门" }}</small></div>
              <div class="dashboard-bar-track green"><span :style="{ width: rankWidth(row.imageCount, businessStatistics.groupRanking) }" /></div>
            </div>
            <b>{{ row.imageCount }}</b>
          </article>
        </div>
        <el-empty v-else description="当前周期暂无小组作图数据" />
      </el-card>
    </section>

    <section class="dashboard-section-heading">
      <div><span>产品维度</span><h3>产品类型占比与选择排名</h3></div>
    </section>

    <section class="dashboard-product-grid" v-loading="businessLoading">
      <el-card shadow="never" class="dashboard-card dashboard-share-card">
        <template #header><div class="card-header"><div><h3>单品 / 多品占比</h3><p>按同一作图批次所含产品数归类</p></div></div></template>
        <div class="dashboard-share-row"><div><strong>单品作图</strong><span>{{ businessStatistics.summary.singleProductImages }} 张</span></div><b>{{ businessStatistics.summary.singleProductShare }}%</b></div>
        <el-progress :percentage="businessStatistics.summary.singleProductShare" :stroke-width="12" :show-text="false" />
        <div class="dashboard-share-row multi"><div><strong>多品连带作图</strong><span>{{ businessStatistics.summary.multiProductImages }} 张</span></div><b>{{ businessStatistics.summary.multiProductShare }}%</b></div>
        <el-progress :percentage="businessStatistics.summary.multiProductShare" :stroke-width="12" color="#f79009" :show-text="false" />
      </el-card>

      <el-card shadow="never" class="dashboard-card dashboard-product-ranking">
        <template #header><div class="card-header"><div><h3>选择最多的前10款产品</h3><p>同一批次重复构图只计算一次产品选择</p></div></div></template>
        <el-table :data="businessStatistics.productRanking" max-height="470">
          <el-table-column type="index" label="#" width="52" />
          <el-table-column prop="name" label="产品名称" min-width="230" show-overflow-tooltip />
          <el-table-column prop="code" label="编号" width="115"><template #default="{ row }">{{ row.code || "-" }}</template></el-table-column>
          <el-table-column prop="selectionCount" label="选择次数" width="95" align="center" />
          <el-table-column prop="imageCount" label="作图数" width="85" align="center" />
        </el-table>
      </el-card>
    </section>

    <section class="dashboard-section-heading catalog-heading">
      <div><span>产品资料</span><h3>商品目录概览</h3></div>
    </section>
    <section class="stat-grid catalog-stat-grid">
      <article class="stat-card"><div class="stat-icon blue"><el-icon :size="24"><Goods /></el-icon></div><div class="stat-content"><span>商品总数</span><strong>{{ catalogStatistics.totalProducts.toLocaleString() }}</strong><small>已聚合商品目录</small></div></article>
      <article class="stat-card"><div class="stat-icon green"><el-icon :size="24"><Picture /></el-icon></div><div class="stat-content"><span>已有文件</span><strong>{{ catalogStatistics.uploadedProducts.toLocaleString() }}</strong><small>已上传商品文件</small></div></article>
      <article class="stat-card"><div class="stat-icon orange"><el-icon :size="24"><Warning /></el-icon></div><div class="stat-content"><span>待补充文件</span><strong>{{ catalogStatistics.pendingProducts.toLocaleString() }}</strong><small>尚未上传商品图片</small></div></article>
      <article class="stat-card"><div class="stat-icon purple"><el-icon :size="24"><Collection /></el-icon></div><div class="stat-content"><span>二级分类</span><strong>{{ catalogStatistics.categoryCount.toLocaleString() }}</strong><small>当前有效分类</small></div></article>
    </section>

    <el-card shadow="never" class="dashboard-card dashboard-recent-products">
      <template #header><div class="card-header"><div><h3>最近商品</h3><p>最新录入或更新的商品记录</p></div><router-link to="/products" class="header-link">查看全部<el-icon><ArrowRight /></el-icon></router-link></div></template>
      <el-table :data="recentProducts" stripe>
        <el-table-column prop="goods_no" label="商品编号" width="150" />
        <el-table-column prop="product_name" label="商品名称" min-width="240" show-overflow-tooltip />
        <el-table-column prop="category_level_3" label="三级分类" width="140" />
        <el-table-column label="文件" width="90" align="center"><template #default="{ row }"><el-tag v-if="row.has_files" type="success">已上传</el-tag><el-tag v-else type="info" effect="plain">未上传</el-tag></template></el-table-column>
        <el-table-column label="更新时间" width="180"><template #default="{ row }">{{ formatDate(row.updated_at) }}</template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
