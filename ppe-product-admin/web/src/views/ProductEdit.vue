<script setup>
import {
  computed,
  onMounted,
  reactive,
  ref
} from "vue"

import {
  useRoute,
  useRouter
} from "vue-router"

import {
  ElMessage,
  ElMessageBox
} from "element-plus"

import BasicInfoCard from "../components/product/BasicInfoCard.vue"
import CategoryColorCard from "../components/product/CategoryColorCard.vue"
import SellingPointSpecCard from "../components/product/SellingPointSpecCard.vue"
import ProductFileCard from "../components/product/ProductFileCard.vue"

import {
  getProductDetail,
  updateProduct,
  uploadProductFile
} from "../api/product"

const route = useRoute()
const router = useRouter()

const productId = computed(() =>
  Number(route.params.id)
)

const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  goods_no: "",
  product_name: "",
  barcode: "",
  brand_name: "",
  status: 1,

  category_level_1: "",
  category_level_2: "",
  category_level_3: "",

  colors: [],
  selling_points: [],

  material: "",
  unit_name: "",
  specification: "",
  packaging_specification: "",
  execution_standard: "",

  files: []
})

const rules = {
  product_name: [
    {
      required: true,
      message: "请输入商品名称",
      trigger: "blur"
    }
  ]
}

function unwrapResponse(response) {
  if (
    response?.data &&
    typeof response.data === "object" &&
    !Array.isArray(response.data)
  ) {
    return response.data
  }

  return response || {}
}

function parseArray(value) {
  if (Array.isArray(value)) {
    return value.filter(Boolean)
  }

  if (!value) {
    return []
  }

  if (typeof value === "string") {
    const text = value.trim()

    if (!text) {
      return []
    }

    try {
      const result = JSON.parse(text)

      if (Array.isArray(result)) {
        return result.filter(Boolean)
      }
    } catch {
      return text
        .split(/[,，、/\n]/)
        .map(item => item.trim())
        .filter(Boolean)
    }
  }

  return []
}

function normalizeFiles(data) {
  return [
    data.files,
    data.product_files,
    data.attachments,
    data.file_list
  ].find(Array.isArray) || []
}

function fillForm(rawData) {
  const data = rawData || {}

  form.id =
    data.id ??
    data.product_id ??
    productId.value

  form.goods_no =
    data.goods_no ??
    data.goodsNo ??
    data.product_no ??
    ""

  form.product_name =
    data.product_name ??
    data.goods_name ??
    data.goodsName ??
    data.name ??
    ""

  form.barcode =
    data.barcode ??
    data.sku_barcode ??
    data.product_barcode ??
    ""

  form.brand_name =
    data.brand_name ??
    data.brand ??
    data.brandName ??
    ""

  form.status = Number(data.status ?? 1)

  form.category_level_1 =
    data.category_level_1 ??
    data.level_1 ??
    ""

  form.category_level_2 =
    data.category_level_2 ??
    data.level_2 ??
    ""

  form.category_level_3 =
    data.category_level_3 ??
    data.level_3 ??
    ""

  form.colors = parseArray(
    data.colors ??
    data.color_list ??
    data.product_colors
  )

  form.selling_points = parseArray(
    data.selling_points ??
    data.product_selling_points ??
    data.highlights ??
    data.product_highlights
  )

  form.material =
    data.material ??
    data.product_material ??
    ""

  form.unit_name =
    data.unit_name ??
    data.unit ??
    ""

  form.specification =
    data.specification ??
    data.specifications ??
    data.product_specification ??
    ""

  form.packaging_specification =
    data.packaging_specification ??
    data.package_specification ??
    data.packaging_spec ??
    ""

  form.execution_standard =
    data.execution_standard ??
    data.national_standard ??
    data.standard ??
    ""

  form.files = normalizeFiles(data)
}

async function loadProduct() {
  if (!productId.value) {
    ElMessage.error("商品 ID 不正确")
    return
  }

  loading.value = true

  try {
    const response =
      await getProductDetail(productId.value)

    const container = unwrapResponse(response)

    const product =
      container.product ??
      container.detail ??
      container.data ??
      container

    fillForm(product)
  } catch (error) {
    console.error("加载商品资料失败：", error)
    ElMessage.error("加载商品资料失败")
  } finally {
    loading.value = false
  }
}

