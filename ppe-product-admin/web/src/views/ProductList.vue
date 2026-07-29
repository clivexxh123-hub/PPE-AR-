<script setup>
const productEditRouter = useRouter()

import {
  computed,
  nextTick,
  onMounted,
  reactive,
  ref,
  watch
} from "vue";

import {
  useRoute,
  useRouter
} from "vue-router";

import {
  getCategories,
  getProductDetail,
  getProducts,
  updateProduct} from "../api/product";

import {
  ElMessage
} from "element-plus";

const route = useRoute();
const router = useRouter();

/* ================================
 * 页面状态
 * ================================ */

const loading = ref(false);
const categoryLoading = ref(false);
const detailLoading = ref(false);

const productList = ref([]);
const categoryTree = ref([]);
const rawCategories = ref([]);

const total = ref(0);

const detailVisible = ref(false);
const currentProduct = ref(null);

const tableRef = ref(null);
const searchInputRef = ref(null);

const isFilterExpanded = ref(true);

/* ================================
 * 查询参数
 * ================================ */

const query = reactive({
  page: Number(route.query.page) || 1,
  size: Number(route.query.size) || 20,

  keyword: route.query.keyword || "",

  category_level_1:
    route.query.category_level_1 || "",

  category_level_2:
    route.query.category_level_2 || "",

  category_level_3:
    route.query.category_level_3 || "",

  has_files:
    route.query.has_files === undefined
      ? ""
      : String(route.query.has_files),

  status:
    route.query.status === undefined
      ? ""
      : String(route.query.status)
});

/* ================================
 * 数据兼容函数
 * ================================ */

function getResponsePayload(response) {
  if (!response) {
    return {};
  }

  if (
    response.data &&
    typeof response.data === "object" &&
    !Array.isArray(response.data)
  ) {
    return response.data;
  }

  return response;
}

function getResponseList(response) {
  const payload = getResponsePayload(response);

  const possibleLists = [
    payload.list,
    payload.rows,
    payload.items,
    payload.records,
    payload.products,
    response?.list,
    response?.rows,
    response?.items,
    response?.records,
    response?.products
  ];

  const matched = possibleLists.find(
    (item) => Array.isArray(item)
  );

  if (matched) {
    return matched;
  }

  if (Array.isArray(response?.data)) {
    return response.data;
  }

  if (Array.isArray(response)) {
    return response;
  }

  return [];
}

function getResponseTotal(response, list = []) {
  const payload = getResponsePayload(response);

  const possibleTotals = [
    payload.total,
    payload.count,
    payload.total_count,
    response?.total,
    response?.count,
    response?.total_count
  ];

  const matched = possibleTotals.find(
    (item) =>
      item !== undefined &&
      item !== null &&
      item !== ""
  );

  if (matched !== undefined) {
    return Number(matched) || 0;
  }

  return list.length;
}

function parseJsonArray(value) {
  if (Array.isArray(value)) {
    return value;
  }

  if (!value) {
    return [];
  }

  if (typeof value === "string") {
    const text = value.trim();

    if (!text) {
      return [];
    }

    try {
      const parsed = JSON.parse(text);

      if (Array.isArray(parsed)) {
        return parsed;
      }
    } catch {
      return text
        .split(/[,，、/]/)
        .map((item) => item.trim())
        .filter(Boolean);
    }
  }

  return [];
}

function normalizeProduct(row) {
  const files = Array.isArray(row.files)
    ? row.files
    : [];

  const fileCount = Number(
    row.file_count ??
    row.files_count ??
    files.length ??
    0
  );

  const hasFiles =
    Number(row.has_files) === 1 ||
    row.has_files === true ||
    fileCount > 0;

  return {
    ...row,

    id:
      row.id ??
      row.product_id ??
      row.catalog_id,

    goods_no:
      row.goods_no ??
      row.goodsNo ??
      row.product_no ??
      row.product_code ??
      row.erp_goods_no ??
      "-",

    product_name:
      row.product_name ??
      row.goods_name ??
      row.goodsName ??
      row.name ??
      "-",

    brand_name:
      row.brand_name ??
      row.brand ??
      row.brandName ??
      "-",

    category_level_1:
      row.category_level_1 ??
      row.category1 ??
      row.first_category ??
      "",

    category_level_2:
      row.category_level_2 ??
      row.category2 ??
      row.second_category ??
      "",

    category_level_3:
      row.category_level_3 ??
      row.category3 ??
      row.third_category ??
      "",

    colors: parseJsonArray(
      row.colors ??
      row.color_list ??
      row.product_colors
    ),

    has_files: hasFiles,
    file_count: fileCount,

    cover_url:
      row.cover_url ??
      row.thumbnail_url ??
      row.main_image ??
      row.image_url ??
      row.file_url ??
      files?.[0]?.file_url ??
      "",

    updated_at:
      row.updated_at ??
      row.update_time ??
      row.modified_at ??
      row.created_at ??
      ""
  };
}

/* ================================
 * 分类数据处理
 * ================================ */

