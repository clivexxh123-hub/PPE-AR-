#!/usr/bin/env bash
set -e

ROOT="/root/ppe-product-admin"
WEB="$ROOT/web"
SRC="$WEB/src"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$SRC/components/product"
mkdir -p "$SRC/views"

echo "===== 1. 创建基础资料组件 ====="

cat > "$SRC/components/product/BasicInfoCard.vue" <<'EOF'
<script setup>
defineProps({
  form: {
    type: Object,
    required: true
  }
})
</script>

<template>
  <section class="edit-card">
    <div class="section-heading">
      <div>
        <h2>基础资料</h2>
        <p>维护商品名称、编号、品牌与状态</p>
      </div>

      <el-tag
        v-if="form.id"
        effect="plain"
      >
        ID：{{ form.id }}
      </el-tag>
    </div>

    <div class="form-grid">
      <el-form-item
        label="商品名称"
        prop="product_name"
        class="span-2"
      >
        <el-input
          v-model="form.product_name"
          maxlength="200"
          show-word-limit
          placeholder="请输入商品名称"
        />
      </el-form-item>

      <el-form-item label="商品编号">
        <el-input
          v-model="form.goods_no"
          placeholder="请输入商品编号"
        />
      </el-form-item>

      <el-form-item label="商品条码">
        <el-input
          v-model="form.barcode"
          placeholder="请输入商品条码"
        />
      </el-form-item>

      <el-form-item label="品牌">
        <el-input
          v-model="form.brand_name"
          placeholder="请输入商品品牌"
        />
      </el-form-item>

      <el-form-item label="商品状态">
        <el-select
          v-model="form.status"
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
    </div>
  </section>
</template>
EOF

echo "===== 2. 创建分类与颜色组件 ====="

cat > "$SRC/components/product/CategoryColorCard.vue" <<'EOF'
<script setup>
import { ref } from "vue"
import { ElMessage } from "element-plus"

const props = defineProps({
  form: {
    type: Object,
    required: true
  }
})

const newColor = ref("")

function addColor() {
  const value = newColor.value.trim()

  if (!value) {
    return
  }

  if (props.form.colors.includes(value)) {
    ElMessage.warning("该颜色已经存在")
    return
  }

  props.form.colors.push(value)
  newColor.value = ""
}

function removeColor(index) {
  props.form.colors.splice(index, 1)
}
</script>

<template>
  <section class="edit-card">
    <div class="section-heading">
      <div>
        <h2>分类与颜色</h2>
        <p>维护商品三级分类和可选颜色</p>
      </div>
    </div>

    <div class="form-grid form-grid-3">
      <el-form-item label="一级分类">
        <el-input
          v-model="form.category_level_1"
          placeholder="例如：个人防护"
        />
      </el-form-item>

      <el-form-item label="二级分类">
        <el-input
          v-model="form.category_level_2"
          placeholder="例如：听力防护"
        />
      </el-form-item>

      <el-form-item label="三级分类">
        <el-input
          v-model="form.category_level_3"
          placeholder="例如：耳塞"
        />
      </el-form-item>
    </div>

    <el-divider />

    <div class="color-editor">
      <div class="color-editor-title">
        <strong>商品颜色</strong>
        <span>支持添加多个颜色</span>
      </div>

      <div class="color-input-row">
        <el-input
          v-model="newColor"
          maxlength="30"
          placeholder="输入颜色名称"
          @keyup.enter="addColor"
        />

        <el-button
          type="primary"
          @click="addColor"
        >
          添加颜色
        </el-button>
      </div>

      <div
        v-if="form.colors.length"
        class="color-tags"
      >
        <el-tag
          v-for="(color, index) in form.colors"
          :key="`${color}-${index}`"
          closable
          size="large"
          effect="plain"
          @close="removeColor(index)"
        >
          {{ color }}
        </el-tag>
      </div>

      <el-empty
        v-else
        description="暂无颜色"
        :image-size="54"
      />
    </div>
  </section>
</template>

<style scoped>
.color-editor-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.color-editor-title span {
  color: #98a2b3;
  font-size: 13px;
}

.color-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 110px;
  gap: 12px;
  max-width: 520px;
}

.color-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}
</style>
EOF

echo "===== 3. 创建卖点与规格组件 ====="

cat > "$SRC/components/product/SellingPointSpecCard.vue" <<'EOF'
<script setup>
import { ref } from "vue"
import { ElMessage } from "element-plus"

const props = defineProps({
  form: {
    type: Object,
    required: true
  }
})

const newPoint = ref("")

function addPoint() {
  const value = newPoint.value.trim()

  if (!value) {
    return
  }

  if (props.form.selling_points.includes(value)) {
    ElMessage.warning("该卖点已经存在")
    return
  }

  props.form.selling_points.push(value)
  newPoint.value = ""
}