function buildPayload() {
  return {
    goods_no: form.goods_no.trim(),

    product_name:
      form.product_name.trim(),

    goods_name:
      form.product_name.trim(),

    barcode:
      form.barcode.trim(),

    brand_name:
      form.brand_name.trim(),

    brand:
      form.brand_name.trim(),

    status: Number(form.status),

    category_level_1:
      form.category_level_1.trim(),

    category_level_2:
      form.category_level_2.trim(),

    category_level_3:
      form.category_level_3.trim(),

    colors: form.colors,
    color_list: form.colors,

    selling_points:
      form.selling_points,

    product_selling_points:
      form.selling_points,

    material:
      form.material.trim(),

    unit_name:
      form.unit_name.trim(),

    specification:
      form.specification.trim(),

    packaging_specification:
      form.packaging_specification.trim(),

    execution_standard:
      form.execution_standard.trim()
  }
}

async function saveProduct() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  saving.value = true

  try {
    await updateProduct(
      productId.value,
      buildPayload()
    )

    ElMessage.success("商品资料保存成功")
    await loadProduct()
  } catch (error) {
    console.error("保存商品资料失败：", error)
  } finally {
    saving.value = false
  }
}

async function returnToList() {
  try {
    await ElMessageBox.confirm(
      "确定返回商品列表吗？尚未保存的修改将丢失。",
      "返回确认",
      {
        confirmButtonText: "返回列表",
        cancelButtonText: "继续编辑",
        type: "warning"
      }
    )

    router.push("/products")
  } catch {
    // 用户取消
  }
}

onMounted(loadProduct)
</script>

<template>
  <div
    v-loading="loading"
    class="product-edit-page"
  >
    <header class="page-header">
      <div>
        <el-button
          text
          class="back-button"
          @click="returnToList"
        >
          ← 返回商品列表
        </el-button>

        <h1>编辑商品</h1>

        <p>
          维护商品资料、卖点、图片和认证文件
        </p>
      </div>

      <div class="header-actions">
        <el-button
          :disabled="saving"
          @click="loadProduct"
        >
          重新加载
        </el-button>

        <el-button
          type="primary"
          :loading="saving"
          @click="saveProduct"
        >
          保存修改
        </el-button>
      </div>
    </header>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
    >
      <BasicInfoCard :form="form" />

      <CategoryColorCard :form="form" />

      <SellingPointSpecCard :form="form" />

      <ProductFileCard
        :product-id="productId"
        :files="form.files"
        :upload-function="uploadProductFile"
        @uploaded="loadProduct"
      />

      <footer class="page-footer">
        <el-button
          size="large"
          @click="returnToList"
        >
          取消并返回
        </el-button>

        <el-button
          type="primary"
          size="large"
          :loading="saving"
          @click="saveProduct"
        >
          保存商品资料
        </el-button>
      </footer>
    </el-form>
  </div>
</template>

<style scoped>
.product-edit-page {
  width: 100%;
  padding: 24px;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}

.page-header h1 {
  margin: 10px 0 6px;
  color: #172033;
  font-size: 28px;
}

.page-header p {
  margin: 0;
  color: #8c99ad;
}

.back-button {
  padding-left: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
  padding-top: 12px;
}

:deep(.edit-card) {
  margin-bottom: 20px;
  padding: 24px;
  border: 1px solid #e5eaf2;
  border-radius: 14px;
  background: #fff;
}

:deep(.section-heading) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  margin-bottom: 20px;
  border-bottom: 1px solid #edf0f5;
}

:deep(.section-heading h2) {
  margin: 0;
  color: #172033;
  font-size: 18px;
}

:deep(.section-heading p) {
  margin: 5px 0 0;
  color: #98a2b3;
  font-size: 13px;
}

:deep(.form-grid) {
  display: grid;
  grid-template-columns:
    repeat(2, minmax(0, 1fr));
  gap: 0 20px;
}

:deep(.form-grid-3) {
  grid-template-columns:
    repeat(3, minmax(0, 1fr));
}

:deep(.span-2) {
  grid-column: 1 / -1;
}

.page-footer {
  position: sticky;
  bottom: 0;
  z-index: 10;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 18px 24px;
  border: 1px solid #e5eaf2;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 -8px 28px rgba(30, 46, 75, 0.08);
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
  }

  :deep(.form-grid),
  :deep(.form-grid-3) {
    grid-template-columns: 1fr;
  }

  :deep(.span-2) {
    grid-column: auto;
  }
}
</style>
