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
