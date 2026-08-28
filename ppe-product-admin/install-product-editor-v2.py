from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

ROOT = Path("/root/ppe-product-admin")
WEB = ROOT / "web"
SRC = WEB / "src"

PRODUCT_LIST = SRC / "views/ProductList.vue"
ROUTER_CANDIDATES = [
    SRC / "router/index.js",
    SRC / "router/index.ts",
    SRC / "router.js",
    SRC / "router.ts",
]

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path):
    if not path.exists():
        return

    target = path.with_name(
        f"{path.name}.backup_{timestamp}"
    )

    shutil.copy2(path, target)
    print(f"备份：{target}")


def find_router():
    for path in ROUTER_CANDIDATES:
        if path.exists():
            return path

    for path in SRC.rglob("*"):
        if (
            path.is_file()
            and path.suffix in {".js", ".ts"}
        ):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue

            if (
                "createRouter" in text
                and "ProductList" in text
            ):
                return path

    return None


def find_api():
    candidates = []

    for path in SRC.rglob("*"):
        if (
            not path.is_file()
            or path.suffix not in {".js", ".ts"}
        ):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        if (
            "/products" in text
            and "getProduct" in text
        ):
            candidates.append(path)

    if not candidates:
        return None

    candidates.sort(
        key=lambda p: (
            0 if "api" in str(p).lower() else 1,
            len(str(p))
        )
    )

    return candidates[0]


if not PRODUCT_LIST.exists():
    raise SystemExit(
        f"未找到商品列表文件：{PRODUCT_LIST}"
    )

router_file = find_router()
api_file = find_api()

if router_file is None:
    raise SystemExit("未找到 Vue Router 配置文件")

if api_file is None:
    raise SystemExit("未找到商品 API 文件")

print("商品列表：", PRODUCT_LIST)
print("路由文件：", router_file)
print("API 文件：", api_file)

backup(PRODUCT_LIST)
backup(router_file)
backup(api_file)

# ============================================================
# 1. 完善 API
# ============================================================

api_text = api_file.read_text(encoding="utf-8")

api_append = []

if not re.search(
    r'export\s+function\s+updateProduct\b',
    api_text
):
    api_append.append(r'''
export function updateProduct(id, data) {
  return request({
    url: `/products/${id}`,
    method: "put",
    data
  });
}
''')

if not re.search(
    r'export\s+function\s+uploadProductFile\b',
    api_text
):
    api_append.append(r'''
export function uploadProductFile(id, formData) {
  return request({
    url: `/products/${id}/files`,
    method: "post",
    data: formData,
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
}
''')

if api_append:
    api_text = (
        api_text.rstrip()
        + "\n\n"
        + "\n".join(api_append)
        + "\n"
    )

    api_file.write_text(
        api_text,
        encoding="utf-8"
    )

    print("已补充商品更新和上传 API")
else:
    print("API 已存在，无需重复添加")

# ============================================================
# 2. 创建商品编辑页面
# ============================================================

relative_api = api_file.relative_to(SRC)
api_import_path = (
    "@/"
    + str(relative_api.with_suffix(""))
    .replace("\\", "/")
)

EDIT_VIEW = SRC / "views/ProductEdit.vue"

backup(EDIT_VIEW)