function removePoint(index) {
  props.form.selling_points.splice(index, 1)
}
</script>

<template>
  <section class="edit-card">
    <div class="section-heading">
      <div>
        <h2>商品卖点</h2>
        <p>每条卖点独立保存，便于营销内容和 AI 调用</p>
      </div>
    </div>

    <div class="point-input-row">
      <el-input
        v-model="newPoint"
        maxlength="300"
        placeholder="输入一条商品卖点"
        @keyup.enter="addPoint"
      />

      <el-button
        type="primary"
        @click="addPoint"
      >
        新增卖点
      </el-button>
    </div>

    <div
      v-if="form.selling_points.length"
      class="point-list"
    >
      <div
        v-for="(point, index) in form.selling_points"
        :key="index"
        class="point-item"
      >
        <span class="point-number">
          {{ index + 1 }}
        </span>

        <el-input
          v-model="form.selling_points[index]"
          maxlength="300"
        />

        <el-button
          type="danger"
          link
          @click="removePoint(index)"
        >
          删除
        </el-button>
      </div>
    </div>

    <el-empty
      v-else
      description="暂无商品卖点"
      :image-size="54"
    />

    <el-divider />

    <div class="section-heading specification-heading">
      <div>
        <h2>商品规格</h2>
        <p>维护产品材质、单位、产品规格与包装信息</p>
      </div>
    </div>

    <div class="form-grid">
      <el-form-item label="商品材质">
        <el-input
          v-model="form.material"
          placeholder="请输入商品材质"
        />
      </el-form-item>

      <el-form-item label="计量单位">
        <el-input
          v-model="form.unit_name"
          placeholder="例如：个、套、盒"
        />
      </el-form-item>

      <el-form-item
        label="产品规格"
        class="span-2"
      >
        <el-input
          v-model="form.specification"
          type="textarea"
          :rows="4"
          placeholder="请输入产品尺寸、重量、性能参数等"
        />
      </el-form-item>

      <el-form-item
        label="包装规格"
        class="span-2"
      >
        <el-input
          v-model="form.packaging_specification"
          type="textarea"
          :rows="4"
          placeholder="请输入包装数量、包装尺寸及包装方式"
        />
      </el-form-item>
    </div>
  </section>
</template>

<style scoped>
.point-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 110px;
  gap: 12px;
}

.point-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.point-item {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 50px;
  align-items: center;
  gap: 10px;
}

.point-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #ecf5ff;
  color: #409eff;
  font-size: 13px;
  font-weight: 700;
}

.specification-heading {
  margin-top: 0;
}
</style>
EOF

echo "===== 4. 创建文件上传组件 ====="

cat > "$SRC/components/product/ProductFileCard.vue" <<'EOF'
<script setup>
import { ref } from "vue"
import { ElMessage } from "element-plus"

const props = defineProps({
  productId: {
    type: [Number, String],
    required: true
  },
  files: {
    type: Array,
    default: () => []
  },
  uploadFunction: {
    type: Function,
    required: true
  }
})

const emit = defineEmits(["uploaded"])

const uploadingType = ref("")

const imageTypes = [
  {
    label: "商品主图",
    value: "cover_image",
    accept: "image/jpeg,image/png,image/webp"
  },
  {
    label: "白底图",
    value: "white_image",
    accept: "image/jpeg,image/png,image/webp"
  },
  {
    label: "场景图",
    value: "scene_image",
    accept: "image/jpeg,image/png,image/webp"
  },
  {
    label: "详情图",
    value: "detail_image",
    accept: "image/jpeg,image/png,image/webp"
  }
]

const documentTypes = [
  {
    label: "认证证书",
    value: "certificate_pdf"
  },
  {
    label: "检测报告",
    value: "test_report_pdf"
  },
  {
    label: "产品说明书",
    value: "manual_pdf"
  }
]

async function uploadSelected(uploadFile, type, pdfOnly = false) {
  const raw = uploadFile?.raw || uploadFile

  if (!raw) {
    return
  }

  if (pdfOnly && raw.type !== "application/pdf") {
    ElMessage.warning("该栏目仅支持 PDF 文件")
    return
  }

  const formData = new FormData()
  formData.append("file", raw)
  formData.append("file_type", type)
  formData.append("type", type)

  uploadingType.value = type

  try {
    await props.uploadFunction(
      props.productId,
      formData
    )

    ElMessage.success("文件上传成功")
    emit("uploaded")
  } catch (error) {
    console.error("文件上传失败：", error)
  } finally {
    uploadingType.value = ""
  }
}

function fileTypeLabel(type) {
  const types = [
    ...imageTypes,
    ...documentTypes
  ]

  return (
    types.find(item => item.value === type)?.label ||
    type ||
    "其他文件"
  )
}