function normalizeCategoryItem(item) {
  return {
    id:
      item.id ??
      item.category_id ??
      `${item.level_1 || ""}-${item.level_2 || ""}-${item.level_3 || ""}`,

    level_1:
      item.category_level_1 ??
      item.level_1 ??
      item.category1 ??
      item.first_category ??
      "",

    level_2:
      item.category_level_2 ??
      item.level_2 ??
      item.category2 ??
      item.second_category ??
      "",

    level_3:
      item.category_level_3 ??
      item.level_3 ??
      item.category3 ??
      item.third_category ??
      "",

    product_count: Number(
      item.product_count ??
      item.count ??
      item.total ??
      0
    )
  };
}

function buildCategoryTree(items) {
  const level1Map = new Map();

  items.forEach((rawItem) => {
    const item = normalizeCategoryItem(rawItem);

    if (!item.level_1) {
      return;
    }

    if (!level1Map.has(item.level_1)) {
      level1Map.set(item.level_1, {
        id: `l1-${item.level_1}`,
        label: item.level_1,
        level: 1,
        value: item.level_1,
        count: 0,
        children: [],
        level2Map: new Map()
      });
    }

    const level1Node = level1Map.get(item.level_1);
    level1Node.count += item.product_count;

    if (!item.level_2) {
      return;
    }

    if (!level1Node.level2Map.has(item.level_2)) {
      level1Node.level2Map.set(item.level_2, {
        id: `l2-${item.level_1}-${item.level_2}`,
        label: item.level_2,
        level: 2,
        value: item.level_2,
        parentLevel1: item.level_1,
        count: 0,
        children: [],
        level3Map: new Map()
      });
    }

    const level2Node =
      level1Node.level2Map.get(item.level_2);

    level2Node.count += item.product_count;

    if (!item.level_3) {
      return;
    }

    if (!level2Node.level3Map.has(item.level_3)) {
      level2Node.level3Map.set(item.level_3, {
        id:
          `l3-${item.level_1}-${item.level_2}-${item.level_3}`,

        label: item.level_3,
        level: 3,
        value: item.level_3,
        parentLevel1: item.level_1,
        parentLevel2: item.level_2,
        count: item.product_count
      });
    } else {
      const existing =
        level2Node.level3Map.get(item.level_3);

      existing.count += item.product_count;
    }
  });

  return Array.from(level1Map.values()).map(
    (level1Node) => {
      level1Node.children = Array.from(
        level1Node.level2Map.values()
      ).map((level2Node) => {
        level2Node.children = Array.from(
          level2Node.level3Map.values()
        );

        delete level2Node.level3Map;

        return level2Node;
      });

      delete level1Node.level2Map;

      return level1Node;
    }
  );
}

function flattenCategoryResponse(response) {
  const source = Array.isArray(response?.data)
    ? response.data
    : [];

  const result = [];

  source.forEach((level2Item) => {
    const level1 = level2Item.level1 || "";
    const level2 = level2Item.name || "";
    const children = Array.isArray(level2Item.children)
      ? level2Item.children
      : [];

    if (!children.length) {
      result.push({
        level_1: level1,
        level_2: level2,
        level_3: "",
        product_count: Number(
          level2Item.count || 0
        )
      });

      return;
    }

    children.forEach((level3Item) => {
      result.push({
        level_1: level1,
        level_2: level2,
        level_3: level3Item.name || "",
        product_count: Number(
          level3Item.count || 0
        )
      });
    });
  });

  return result;
}

async function loadCategories() {
  categoryLoading.value = true;

  try {
    const response = await getCategories();

    const list = flattenCategoryResponse(response);

    rawCategories.value = list;
    categoryTree.value = buildCategoryTree(list);
  } catch (error) {
    console.error("加载分类失败：", error);
  } finally {
    categoryLoading.value = false;
  }
}

/* ================================
 * 分类下拉选项
 * ================================ */

const level1Options = computed(() => {
  const set = new Set();

  rawCategories.value.forEach((item) => {
    const category = normalizeCategoryItem(item);

    if (category.level_1) {
      set.add(category.level_1);
    }
  });

  return Array.from(set);
});

const level2Options = computed(() => {
  const set = new Set();

  rawCategories.value.forEach((item) => {
    const category = normalizeCategoryItem(item);

    if (
      query.category_level_1 &&
      category.level_1 !== query.category_level_1
    ) {
      return;
    }

    if (category.level_2) {
      set.add(category.level_2);
    }
  });

  return Array.from(set);
});

const level3Options = computed(() => {
  const set = new Set();

  rawCategories.value.forEach((item) => {
    const category = normalizeCategoryItem(item);

    if (
      query.category_level_1 &&
      category.level_1 !== query.category_level_1
    ) {
      return;
    }

    if (
      query.category_level_2 &&
      category.level_2 !== query.category_level_2
    ) {
      return;
    }

    if (category.level_3) {
      set.add(category.level_3);
    }
  });

  return Array.from(set);
});

/* ================================
 * 商品列表
 * ================================ */