edit_view_code = f'''<script setup>
import {{
  computed,
  onMounted,
  reactive,
  ref
}} from "vue";

import {{
  useRoute,
  useRouter
}} from "vue-router";

import {{
  ElMessage,
  ElMessageBox
}} from "element-plus";

import {{
  getProductDetail,
  updateProduct,
  uploadProductFile
}} from "{api_import_path}";

const route = useRoute();
const router = useRouter();

const productId = computed(() =>
  Number(route.params.id)
);

const loading = ref(false);
const saving = ref(false);
const formRef = ref(null);

const imageUploading = ref(false);
const pdfUploading = ref(false);

const form = reactive({{
  id: null,
  goods_no: "",
  product_name: "",
  brand_name: "",
  category_level_1: "",
  category_level_2: "",
  category_level_3: "",
  colors_text: "",
  status: 1,

  selling_points: "",
  material: "",
  specification: "",
  packaging_specification: "",
  unit_name: "",
  barcode: "",

  files: []
}});

const rules = {{
  product_name: [
    {{
      required: true,
      message: "请输入商品名称",
      trigger: "blur"
    }}
  ]
}};

const imageTypes = [
  {{
    label: "商品主图",
    value: "cover_image"
  }},
  {{
    label: "白底图",
    value: "white_image"
  }},
  {{
    label: "场景图",
    value: "scene_image"
  }},
  {{
    label: "商品详情图",
    value: "detail_image"
  }}
];

const documentTypes = [
  {{
    label: "认证证书",
    value: "certificate_pdf"
  }},
  {{
    label: "产品说明书",
    value: "manual_pdf"
  }},
  {{
    label: "检测报告",
    value: "test_report_pdf"
  }}
];

function unwrapResponse(response) {{
  if (
    response?.data &&
    typeof response.data === "object" &&
    !Array.isArray(response.data)
  ) {{
    return response.data;
  }}

  return response || {{}};
}}

function normalizeFiles(data) {{
  const candidates = [
    data?.files,
    data?.product_files,
    data?.attachments,
    data?.file_list
  ];

  const files = candidates.find(
    item => Array.isArray(item)
  );

  return files || [];
}}

function normalizeColors(value) {{
  if (Array.isArray(value)) {{
    return value.join("、");
  }}

  if (!value) {{
    return "";
  }}

  if (typeof value === "string") {{
    try {{
      const parsed = JSON.parse(value);

      if (Array.isArray(parsed)) {{
        return parsed.join("、");
      }}
    }} catch {{
      return value;
    }}
  }}

  return String(value);
}}

function fillForm(raw) {{
  const data = raw || {{}};

  form.id =
    data.id ??
    data.product_id ??
    productId.value;

  form.goods_no =
    data.goods_no ??
    data.goodsNo ??
    data.product_no ??
    data.product_code ??
    "";

  form.product_name =
    data.product_name ??
    data.goods_name ??
    data.goodsName ??
    data.name ??
    "";

  form.brand_name =
    data.brand_name ??
    data.brand ??
    data.brandName ??
    "";

  form.category_level_1 =
    data.category_level_1 ??
    data.level_1 ??
    data.category1 ??
    "";

  form.category_level_2 =
    data.category_level_2 ??
    data.level_2 ??
    data.category2 ??
    "";

  form.category_level_3 =
    data.category_level_3 ??
    data.level_3 ??
    data.category3 ??
    "";

  form.colors_text = normalizeColors(
    data.colors ??
    data.color_list ??
    data.product_colors
  );

  form.status = Number(
    data.status ?? 1
  );

  form.selling_points =
    data.selling_points ??
    data.product_selling_points ??
    data.highlights ??
    data.product_highlights ??
    "";

  form.material =
    data.material ??
    data.product_material ??
    "";

  form.specification =
    data.specification ??
    data.specifications ??
    data.product_specification ??
    "";

  form.packaging_specification =
    data.packaging_specification ??
    data.package_specification ??
    data.packaging_spec ??
    "";

  form.unit_name =
    data.unit_name ??
    data.unit ??
    "";

  form.barcode =
    data.barcode ??
    data.sku_barcode ??
    data.product_barcode ??
    "";

  form.files = normalizeFiles(data);
}}

async function loadProduct() {{
  if (!productId.value) {{
    ElMessage.error("商品 ID 不正确");
    return;
  }}

  loading.value = true;

  try {{
    const response =
      await getProductDetail(productId.value);

    const container =
      unwrapResponse(response);

    const product =
      container.product ??
      container.detail ??
      container.data ??
      container;

    fillForm(product);
  }} catch (error) {{
    console.error(
      "加载商品详情失败：",
      error
    );

    ElMessage.error("加载商品资料失败");
  }} finally {{
    loading.value = false;
  }}
}}

function buildColors() {{
  return form.colors_text
    .split(/[,，、/\\\\\\n]/)
    .map(item => item.trim())
    .filter(Boolean);
}}

function buildPayload() {{
  const colors = buildColors();

  return {{
    goods_no: form.goods_no.trim(),

    product_name:
      form.product_name.trim(),

    goods_name:
      form.product_name.trim(),

    brand_name:
      form.brand_name.trim(),

    brand:
      form.brand_name.trim(),

    category_level_1:
      form.category_level_1.trim(),

    category_level_2:
      form.category_level_2.trim(),

    category_level_3:
      form.category_level_3.trim(),

    colors,
    color_list: colors,

    status: Number(form.status),

    selling_points:
      form.selling_points.trim(),

    product_selling_points:
      form.selling_points.trim(),

    material:
      form.material.trim(),

    specification:
      form.specification.trim(),

    packaging_specification:
      form.packaging_specification.trim(),

    unit_name:
      form.unit_name.trim(),

    barcode:
      form.barcode.trim()
  }};
}}

async function saveProduct() {{
  try {{
    await formRef.value?.validate();
  }} catch {{
    return;
  }}

  saving.value = true;

  try {{
    await updateProduct(
      productId.value,
      buildPayload()
    );

    ElMessage.success("商品资料保存成功");

    await loadProduct();
  }} catch (error) {{
    console.error(
      "保存商品失败：",
      error
    );
  }} finally {{
    saving.value = false;
  }}
}}

async function uploadFile(
  uploadFile,
  fileType
) {{
  const rawFile =
    uploadFile?.raw ??
    uploadFile;

  if (!rawFile) {{
    ElMessage.warning("请选择文件");
    return;
  }}

  const formData = new FormData();

  formData.append("file", rawFile);
  formData.append("file_type", fileType);
  formData.append("type", fileType);

  await uploadProductFile(
    productId.value,
    formData
  );
}}

async function handleImageUpload(
  uploadFile,
  fileType
) {{
  imageUploading.value = true;

  try {{
    await uploadFile(
      uploadFile,
      fileType
    );

    ElMessage.success("图片上传成功");

    await loadProduct();
  }} catch (error) {{
    console.error(
      "图片上传失败：",
      error
    );
  }} finally {{
    imageUploading.value = false;
  }}
}}

async function handlePdfUpload(
  uploadFile,
  fileType
) {{
  const rawFile =
    uploadFile?.raw ??
    uploadFile;

  if (
    rawFile &&
    rawFile.type !== "application/pdf"
  ) {{
    ElMessage.warning(
      "认证证书和说明书仅支持 PDF"
    );
    return;
  }}

  pdfUploading.value = true;

  try {{
    await uploadFile(
      uploadFile,
      fileType
    );

    ElMessage.success("PDF 上传成功");

    await loadProduct();
  }} catch (error) {{
    console.error(
      "PDF 上传失败：",
      error
    );
  }} finally {{
    pdfUploading.value = false;
  }}
}}

function resolveFileUrl(file) {{
  const value =
    file.file_url ??
    file.url ??
    file.path ??
    "";

  if (!value) {{
    return "";
  }}

  if (
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("/")
  ) {{
    return value;
  }}

  return "/" + value;
}}

function fileTypeLabel(type) {{
  const allTypes = [
    ...imageTypes,
    ...documentTypes
  ];

  return (
    allTypes.find(
      item => item.value === type
    )?.label ||
    type ||
    "其他文件"
  );
}}

async function leavePage() {{
  try {{
    await ElMessageBox.confirm(
      "确定返回商品列表吗？未保存的修改将丢失。",
      "返回确认",
      {{
        confirmButtonText: "返回列表",
        cancelButtonText: "继续编辑",
        type: "warning"
      }}
    );

    router.push("/products");
  }} catch {{
    // 用户取消
  }}
}}

onMounted(() => {{
  loadProduct();
}});
</script>

<template>
  <div
    v-loading="loading"
    class="product-edit-page"
  >
    <header class="edit-page-header">
      <div>
        <el-button
          text
          class="back-button"
          @click="leavePage"
        >
          ← 返回商品列表
        </el-button>

        <h1>编辑商品</h1>

        <p>
          编辑商品基础资料、商品卖点、图片和认证文件
        </p>
      </div>

      <div class="header-actions">
        <el-button
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
      <section class="edit-card">
        <div class="section-heading">
          <h2>基础资料</h2>
          <span>
            商品 ID：{{ form.id || productId }}
          </span>
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
              placeholder="请输入品牌"
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

      <section class="edit-card">
        <div class="section-heading">
          <h2>商品分类</h2>
          <span>维护商品三级分类结构</span>
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
      </section>

      <section class="edit-card">
        <div class="section-heading">
          <h2>商品卖点</h2>
          <span>
            每行填写一个卖点，便于后续生成营销内容
          </span>
        </div>

        <el-form-item label="商品卖点">
          <el-input
            v-model="form.selling_points"
            type="textarea"
            :rows="8"
            maxlength="3000"
            show-word-limit
            placeholder="示例：&#10;高效降噪，适用于工业环境&#10;柔软材质，长时间佩戴舒适&#10;独立包装，方便携带"
          />
        </el-form-item>
      </section>

      <section class="edit-card">
        <div class="section-heading">
          <h2>商品规格</h2>
          <span>维护商品材质、包装和规格参数</span>
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
              placeholder="请输入尺寸、重量、性能参数等"
            />
          </el-form-item>

          <el-form-item
            label="包装规格"
            class="span-2"
          >
            <el-input
              v-model="form.packaging_specification"
              type="textarea"
              :rows="3"
              placeholder="请输入包装数量、包装尺寸等"
            />
          </el-form-item>
        </div>
      </section>

      <section class="edit-card">
        <div class="section-heading">
          <h2>商品颜色</h2>
          <span>
            多个颜色可使用逗号、顿号、斜杠或换行分隔
          </span>
        </div>

        <el-form-item label="颜色列表">
          <el-input
            v-model="form.colors_text"
            type="textarea"
            :rows="4"
            placeholder="黑色、白色、蓝色"
          />
        </el-form-item>
      </section>

      <section class="edit-card">
        <div class="section-heading">
          <h2>商品图片</h2>
          <span>
            支持 JPG、PNG、WEBP，上传后自动绑定到当前商品
          </span>
        </div>

        <div class="upload-grid">
          <article
            v-for="item in imageTypes"
            :key="item.value"
            class="upload-panel"
          >
            <div>
              <strong>{{ item.label }}</strong>
              <p>
                点击或拖拽图片到此区域
              </p>
            </div>

            <el-upload
              drag
              action="#"
              accept="image/jpeg,image/png,image/webp"
              :show-file-list="false"
              :auto-upload="false"
              :disabled="imageUploading"
              :on-change="
                file =>
                  handleImageUpload(
                    file,
                    item.value
                  )
              "
            >
              <div class="upload-symbol">＋</div>
              <div>选择{{ item.label }}</div>
            </el-upload>
          </article>
        </div>
      </section>

      <section class="edit-card">
        <div class="section-heading">
          <h2>认证与资料文件</h2>
          <span>
            支持认证证书、检测报告及产品说明书 PDF
          </span>
        </div>

        <div class="upload-grid document-grid">
          <article
            v-for="item in documentTypes"
            :key="item.value"
            class="upload-panel"
          >
            <div>
              <strong>{{ item.label }}</strong>
              <p>仅支持 PDF 文件</p>
            </div>

            <el-upload
              drag
              action="#"
              accept="application/pdf,.pdf"
              :show-file-list="false"
              :auto-upload="false"
              :disabled="pdfUploading"
              :on-change="
                file =>
                  handlePdfUpload(
                    file,
                    item.value
                  )
              "
            >
              <div class="upload-symbol">
                PDF
              </div>
              <div>选择{{ item.label }}</div>
            </el-upload>
          </article>
        </div>
      </section>

      <section class="edit-card">
        <div class="section-heading">
          <h2>已上传文件</h2>
          <span>
            当前共 {{ form.files.length }} 个文件
          </span>
        </div>

        <el-empty
          v-if="!form.files.length"
          description="当前商品暂无已上传文件"
          :image-size="70"
        />

        <el-table
          v-else
          :data="form.files"
          stripe
        >
          <el-table-column
            label="文件类型"
            width="180"
          >
            <template #default="{ row }">
              {{
                fileTypeLabel(
                  row.file_type ?? row.type
                )
              }}
            </template>
          </el-table-column>

          <el-table-column
            prop="file_name"
            label="文件名称"
            min-width="260"
          />

          <el-table-column
            label="操作"
            width="120"
            align="center"
          >
            <template #default="{ row }">
              <el-link
                v-if="resolveFileUrl(row)"
                :href="resolveFileUrl(row)"
                target="_blank"
                type="primary"
              >
                查看文件
              </el-link>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <footer class="edit-page-footer">
        <el-button
          size="large"
          @click="leavePage"
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
.product-edit-page {{
  width: 100%;
  padding: 24px;
  box-sizing: border-box;
}}

.edit-page-header {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}}

.edit-page-header h1 {{
  margin: 10px 0 6px;
  font-size: 28px;
  color: #172033;
}}

.edit-page-header p {{
  margin: 0;
  color: #8c99ad;
}}

.back-button {{
  padding-left: 0;
}}

.header-actions {{
  display: flex;
  gap: 12px;
  padding-top: 12px;
}}

.edit-card {{
  margin-bottom: 20px;
  padding: 24px;
  border: 1px solid #e6ebf3;
  border-radius: 14px;
  background: #ffffff;
}}

.section-heading {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  margin-bottom: 20px;
  border-bottom: 1px solid #edf0f5;
}}

.section-heading h2 {{
  margin: 0;
  font-size: 18px;
  color: #172033;
}}

.section-heading span {{
  font-size: 13px;
  color: #98a3b5;
}}

.form-grid {{
  display: grid;
  grid-template-columns:
    repeat(2, minmax(0, 1fr));
  gap: 0 20px;
}}

.form-grid-3 {{
  grid-template-columns:
    repeat(3, minmax(0, 1fr));
}}

.span-2 {{
  grid-column: 1 / -1;
}}

.upload-grid {{
  display: grid;
  grid-template-columns:
    repeat(2, minmax(0, 1fr));
  gap: 18px;
}}

.document-grid {{
  grid-template-columns:
    repeat(3, minmax(0, 1fr));
}}

.upload-panel {{
  padding: 18px;
  border: 1px solid #e7ebf2;
  border-radius: 12px;
  background: #fafbfd;
}}

.upload-panel strong {{
  color: #25324a;
}}

.upload-panel p {{
  margin: 5px 0 14px;
  color: #99a4b5;
  font-size: 13px;
}}

.upload-panel :deep(.el-upload) {{
  width: 100%;
}}

.upload-panel :deep(.el-upload-dragger) {{
  width: 100%;
  min-height: 138px;
  padding: 24px;
  box-sizing: border-box;
}}

.upload-symbol {{
  margin-bottom: 8px;
  font-size: 26px;
  font-weight: 700;
  color: #409eff;
}}

.edit-page-footer {{
  position: sticky;
  bottom: 0;
  z-index: 5;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 18px 24px;
  border: 1px solid #e6ebf3;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 -8px 28px rgba(30, 46, 75, 0.06);
}}

@media (max-width: 900px) {{
  .edit-page-header {{
    flex-direction: column;
  }}

  .form-grid,
  .form-grid-3,
  .upload-grid,
  .document-grid {{
    grid-template-columns: 1fr;
  }}

  .span-2 {{
    grid-column: auto;
  }}
}}
</style>
'''