function fileUrl(file) {
  const value =
    file.file_url ||
    file.url ||
    file.path ||
    ""

  if (!value) {
    return ""
  }

  if (
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("/")
  ) {
    return value
  }

  return `/${value}`
}
</script>

<template>
  <section class="edit-card">
    <div class="section-heading">
      <div>
        <h2>商品图片</h2>
        <p>上传主图、白底图、场景图和详情图</p>
      </div>
    </div>

    <div class="upload-grid">
      <article
        v-for="item in imageTypes"
        :key="item.value"
        class="upload-item"
      >
        <div class="upload-item-header">
          <strong>{{ item.label }}</strong>
          <span>JPG / PNG / WEBP</span>
        </div>

        <el-upload
          drag
          action="#"
          :accept="item.accept"
          :show-file-list="false"
          :auto-upload="false"
          :disabled="Boolean(uploadingType)"
          :on-change="
            file => uploadSelected(
              file,
              item.value,
              false
            )
          "
        >
          <div class="upload-icon">＋</div>

          <div v-if="uploadingType === item.value">
            正在上传……
          </div>

          <div v-else>
            点击或拖拽上传
          </div>
        </el-upload>
      </article>
    </div>
  </section>

  <section class="edit-card">
    <div class="section-heading">
      <div>
        <h2>认证证书与 PDF</h2>
        <p>上传认证证书、检测报告和产品说明书</p>
      </div>
    </div>

    <div class="upload-grid document-grid">
      <article
        v-for="item in documentTypes"
        :key="item.value"
        class="upload-item"
      >
        <div class="upload-item-header">
          <strong>{{ item.label }}</strong>
          <span>仅支持 PDF</span>
        </div>

        <el-upload
          drag
          action="#"
          accept="application/pdf,.pdf"
          :show-file-list="false"
          :auto-upload="false"
          :disabled="Boolean(uploadingType)"
          :on-change="
            file => uploadSelected(
              file,
              item.value,
              true
            )
          "
        >
          <div class="upload-icon pdf-icon">
            PDF
          </div>

          <div v-if="uploadingType === item.value">
            正在上传……
          </div>

          <div v-else>
            点击或拖拽上传
          </div>
        </el-upload>
      </article>
    </div>
  </section>

  <section class="edit-card">
    <div class="section-heading">
      <div>
        <h2>已上传文件</h2>
        <p>当前商品共 {{ files.length }} 个文件</p>
      </div>
    </div>

    <el-empty
      v-if="!files.length"
      description="当前商品暂无文件"
      :image-size="64"
    />

    <el-table
      v-else
      :data="files"
      stripe
    >
      <el-table-column
        label="文件类型"
        width="180"
      >
        <template #default="{ row }">
          {{ fileTypeLabel(row.file_type || row.type) }}
        </template>
      </el-table-column>

      <el-table-column
        label="文件名称"
        min-width="260"
      >
        <template #default="{ row }">
          {{ row.file_name || row.name || "-" }}
        </template>
      </el-table-column>

      <el-table-column
        label="上传时间"
        width="190"
      >
        <template #default="{ row }">
          {{ row.created_at || row.uploaded_at || "-" }}
        </template>
      </el-table-column>

      <el-table-column
        label="操作"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          <el-link
            v-if="fileUrl(row)"
            :href="fileUrl(row)"
            target="_blank"
            type="primary"
          >
            查看文件
          </el-link>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<style scoped>
.upload-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.document-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.upload-item {
  padding: 16px;
  border: 1px solid #e5eaf2;
  border-radius: 12px;
  background: #fafbfd;
}

.upload-item-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.upload-item-header span {
  color: #98a2b3;
  font-size: 12px;
}

.upload-item :deep(.el-upload),
.upload-item :deep(.el-upload-dragger) {
  width: 100%;
}

.upload-item :deep(.el-upload-dragger) {
  min-height: 136px;
  padding: 24px 16px;
  box-sizing: border-box;
}

.upload-icon {
  margin-bottom: 8px;
  color: #409eff;
  font-size: 28px;
  font-weight: 700;
}

.pdf-icon {
  font-size: 20px;
}

@media (max-width: 900px) {
  .upload-grid,
  .document-grid {
    grid-template-columns: 1fr;
  }
}
</style>
EOF

echo "===== 5. 创建 ProductEdit.vue ====="

cat > "$SRC/views/ProductEdit.vue" <<'EOF'
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

import BasicInfoCard from "@/components/product/BasicInfoCard.vue"
import CategoryColorCard from "@/components/product/CategoryColorCard.vue"
import SellingPointSpecCard from "@/components/product/SellingPointSpecCard.vue"
import ProductFileCard from "@/components/product/ProductFileCard.vue"