function buildRequestParams() {
  const params = {
    page: query.page,
    size: query.size
  };

  const keyword = query.keyword.trim();

  if (keyword) {
    params.keyword = keyword;
  }

  /*
   * 分类参数同时保留标准字段和兼容字段。
   * 后端识别其中任意一种即可。
   */
  if (query.category_level_1) {
    params.category_level_1 = query.category_level_1;
    params.level1 = query.category_level_1;
    params.category1 = query.category_level_1;
  }

  if (query.category_level_2) {
    params.category_level_2 = query.category_level_2;
    params.level2 = query.category_level_2;
    params.category2 = query.category_level_2;
  }

  if (query.category_level_3) {
    params.category_level_3 = query.category_level_3;
    params.level3 = query.category_level_3;
    params.category3 = query.category_level_3;
  }

  if (query.has_files !== "") {
    params.has_files = Number(query.has_files);
  }

  if (query.status !== "") {
    params.status = Number(query.status);
  }

  return params;
}

async function loadProducts(options = {}) {
  const {
    scrollTop = false,
    showMessage = false
  } = options;

  loading.value = true;

  try {
    const response = await getProducts(
      buildRequestParams()
    );

    const list = getResponseList(response);

    productList.value = list.map(
      normalizeProduct
    );

    total.value = getResponseTotal(
      response,
      productList.value
    );

    syncQueryToUrl();

    if (scrollTop) {
      await nextTick();

      document
        .querySelector(".admin-content")
        ?.scrollTo({
          top: 0,
          behavior: "smooth"
        });
    }

    if (showMessage) {
      ElMessage.success("商品列表已刷新");
    }
  } catch (error) {
    console.error("加载商品失败：", error);

    productList.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

/* ================================
 * URL 同步
 * ================================ */

function syncQueryToUrl() {
  const urlQuery = {};

  if (query.page !== 1) {
    urlQuery.page = String(query.page);
  }

  if (query.size !== 20) {
    urlQuery.size = String(query.size);
  }

  if (query.keyword.trim()) {
    urlQuery.keyword = query.keyword.trim();
  }

  if (query.category_level_1) {
    urlQuery.category_level_1 =
      query.category_level_1;
  }

  if (query.category_level_2) {
    urlQuery.category_level_2 =
      query.category_level_2;
  }

  if (query.category_level_3) {
    urlQuery.category_level_3 =
      query.category_level_3;
  }

  if (query.has_files !== "") {
    urlQuery.has_files = query.has_files;
  }

  if (query.status !== "") {
    urlQuery.status = query.status;
  }

  router.replace({
    path: route.path,
    query: urlQuery
  });
}

/* ================================
 * 搜索和筛选
 * ================================ */

function handleSearch() {
  query.page = 1;

  loadProducts({
    scrollTop: true
  });
}

function handleReset() {
  query.page = 1;
  query.size = 20;
  query.keyword = "";

  query.category_level_1 = "";
  query.category_level_2 = "";
  query.category_level_3 = "";

  query.has_files = "";
  query.status = "";

  loadProducts({
    scrollTop: true
  });
}

function handleRefresh() {
  loadProducts({
    showMessage: true
  });
}

function handleLevel1Change() {
  query.category_level_2 = "";
  query.category_level_3 = "";
}

function handleLevel2Change() {
  query.category_level_3 = "";
}

function handlePageChange(page) {
  query.page = page;

  loadProducts({
    scrollTop: true
  });
}

function handleSizeChange(size) {
  query.size = size;
  query.page = 1;

  loadProducts({
    scrollTop: true
  });
}

/* ================================
 * 左侧分类树
 * ================================ */

async function handleCategoryNodeClick(node) {
  query.page = 1;

  if (node.level === 1) {
    query.category_level_1 = node.value;
    query.category_level_2 = "";
    query.category_level_3 = "";
  } else if (node.level === 2) {
    query.category_level_1 = node.parentLevel1;
    query.category_level_2 = node.value;
    query.category_level_3 = "";
  } else if (node.level === 3) {
    query.category_level_1 = node.parentLevel1;
    query.category_level_2 = node.parentLevel2;
    query.category_level_3 = node.value;
  }

  console.log("当前分类筛选：", {
    category_level_1: query.category_level_1,
    category_level_2: query.category_level_2,
    category_level_3: query.category_level_3
  });

  await loadProducts({
    scrollTop: true
  });
}

function showAllCategories() {
  query.page = 1;

  query.category_level_1 = "";
  query.category_level_2 = "";
  query.category_level_3 = "";

  loadProducts({
    scrollTop: true
  });
}

const isAllCategoryActive = computed(() => {
  return (
    !query.category_level_1 &&
    !query.category_level_2 &&
    !query.category_level_3
  );
});

/* ================================
 * 筛选标签
 * ================================ */

const activeFilters = computed(() => {
  const filters = [];

  if (query.keyword.trim()) {
    filters.push({
      key: "keyword",
      label: `关键词：${query.keyword.trim()}`
    });
  }

  if (query.category_level_1) {
    filters.push({
      key: "category_level_1",
      label: `一级分类：${query.category_level_1}`
    });
  }

  if (query.category_level_2) {
    filters.push({
      key: "category_level_2",
      label: `二级分类：${query.category_level_2}`
    });
  }

  if (query.category_level_3) {
    filters.push({
      key: "category_level_3",
      label: `三级分类：${query.category_level_3}`
    });
  }

  if (query.has_files === "1") {
    filters.push({
      key: "has_files",
      label: "已有文件"
    });
  }

  if (query.has_files === "0") {
    filters.push({
      key: "has_files",
      label: "未上传文件"
    });
  }

  if (query.status === "1") {
    filters.push({
      key: "status",
      label: "有效商品"
    });
  }

  if (query.status === "0") {
    filters.push({
      key: "status",
      label: "停用商品"
    });
  }

  return filters;
});

function removeFilter(key) {
  query.page = 1;

  if (key === "keyword") {
    query.keyword = "";
  }

  if (key === "category_level_1") {
    query.category_level_1 = "";
    query.category_level_2 = "";
    query.category_level_3 = "";
  }

  if (key === "category_level_2") {
    query.category_level_2 = "";
    query.category_level_3 = "";
  }

  if (key === "category_level_3") {
    query.category_level_3 = "";
  }

  if (key === "has_files") {
    query.has_files = "";
  }

  if (key === "status") {
    query.status = "";
  }

  loadProducts();
}

/* ================================
 * 商品详情
 * ================================ */

async function openProductDetail(row) {
  detailVisible.value = true;
  detailLoading.value = true;

  currentProduct.value = normalizeProduct(row);

  try {
    const response = await getProductDetail(
      row.id
    );

    const payload = getResponsePayload(response);

    const detail =
      payload.product ??
      payload.detail ??
      payload;

    currentProduct.value = normalizeProduct({
      ...row,
      ...detail
    });
  } catch (error) {
    console.error("加载商品详情失败：", error);
  } finally {
    detailLoading.value = false;
  }
}

function closeProductDetail() {
  detailVisible.value = false;
  currentProduct.value = null;
}

/* ================================
 * 图片与格式化
 * ================================ */

function getFileUrl(url) {
  if (!url) {
    return "";
  }

  if (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("data:")
  ) {
    return url;
  }

  if (url.startsWith("/")) {
    return url;
  }

  return `/${url}`;
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
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

function getCategoryPath(row) {
  return [
    row.category_level_1,
    row.category_level_2,
    row.category_level_3
  ]
    .filter(Boolean)
    .join(" / ") || "-";
}

/* PRODUCT_EDIT_LOGIC_V1 */

const editDialogVisible = ref(false);
const editLoading = ref(false);
const editSaving = ref(false);
const editFormRef = ref(null);

const editForm = reactive({
  id: null,
  goods_no: "",
  product_name: "",
  brand_name: "",
  category_level_1: "",
  category_level_2: "",
  category_level_3: "",
  colors_text: "",
  status: 1
});

const editRules = {
  product_name: [
    {
      required: true,
      message: "请输入商品名称",
      trigger: "blur"
    }
  ]
};

function resetEditForm() {
  editForm.id = null;
  editForm.goods_no = "";
  editForm.product_name = "";
  editForm.brand_name = "";
  editForm.category_level_1 = "";
  editForm.category_level_2 = "";
  editForm.category_level_3 = "";
  editForm.colors_text = "";
  editForm.status = 1;
}

function fillEditForm(product) {
  const data = product || {};

  editForm.id =
    data.id ??
    data.product_id ??
    null;

  editForm.goods_no =
    data.goods_no ??
    data.goodsNo ??
    data.product_no ??
    "";

  editForm.product_name =
    data.product_name ??
    data.goods_name ??
    data.goodsName ??
    data.name ??
    "";

  editForm.brand_name =
    data.brand_name ??
    data.brand ??
    data.brandName ??
    "";

  editForm.category_level_1 =
    data.category_level_1 ??
    data.level_1 ??
    data.category1 ??
    "";

  editForm.category_level_2 =
    data.category_level_2 ??
    data.level_2 ??
    data.category2 ??
    "";

  editForm.category_level_3 =
    data.category_level_3 ??
    data.level_3 ??
    data.category3 ??
    "";

  const colors =
    data.colors ??
    data.color_list ??
    data.product_colors ??
    [];

  if (Array.isArray(colors)) {
    editForm.colors_text =
      colors.join("、");
  } else {
    editForm.colors_text =
      String(colors || "");
  }

  editForm.status =
    Number(data.status ?? 1);
}


function openProductEditor(row) {
  const source =
    row ||
    detailProduct?.value ||
    selectedProduct?.value ||
    {}

  const id =
    source.id ??
    source.product_id

  if (!id) {
    ElMessage.warning("未找到商品 ID")
    return
  }

  productEditRouter.push(
    `/products/${id}/edit`
  )
}


function closeEditDialog() {
  editDialogVisible.value = false;
  resetEditForm();

  if (editFormRef.value) {
    editFormRef.value.clearValidate?.();
  }
}

async function submitProductEdit() {
  if (!editForm.id) {
    ElMessage.warning("商品 ID 不存在");
    return;
  }

  try {
    await editFormRef.value?.validate();
  } catch {
    return;
  }

  const colors = editForm.colors_text
    .split(/[,，、/]/)
    .map(item => item.trim())
    .filter(Boolean);

  const payload = {
    goods_no: editForm.goods_no.trim(),
    product_name: editForm.product_name.trim(),

    // 同时提交两种品牌字段，兼容现有后端字段命名
    brand_name: editForm.brand_name.trim(),
    brand: editForm.brand_name.trim(),

    category_level_1:
      editForm.category_level_1.trim(),

    category_level_2:
      editForm.category_level_2.trim(),

    category_level_3:
      editForm.category_level_3.trim(),

    colors,
    color_list: colors,
    status: Number(editForm.status)
  };

  editSaving.value = true;

  try {
    await updateProduct(
      editForm.id,
      payload
    );

    ElMessage.success("商品资料保存成功");

    editDialogVisible.value = false;

    // 如果详情抽屉处于打开状态，立即同步展示内容
    if (
      typeof detailProduct !== "undefined" &&
      detailProduct?.value
    ) {
      detailProduct.value = {
        ...detailProduct.value,
        ...payload,
        colors
      };
    }

    /*
     * ProductList.vue 当前商品加载函数通常为 loadProducts。
     * 存在时刷新列表；不存在时不阻断保存流程。
     */
    if (
      typeof loadProducts === "function"
    ) {
      await loadProducts();
    }

    resetEditForm();
  } catch (error) {
    console.error(
      "保存商品资料失败：",
      error
    );
  } finally {
    editSaving.value = false;
  }
}

/* END_PRODUCT_EDIT_LOGIC_V1 */

function handleFilePlaceholder() {
  ElMessage.info(
    "文件上传管理将在 Phase 3 开放"
  );
}

/* ================================
 * 监听器
 * ================================ */

watch(
  () => query.category_level_1,
  (newValue, oldValue) => {
    if (
      oldValue !== undefined &&
      newValue !== oldValue
    ) {
      const validLevel2 =
        level2Options.value.includes(
          query.category_level_2
        );

      if (!validLevel2) {
        query.category_level_2 = "";
        query.category_level_3 = "";
      }
    }
  }
);

watch(
  () => query.category_level_2,
  (newValue, oldValue) => {
    if (
      oldValue !== undefined &&
      newValue !== oldValue
    ) {
      const validLevel3 =
        level3Options.value.includes(
          query.category_level_3
        );

      if (!validLevel3) {
        query.category_level_3 = "";
      }
    }
  }
);

onMounted(async () => {
  await loadCategories();
  await loadProducts();
});


function openDetailProductEditor() {
  const source = currentProduct.value || {};

  const id =
    source.id ??
    source.product_id ??
    source.database_id;

  if (!id) {
    ElMessage.warning("未找到商品数据库 ID");
    console.error("当前商品数据：", source);
    return;
  }

  detailVisible.value = false;

  productEditRouter.push({
    name: "ProductEdit",
    params: {
      id
    }
  });
}

</script>

<template>
  <div class="product-management-page">
    <section class="product-page-toolbar">
      <div class="product-page-heading">
        <div>
          <h2>商品列表</h2>

          <p>
            查询和管理聚合后的 PPE 商品资料
          </p>
        </div>

        <div class="product-toolbar-actions">
          <el-button
            @click="isFilterExpanded = !isFilterExpanded"
          >
            <el-icon>
              <Filter />
            </el-icon>

            {{ isFilterExpanded ? "收起筛选" : "展开筛选" }}
          </el-button>

          <el-button
            :loading="loading"
            @click="handleRefresh"
          >
            <el-icon>
              <Refresh />
            </el-icon>

            刷新
          </el-button>
        </div>
      </div>
    </section>

    <section
      v-show="isFilterExpanded"
      class="product-filter-panel"
    >
      <el-form
        label-position="top"
        class="product-filter-form"
        @submit.prevent="handleSearch"
      >
        <el-form-item
          label="商品关键词"
          class="filter-keyword-item"
        >
          <el-input
            ref="searchInputRef"
            v-model="query.keyword"
            clearable
            placeholder="商品名称、商品编号或品牌"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon>
                <Search />
              </el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="一级分类">
          <el-select
            v-model="query.category_level_1"
            clearable
            filterable
            placeholder="全部一级分类"
            @change="handleLevel1Change"
          >
            <el-option
              v-for="item in level1Options"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="二级分类">
          <el-select
            v-model="query.category_level_2"
            clearable
            filterable
            :disabled="!level2Options.length"
            placeholder="全部二级分类"
            @change="handleLevel2Change"
          >
            <el-option
              v-for="item in level2Options"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="三级分类">
          <el-select
            v-model="query.category_level_3"
            clearable
            filterable
            :disabled="!level3Options.length"
            placeholder="全部三级分类"
          >
            <el-option
              v-for="item in level3Options"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="文件状态">
          <el-select
            v-model="query.has_files"
            clearable
            placeholder="全部状态"
          >
            <el-option
              label="已有文件"
              value="1"
            />

            <el-option
              label="未上传文件"
              value="0"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="商品状态">
          <el-select
            v-model="query.status"
            clearable
            placeholder="全部状态"
          >
            <el-option
              label="有效"
              value="1"
            />

            <el-option
              label="停用"
              value="0"
            />
          </el-select>
        </el-form-item>

        <div class="filter-action-group">
          <el-button
            type="primary"
            :loading="loading"
            @click="handleSearch"
          >
            <el-icon>
              <Search />
            </el-icon>

            查询
          </el-button>

          <el-button @click="handleReset">
            重置
          </el-button>
        </div>
      </el-form>

      <div
        v-if="activeFilters.length"
        class="active-filter-bar"
      >
        <span class="active-filter-label">
          当前筛选：
        </span>

        <el-tag
          v-for="item in activeFilters"
          :key="item.key"
          closable
          effect="plain"
          @close="removeFilter(item.key)"
        >
          {{ item.label }}
        </el-tag>

        <el-button
          link
          type="primary"
          @click="handleReset"
        >
          清除全部
        </el-button>
      </div>
    </section>

    <section class="product-workspace">
      <aside class="product-category-panel">
        <div class="category-panel-header">
          <div>
            <h3>商品分类</h3>
            <span>按分类快速筛选</span>
          </div>

          <el-tooltip
            content="重新加载分类"
            placement="top"
          >
            <el-button
              text
              circle
              :loading="categoryLoading"
              @click="loadCategories"
            >
              <el-icon>
                <Refresh />
              </el-icon>
            </el-button>
          </el-tooltip>
        </div>

        <button
          type="button"
          class="all-category-button"
          :class="{
            active: isAllCategoryActive
          }"
          @click="showAllCategories"
        >
          <div>
            <el-icon>
              <Grid />
            </el-icon>

            <span>全部商品</span>
          </div>

          <el-icon>
            <ArrowRight />
          </el-icon>
        </button>

        <div
          v-loading="categoryLoading"
          class="category-tree-wrapper"
        >
          <el-tree
            v-if="categoryTree.length"
            :data="categoryTree"
            node-key="id"
            default-expand-all
            :expand-on-click-node="false"
            :highlight-current="false"
            class="product-category-tree"
            @node-click="handleCategoryNodeClick"
          >
            <template #default="{ data }">
              <div
                class="category-tree-node"
                :class="{
                  active:
                    (data.level === 1 &&
                      query.category_level_1 === data.value &&
                      !query.category_level_2) ||
                    (data.level === 2 &&
                      query.category_level_2 === data.value &&
                      !query.category_level_3) ||
                    (data.level === 3 &&
                      query.category_level_3 === data.value)
                }"
              >
                <span class="category-node-label">
                  {{ data.label }}
                </span>

                <span
                  v-if="data.count"
                  class="category-node-count"
                >
                  {{ data.count }}
                </span>
              </div>
            </template>
          </el-tree>

          <el-empty
            v-else
            :image-size="64"
            description="暂无分类数据"
          />
        </div>
      </aside>

      <section class="product-table-panel">
        <div class="table-panel-header">
          <div class="table-result-summary">
            <h3>商品数据</h3>

            <span>
              共
              <strong>
                {{ total.toLocaleString() }}
              </strong>
              条记录
            </span>
          </div>

          <div class="table-header-actions">
            <el-tooltip
              content="刷新列表"
              placement="top"
            >
              <el-button
                circle
                :loading="loading"
                @click="handleRefresh"
              >
                <el-icon>
                  <Refresh />
                </el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <div class="product-table-container">
          <el-table
            ref="tableRef"
            v-loading="loading"
            :data="productList"
            row-key="id"
            stripe
            class="product-data-table"
            empty-text="没有找到符合条件的商品"
          >
            <el-table-column
              label="商品"
              min-width="310"
              fixed="left"
            >
              <template #default="{ row }">
                <div class="product-main-cell">
                  <div class="product-thumbnail">
                    <el-image
                      v-if="row.cover_url"
                      :src="getFileUrl(row.cover_url)"
                      :preview-src-list="[
                        getFileUrl(row.cover_url)
                      ]"
                      preview-teleported
                      fit="contain"
                    >
                      <template #error>
                        <div class="image-error-placeholder">
                          <el-icon>
                            <Picture />
                          </el-icon>
                        </div>
                      </template>
                    </el-image>

                    <div
                      v-else
                      class="image-empty-placeholder"
                    >
                      <el-icon>
                        <Picture />
                      </el-icon>
                    </div>
                  </div>

                  <div class="product-main-info">
                    <button
                      type="button"
                      class="product-name-button"
                      :title="row.product_name"
                      @click="openProductDetail(row)"
                    >
                      {{ row.product_name }}
                    </button>

                    <div class="product-sub-info">
                      <span>
                        编号：{{ row.goods_no }}
                      </span>

                      <span v-if="row.brand_name !== '-'">
                        品牌：{{ row.brand_name }}
                      </span>
                    </div>
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column
              label="商品分类"
              min-width="230"
            >
              <template #default="{ row }">
                <div class="category-path-cell">
                  <span
                    v-if="row.category_level_1"
                    class="category-level-one"
                  >
                    {{ row.category_level_1 }}
                  </span>

                  <el-icon
                    v-if="row.category_level_2"
                    class="category-separator"
                  >
                    <ArrowRight />
                  </el-icon>

                  <span v-if="row.category_level_2">
                    {{ row.category_level_2 }}
                  </span>

                  <el-icon
                    v-if="row.category_level_3"
                    class="category-separator"
                  >
                    <ArrowRight />
                  </el-icon>

                  <span v-if="row.category_level_3">
                    {{ row.category_level_3 }}
                  </span>

                  <span
                    v-if="
                      !row.category_level_1 &&
                      !row.category_level_2 &&
                      !row.category_level_3
                    "
                  >
                    -
                  </span>
                </div>
              </template>
            </el-table-column>

            <el-table-column
              label="颜色"
              min-width="160"
            >
              <template #default="{ row }">
                <div
                  v-if="row.colors.length"
                  class="color-tag-list"
                >
                  <el-tag
                    v-for="color in row.colors.slice(0, 3)"
                    :key="color"
                    size="small"
                    effect="plain"
                  >
                    {{ color }}
                  </el-tag>

                  <el-tooltip
                    v-if="row.colors.length > 3"
                    :content="row.colors.join('、')"
                    placement="top"
                  >
                    <span class="more-color-count">
                      +{{ row.colors.length - 3 }}
                    </span>
                  </el-tooltip>
                </div>

                <span
                  v-else
                  class="empty-value"
                >
                  -
                </span>
              </template>
            </el-table-column>

            <el-table-column
              label="文件状态"
              width="130"
              align="center"
            >
              <template #default="{ row }">
                <div class="file-status-cell">
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

                  <span
                    v-if="row.file_count"
                    class="file-count-text"
                  >
                    {{ row.file_count }} 个文件
                  </span>
                </div>
              </template>
            </el-table-column>

            <el-table-column
              label="更新时间"
              width="165"
            >
              <template #default="{ row }">
                <span class="table-date-text">
                  {{ formatDate(row.updated_at) }}
                </span>
              </template>
            </el-table-column>

            <el-table-column
              label="操作"
              width="210"
              fixed="right"
              align="center"
            >
              <template #default="{ row }">
                <div class="table-operation-group">
                  <el-button
                    link
                    type="primary"
                    @click="openProductDetail(row)"
                  >
                    详情
                  </el-button>

                  <el-button
                    link
                    type="primary"
                    @click="openProductEditor(row)"
                  >
                    编辑
                  </el-button>

                  <el-button
                    link
                    type="primary"
                    @click="handleFilePlaceholder(row)"
                  >
                    文件
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="product-pagination-bar">
          <div class="pagination-info">
            第
            <strong>{{ query.page }}</strong>
            页，每页显示
            <strong>{{ query.size }}</strong>
            条
          </div>

          <el-pagination
            v-model:current-page="query.page"
            v-model:page-size="query.size"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </section>
    </section>

    <el-drawer
      v-model="detailVisible"
      size="620px"
      destroy-on-close
      class="product-detail-drawer"
      @closed="closeProductDetail"
    >
      <template #header>
        <div class="drawer-title-area">
          <div class="drawer-title-icon">
            <el-icon>
              <Goods />
            </el-icon>
          </div>

          <div>
            <h3>商品详情</h3>

            <span>
              查看商品基础信息和文件状态
            </span>
          </div>
        </div>
      </template>

      <div
        v-loading="detailLoading"
        class="product-detail-content"
      >
        <template v-if="currentProduct">
          <section class="detail-product-summary">
            <div class="detail-product-image">
              <el-image
                v-if="currentProduct.cover_url"
                :src="getFileUrl(
                  currentProduct.cover_url
                )"
                :preview-src-list="[
                  getFileUrl(
                    currentProduct.cover_url
                  )
                ]"
                preview-teleported
                fit="contain"
              >
                <template #error>
                  <div class="detail-image-placeholder">
                    <el-icon :size="30">
                      <Picture />
                    </el-icon>
                  </div>
                </template>
              </el-image>

              <div
                v-else
                class="detail-image-placeholder"
              >
                <el-icon :size="30">
                  <Picture />
                </el-icon>
              </div>
            </div>

            <div class="detail-product-main">
              <el-tag
                v-if="currentProduct.has_files"
                type="success"
                effect="light"
              >
                已上传文件
              </el-tag>

              <el-tag
                v-else
                type="info"
                effect="plain"
              >
                未上传文件
              </el-tag>

              <h2>
                {{ currentProduct.product_name }}
              </h2>

              <p>
                商品编号：
                {{ currentProduct.goods_no }}
              </p>
            </div>
          </section>

          <section class="detail-section">
            <div class="detail-section-title">
              <h4>基础信息</h4>
            </div>

            <div class="detail-info-grid">
              <div class="detail-info-item">
                <span>数据库 ID</span>
                <strong>
                  {{ currentProduct.id || "-" }}
                </strong>
              </div>

              <div class="detail-info-item">
                <span>商品编号</span>
                <strong>
                  {{ currentProduct.goods_no }}
                </strong>
              </div>

              <div class="detail-info-item">
                <span>品牌</span>
                <strong>
                  {{ currentProduct.brand_name }}
                </strong>
              </div>

              <div class="detail-info-item">
                <span>文件数量</span>
                <strong>
                  {{ currentProduct.file_count || 0 }}
                </strong>
              </div>
            </div>
          </section>

          <section class="detail-section">
            <div class="detail-section-title">
              <h4>商品分类</h4>
            </div>

            <div class="detail-category-path">
              <el-tag
                v-if="currentProduct.category_level_1"
                effect="plain"
              >
                {{ currentProduct.category_level_1 }}
              </el-tag>

              <el-icon
                v-if="currentProduct.category_level_2"
              >
                <ArrowRight />
              </el-icon>

              <el-tag
                v-if="currentProduct.category_level_2"
                effect="plain"
              >
                {{ currentProduct.category_level_2 }}
              </el-tag>

              <el-icon
                v-if="currentProduct.category_level_3"
              >
                <ArrowRight />
              </el-icon>

              <el-tag
                v-if="currentProduct.category_level_3"
                effect="plain"
              >
                {{ currentProduct.category_level_3 }}
              </el-tag>

              <span
                v-if="
                  !currentProduct.category_level_1 &&
                  !currentProduct.category_level_2 &&
                  !currentProduct.category_level_3
                "
                class="empty-value"
              >
                暂无分类
              </span>
            </div>
          </section>

          <section class="detail-section">
            <div class="detail-section-title">
              <h4>商品颜色</h4>
            </div>

            <div
              v-if="currentProduct.colors.length"
              class="detail-color-list"
            >
              <el-tag
                v-for="color in currentProduct.colors"
                :key="color"
                effect="plain"
              >
                {{ color }}
              </el-tag>
            </div>

            <span
              v-else
              class="empty-value"
            >
              暂无颜色数据
            </span>
          </section>

          <section class="detail-section">
            <div class="detail-section-title">
              <h4>记录信息</h4>
            </div>

            <div class="detail-info-grid">
              <div class="detail-info-item full-width">
                <span>更新时间</span>
                <strong>
                  {{ formatDate(
                    currentProduct.updated_at
                  ) }}
                </strong>
              </div>
            </div>
          </section>
        </template>
      </div>

      <template #footer>
        <div class="drawer-footer-actions">
          <el-button
            @click="detailVisible = false"
          >
            关闭
          </el-button>

          <el-button
            type="primary"
            @click="openDetailProductEditor"
          >
            <el-icon>
              <Edit />
            </el-icon>

            编辑商品
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>

  <!-- PRODUCT_EDIT_DIALOG_V1 -->
  <el-dialog
    v-model="editDialogVisible"
    title="编辑商品"
    width="720px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @closed="closeEditDialog"
  >
    <div
      v-loading="editLoading"
      class="product-edit-dialog"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-position="top"
        class="product-edit-form"
      >
        <div class="product-edit-grid">
          <el-form-item
            label="商品名称"
            prop="product_name"
            class="product-edit-full"
          >
            <el-input
              v-model="editForm.product_name"
              maxlength="200"
              show-word-limit
              placeholder="请输入商品名称"
            />
          </el-form-item>

          <el-form-item label="商品编号">
            <el-input
              v-model="editForm.goods_no"
              placeholder="请输入商品编号"
            />
          </el-form-item>

          <el-form-item label="品牌">
            <el-input
              v-model="editForm.brand_name"
              placeholder="请输入品牌"
            />
          </el-form-item>

          <el-form-item label="一级分类">
            <el-input
              v-model="editForm.category_level_1"
              placeholder="请输入一级分类"
            />
          </el-form-item>

          <el-form-item label="二级分类">
            <el-input
              v-model="editForm.category_level_2"
              placeholder="请输入二级分类"
            />
          </el-form-item>

          <el-form-item label="三级分类">
            <el-input
              v-model="editForm.category_level_3"
              placeholder="请输入三级分类"
            />
          </el-form-item>

          <el-form-item label="商品状态">
            <el-select
              v-model="editForm.status"
              style="width: 100%"
            >
              <el-option
                label="有效"
                :value="1"
              />
              <el-option
                label="停用"
                :value="0"
              />
            </el-select>
          </el-form-item>

          <el-form-item
            label="商品颜色"
            class="product-edit-full"
          >
            <el-input
              v-model="editForm.colors_text"
              type="textarea"
              :rows="3"
              placeholder="多个颜色使用逗号、顿号或斜杠分隔"
            />
          </el-form-item>
        </div>
      </el-form>
    </div>

    <template #footer>
      <div class="product-edit-footer">
        <el-button
          :disabled="editSaving"
          @click="editDialogVisible = false"
        >
          取消
        </el-button>

        <el-button
          type="primary"
          :loading="editSaving"
          @click="submitProductEdit"
        >
          保存修改
        </el-button>
      </div>
    </template>
  </el-dialog>
  <!-- END_PRODUCT_EDIT_DIALOG_V1 -->

</template>

<style scoped>


/* PRODUCT_EDIT_STYLE_V1 */

.product-edit-dialog {
  min-height: 260px;
}

.product-edit-grid {
  display: grid;
  grid-template-columns:
    minmax(0, 1fr)
    minmax(0, 1fr);
  column-gap: 20px;
  row-gap: 2px;
}

.product-edit-full {
  grid-column: 1 / -1;
}

.product-edit-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 768px) {
  .product-edit-grid {
    grid-template-columns: 1fr;
  }

  .product-edit-full {
    grid-column: auto;
  }
}

/* END_PRODUCT_EDIT_STYLE_V1 */

</style>