EDIT_VIEW.write_text(
    edit_view_code,
    encoding="utf-8"
)

print("已创建：", EDIT_VIEW)

# ============================================================
# 3. 修改 Router
# ============================================================

router_text = router_file.read_text(
    encoding="utf-8"
)

if "ProductEdit" not in router_text:
    last_import = list(
        re.finditer(
            r'^import\s+.*?$',
            router_text,
            flags=re.M
        )
    )

    import_line = (
        '\nimport ProductEdit '
        'from "@/views/ProductEdit.vue";\n'
    )

    if last_import:
        position = last_import[-1].end()

        router_text = (
            router_text[:position]
            + import_line
            + router_text[position:]
        )
    else:
        router_text = (
            import_line
            + router_text
        )

route_block = '''
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

if 'name: "ProductEdit"' not in router_text:
    product_route = re.search(
        r'\{\s*'
        r'path:\s*["\']products["\'].*?'
        r'\}\s*,?',
        router_text,
        flags=re.S
    )

    if product_route:
        position = product_route.end()

        router_text = (
            router_text[:position]
            + "\n"
            + route_block
            + router_text[position:]
        )
    else:
        children_match = re.search(
            r'children\s*:\s*\[',
            router_text
        )

        if not children_match:
            raise SystemExit(
                "无法在 Router 中找到 children 路由"
            )

        position = children_match.end()

        router_text = (
            router_text[:position]
            + "\n"
            + route_block
            + router_text[position:]
        )

router_file.write_text(
    router_text,
    encoding="utf-8"
)

print("已添加商品编辑路由")

# ============================================================
# 4. 修改 ProductList.vue
# ============================================================

product_text = PRODUCT_LIST.read_text(
    encoding="utf-8"
)

# 找到 useRouter 变量名
router_variable = None

match = re.search(
    r'const\s+([A-Za-z_$][\\w$]*)'
    r'\s*=\s*useRouter\s*\(\s*\)',
    product_text
)

if match:
    router_variable = match.group(1)
else:
    # script setup 中补充 useRouter
    script_match = re.search(
        r'<script\s+setup[^>]*>',
        product_text
    )

    if not script_match:
        raise SystemExit(
            "ProductList.vue 不是 script setup 结构"
        )

    existing_import = re.search(
        r'import\s*\{([^}]*)\}'
        r'\s*from\s*["\']vue-router["\']',
        product_text,
        flags=re.S
    )

    if existing_import:
        names = existing_import.group(1)

        if "useRouter" not in names:
            replacement = (
                "import {"
                + names.rstrip().rstrip(",")
                + ", useRouter"
                + '} from "vue-router"'
            )

            product_text = (
                product_text[:existing_import.start()]
                + replacement
                + product_text[existing_import.end():]
            )
    else:
        position = script_match.end()

        product_text = (
            product_text[:position]
            + '\nimport { useRouter } '
              'from "vue-router";\n'
            + product_text[position:]
        )

    router_variable = "productEditorRouter"

    declaration_position = re.search(
        r'<script\s+setup[^>]*>',
        product_text
    ).end()

    product_text = (
        product_text[:declaration_position]
        + f'''