import {
  getProductDetail,
  updateProduct,
  uploadProductFile
} from "@/api/product"

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
      form.packaging_specification.trim()
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
EOF

echo "===== 6. 补充商品 API ====="

API_FILE="$SRC/api/product.js"

if ! grep -q "function uploadProductFile" "$API_FILE"; then
cat >> "$API_FILE" <<'EOF'

/**
 * 上传商品文件
 * POST /api/products/:id/files
 */
export function uploadProductFile(id, formData) {
  return request({
    url: `/products/${id}/files`,
    method: "post",
    data: formData,
    headers: {
      "Content-Type": "multipart/form-data"
    }
  })
}
EOF
fi

echo "===== 7. 修改路由和编辑入口 ====="

ROUTER="$SRC/router/index.js"
PRODUCT_LIST="$SRC/views/ProductList.vue"

cp "$ROUTER" "$ROUTER.backup_$STAMP"
cp "$PRODUCT_LIST" "$PRODUCT_LIST.backup_$STAMP"

python3 <<'PY'
from pathlib import Path
import re

src = Path("/root/ppe-product-admin/web/src")
router_file = src / "router/index.js"
product_file = src / "views/ProductList.vue"

router = router_file.read_text(encoding="utf-8")

if "ProductEdit.vue" not in router:
    imports = list(
        re.finditer(
            r'^import\s+.*?$',
            router,
            flags=re.M
        )
    )

    line = '\nimport ProductEdit from "@/views/ProductEdit.vue"\n'

    if imports:
        pos = imports[-1].end()
        router = router[:pos] + line + router[pos:]
    else:
        router = line + router

if 'name: "ProductEdit"' not in router and "name: 'ProductEdit'" not in router:
    product_route = re.search(
        r'\{\s*'
        r'path\s*:\s*["\']products["\']'
        r'.*?'
        r'\}\s*,?',
        router,
        flags=re.S
    )

    new_route = '''
      {
        path: "products/:id/edit",
        name: "ProductEdit",
        component: ProductEdit,
        meta: {
          title: "编辑商品",
          icon: "Edit"
        }
      },
'''

    if product_route:
        pos = product_route.end()
        router = router[:pos] + "\n" + new_route + router[pos:]
    else:
        children = re.search(
            r'children\s*:\s*\[',
            router
        )

        if not children:
            raise SystemExit("无法找到 router children")

        pos = children.end()
        router = router[:pos] + "\n" + new_route + router[pos:]

router_file.write_text(router, encoding="utf-8")

product = product_file.read_text(encoding="utf-8")

# 确保已经导入 useRouter
vue_router_import = re.search(
    r'import\s*\{([^}]*)\}\s*from\s*["\']vue-router["\']',
    product,
    flags=re.S
)

if vue_router_import:
    names = vue_router_import.group(1)

    if "useRouter" not in names:
        replacement = (
            "import {"
            + names.rstrip().rstrip(",")
            + ", useRouter"
            + '} from "vue-router"'
        )

        product = (
            product[:vue_router_import.start()]
            + replacement
            + product[vue_router_import.end():]
        )
else:
    script = re.search(
        r'<script\s+setup[^>]*>',
        product
    )

    if not script:
        raise SystemExit("未找到 ProductList script setup")

    product = (
        product[:script.end()]
        + '\nimport { useRouter } from "vue-router"\n'
        + product[script.end():]
    )

if "const productEditRouter = useRouter()" not in product:
    script = re.search(
        r'<script\s+setup[^>]*>',
        product
    )

    pos = script.end()

    product = (
        product[:pos]
        + "\nconst productEditRouter = useRouter()\n"
        + product[pos:]
    )

navigation = '''
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
'''

if "function openProductEditor" not in product:
    old_function = re.search(
        r'async\s+function\s+handleEdit\s*\([^)]*\)\s*\{.*?'
        r'\n\}',
        product,
        flags=re.S
    )

    if old_function:
        product = (
            product[:old_function.start()]
            + navigation
            + product[old_function.end():]
        )
    else:
        script_end = product.find("</script>")

        product = (
            product[:script_end]
            + "\n"
            + navigation
            + "\n"
            + product[script_end:]
        )

product = product.replace(
    '@click="handleEdit(row)"',
    '@click="openProductEditor(row)"'
)

product = product.replace(
    '@click="handleEdit(detailProduct)"',
    '@click="openProductEditor(detailProduct)"'
)

product = product.replace(
    '@click="handleEditPlaceholder(row)"',
    '@click="openProductEditor(row)"'
)

product = product.replace(
    '@click="handleEditPlaceholder"',
    '@click="openProductEditor(detailProduct)"'
)

product_file.write_text(product, encoding="utf-8")
PY

echo
echo "===== 安装完成 ====="
echo "下一步执行："
echo "cd $WEB && npm run build"