const {router_variable} = useRouter();
'''
        + product_text[declaration_position:]
    )

navigation_function = f'''
function openProductEditor(row) {{
  const id =
    row?.id ??
    row?.product_id ??
    detailProduct?.value?.id ??
    detailProduct?.value?.product_id;

  if (!id) {{
    ElMessage.warning("未找到商品 ID");
    return;
  }}

  {router_variable}.push(
    `/products/${{id}}/edit`
  );
}}
'''

# 替换 Phase 3 占位函数
placeholder = re.compile(
    r'function\s+handleEditPlaceholder'
    r'\s*\([^)]*\)\s*\{{.*?\n\s*\}}',
    flags=re.S
)

if placeholder.search(product_text):
    product_text = placeholder.sub(
        navigation_function,
        product_text,
        count=1
    )
elif "function openProductEditor" not in product_text:
    mounted = re.search(
        r'\bonMounted\s*\(',
        product_text
    )

    if mounted:
        product_text = (
            product_text[:mounted.start()]
            + navigation_function
            + "\n"
            + product_text[mounted.start():]
        )
    else:
        script_end = product_text.find(
            "</script>"
        )

        product_text = (
            product_text[:script_end]
            + navigation_function
            + "\n"
            + product_text[script_end:]
        )

# 将所有旧事件指向编辑页
product_text = product_text.replace(
    "handleEditPlaceholder(row)",
    "openProductEditor(row)"
)

product_text = product_text.replace(
    "handleEdit(row)",
    "openProductEditor(row)"
)

product_text = re.sub(
    r'@click\s*=\s*["\']'
    r'handleEditPlaceholder'
    r'["\']',
    '@click="openProductEditor(detailProduct)"',
    product_text
)

product_text = re.sub(
    r'@click\s*=\s*["\']'
    r'handleEdit'
    r'["\']',
    '@click="openProductEditor(detailProduct)"',
    product_text
)

# 兼容实际详情变量 selectedProduct / detailProduct
if "detailProduct" not in product_text:
    product_text = product_text.replace(
        '@click="openProductEditor(detailProduct)"',
        '@click="openProductEditor(selectedProduct)"'
    )

PRODUCT_LIST.write_text(
    product_text,
    encoding="utf-8"
)

print("已修改商品列表编辑入口")

print()
print("========================================")
print("商品编辑 V2 安装完成")
print("========================================")
print("请继续执行：")
print("cd /root/ppe-product-admin/web")
print("npm run build")
