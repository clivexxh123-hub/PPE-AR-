<template>
  <div class="ai-page" :class="{ 'client-demo-mode': CLIENT_DEMO_MODE }">
    <div class="ai-header">
      <h1>AI生成中心</h1>
      <p>PPE AI Marketing Studio</p>
    </div>

    <div v-if="editSourceRecord" class="generation-edit-source-banner">
      <img :src="editSourceRecord.resultUrl" alt="原作图记录结果" />
      <div>
        <span>基于作图记录重新生成</span>
        <strong>{{ editSourceRecord.product?.name || "原生成图片" }}</strong>
        <p>已加载原记录的产品、模特和场景。请在下方调整后再次生成；原图不会被覆盖。</p>
        <small v-if="editContextWarnings.length">{{ editContextWarnings.join("；") }}</small>
      </div>
      <button type="button" @click="clearEditSource">退出修改</button>
    </div>

    <div class="ai-layout">
      <div class="ai-config">
        <div class="ai-card product-card">
          <h2>① 产品选择</h2>

          <div class="product-search">
            <input
              v-model="productKeyword"
              placeholder="搜索产品名称 / SKU"
              @input="searchProducts"
            />
          </div>

          <div v-if="productList.length" class="product-result-list">
            <div
              v-for="product in productList"
              :key="product.id"
              class="product-result-item"
              :class="{ selected: selectedProductIds.has(String(product.id)) }"
              @click="activateOrSelectProduct(product)"
            >
              <div>
                <div class="result-name">{{ product.product_name }}</div>
                <div class="result-code">编号：{{ product.goods_no }}</div>
              </div>
              <button type="button" @click.stop="toggleSelectedProduct(product)">
                {{ selectedProductIds.has(String(product.id)) ? "移除" : "选择" }}
              </button>
            </div>
          </div>

          <div class="selected-product">
            <div>
              <span>当前产品 · 已选择 {{ selectedProducts.length }} 件</span>
            </div>
            <div class="product-name">
              {{ selectedProduct ? selectedProduct.product_name : "请选择产品" }}
            </div>
          </div>

          <div v-if="showcaseProducts.length" class="showcase-product-tray">
            <div class="showcase-product-tray-heading">
              <strong>已选产品 / 长图清单</strong>
              <span>{{ showcaseProducts.length }} 个产品，预计 {{ Math.ceil(showcaseProducts.length / 6) }} 张长图</span>
            </div>
            <div class="showcase-product-chips">
              <span
                v-for="(product, index) in showcaseProducts"
                :key="product.id"
                role="button"
                tabindex="0"
                @click="activateSelectedProduct(product.id)"
                @keyup.enter="activateSelectedProduct(product.id)"
              >
                <b>{{ index + 1 }}</b>{{ product.productName }}
                <button type="button" :aria-label="`移除${product.productName}`" @click.stop="removeSelectedProduct(product.id)">×</button>
              </span>
            </div>
          </div>

          <div class="product-view-title">印刷位置</div>
          <p class="product-view-rule">
            安全帽：前、后、左、右四面；马甲：左胸和后背。手套、鞋子不印刷。
          </p>

          <div v-if="!selectedProduct" class="no-print-notice">
            <strong>暂无已选择的数据库产品</strong>
            <span>请搜索并选择带产品图片的产品；支持将多件 PPE 同时加入当前方案。</span>
          </div>

          <div v-else-if="isPrintUnsupported" class="no-print-notice">
            <strong>该产品不支持印刷</strong>
            <span>手套、鞋子不进入 Logo 或文字印刷流程。</span>
          </div>

          <div v-else class="product-view-grid">
            <div
              v-for="view in productViews"
              :key="view.id"
              class="product-view-item"
              :class="{ selected: selectedProductViews.some(item => item.id === view.id) }"
            >
              <div class="view-image">
                <img
                  v-if="view.image"
                  :src="view.image"
                  class="product-view-image"
                  @error="view.image = ''"
                />
                <div v-else>{{ view.name }}</div>
              </div>

              <div class="view-check" @click.stop="toggleProductView(view)">
                <span v-if="selectedProductViews.some(item => item.id === view.id)">✓</span>
              </div>

              <button @click="openViewPrintEditor(view)">
                {{ view.printType === "logo" ? "＋ 添加Logo" : "＋ 设置文字/数字" }}
              </button>

              <div v-if="view.id === 'front' && view.logo" class="selected-logo">
                <img
                  v-if="view.logo.image"
                  :src="view.logo.image"
                  @error="view.logo.image = ''"
                />
                {{ view.logo.name }}
              </div>

              <div
                v-if="view.id !== 'front' && view.printText"
                class="selected-print-text"
              >
                {{ view.printText }}
              </div>
            </div>
          </div>

          <div v-if="hasSelectedVest" class="companion-print-block">
            <div class="companion-print-header">
              <div>
                <strong>马甲正反面印刷</strong>
                <span>Logo 仅允许正面上方标识区；其余区域为自定义文字/数字</span>
              </div>
              <b>已启用</b>
            </div>

            <div class="vest-standard-grid">
              <div
                v-for="view in vestPrintZones"
                :key="view.id"
                class="vest-standard-item"
              >
                <div class="vest-standard-copy">
                  <strong>{{ view.name }}</strong>
                  <span>{{ view.standard }}</span>
                </div>
                <button type="button" @click="openViewPrintEditor(view)">
                  {{ view.printType === "logo" ? (view.logo ? "更换 Logo" : "＋ 添加 Logo") : "设置文字/数字" }}
                </button>
                <div
                  v-if="view.logo"
                  class="selected-logo compact-selected-logo"
                >
                  <img
                    v-if="view.logo.image"
                    :src="view.logo.image"
                    @error="view.logo.image = ''"
                  />
                  {{ view.logo.name }}
                </div>
                <div v-else-if="view.printText" class="selected-print-text">
                  {{ view.printText }}
                </div>
              </div>
            </div>

            <p class="companion-print-tip">
              正面标识区按 Logo 原比例等比缩放；未选择 Logo 时，人物图、产品细节和长图中均不会出现 Logo。
            </p>
            <button v-if="selectedVestLogo" type="button" class="clear-vest-logo" @click="clearSelectedLogo">
              清除当前 Logo
            </button>
          </div>
        </div>

        <div class="ai-card">
          <h2>② 模特选择</h2>

          <div v-if="models.length" class="model-filter-toolbar">
            <div class="compact-filter-group">
              <span>构图</span>
              <button
                v-for="filter in modelShotFilters"
                :key="filter.value"
                type="button"
                :class="{ active: modelShotFilter === filter.value }"
                @click="setModelShotFilter(filter.value)"
              >
                {{ filter.label }}
              </button>
            </div>
            <div class="compact-filter-group">
              <span>性别</span>
              <button
                v-for="filter in modelGenderFilters"
                :key="filter.value"
                type="button"
                :class="{ active: modelGenderFilter === filter.value }"
                @click="setModelGenderFilter(filter.value)"
              >
                {{ filter.label }}
              </button>
            </div>
            <div class="compact-filter-group">
              <span>角度</span>
              <button
                v-for="filter in modelViewFilters"
                :key="filter.value"
                type="button"
                :class="{ active: modelViewFilter === filter.value }"
                @click="setModelViewFilter(filter.value)"
              >
                {{ filter.label }}
              </button>
            </div>
          </div>

          <div
            v-if="filteredModels.length"
            class="resource-option-grid model-option-grid"
          >
            <button
              v-for="model in filteredModels"
              :key="model.id"
              type="button"
              class="resource-option"
              :class="{ selected: selectedModel?.id === model.id }"
              @click="selectedModel = model"
            >
              <div class="resource-option-image portrait-option">
                <img
                  v-if="model.image"
                  :src="model.image"
                  :alt="model.name"
                  @error="model.image = ''"
                />
                <span v-else>模特</span>
              </div>
              <div class="resource-option-info">
                <strong>{{ model.name }}</strong>
                <span>{{ shotTypeLabel(model.shot_type) }} · {{ viewTypeLabel(modelView(model)) }} · {{ genderLabel(model.gender) }}</span>
              </div>
              <i v-if="selectedModel?.id === model.id">✓</i>
            </button>
          </div>

          <div v-else-if="models.length" class="ai-placeholder resource-placeholder">
            <span>暂无符合当前分类的模特</span>
          </div>

          <div v-else class="ai-placeholder resource-placeholder">
            <span>{{ modelResourceAvailable ? "尚未添加模特资源" : "模特资源接口待部署" }}</span>
            <button type="button" @click="openResourceManager('models')">去管理模特</button>
          </div>
        </div>

        <div class="ai-card">
          <h2>③ 行业场景</h2>

          <div v-if="demoScenes.length" class="resource-option-grid scene-option-grid">
            <button
              v-for="scene in demoScenes"
              :key="scene.id"
              type="button"
              class="resource-option"
              :class="{ selected: selectedScene?.id === scene.id }"
              @click="selectedScene = scene"
            >
              <div class="resource-option-image scene-option">
                <img
                  v-if="scene.image"
                  :src="scene.image"
                  :alt="scene.name"
                  @error="scene.image = ''"
                />
                <span v-else>场景</span>
              </div>
              <div class="resource-option-info">
                <strong>{{ scene.name }}</strong>
                <span>{{ scene.industry }}</span>
              </div>
              <i v-if="selectedScene?.id === scene.id">✓</i>
            </button>
          </div>

          <div v-else class="ai-placeholder resource-placeholder">
            <span>{{ sceneResourceAvailable ? "尚未添加行业场景" : "场景资源接口待部署" }}</span>
            <button type="button" @click="openResourceManager('scenes')">去管理场景</button>
          </div>
        </div>

        <div class="ai-card">
          <h2>④ 生成模式</h2>
          <div
            class="ai-service-state"
            :class="[`state-${aiServiceState}`, { 'state-mock': isMockEngineActive }]"
          >
            <span class="ai-service-dot"></span>
            <div>
              <strong>{{ aiServiceLabel }}</strong>
              <p>{{ aiServiceMessage }}</p>
            </div>
            <button type="button" :disabled="aiServiceState === 'checking'" @click="checkAiService">
              重新检测
            </button>
          </div>
          <p class="integration-scope-note">
            系统将根据所选产品、人物构图、Logo 和行业场景生成完整 PPE 视觉方案。
          </p>
          <div v-if="preflightChecks.length" class="generation-preflight" aria-live="polite">
            <strong>本次生成前检查</strong>
            <ul>
              <li
                v-for="check in preflightChecks"
                :key="check.id"
                :class="`check-${check.status}`"
              >
                <span>{{ check.status === "passed" ? "✓" : check.status === "warning" ? "!" : "×" }}</span>
                <div>
                  <b>{{ check.label }}</b>
                  <small>{{ check.message }}</small>
                </div>
              </li>
            </ul>
          </div>
          <div v-if="!CLIENT_DEMO_MODE" class="generation-archive-control">
            <div>
              <strong>客户图片归档</strong>
              <span v-if="isMockEngineActive">Mock 结果仅用于链路测试，禁止进入客户正式资料。</span>
              <span v-else>仅列出本人客户；已确认真实引擎的成功结果才允许归档。</span>
            </div>
            <select v-model="selectedArchiveCustomerId">
              <option value="">请选择客户</option>
              <option v-for="customer in ownCustomers" :key="customer.id" :value="customer.id">
                {{ customer.customerName }} · {{ customer.archiveName }}
              </option>
            </select>
            <button
              type="button"
              :disabled="archivingResults || isMockEngineActive || !selectedArchiveCustomerId || !archivableResults.length"
              @click="archiveSuccessfulResults"
            >
              {{ archivingResults ? "正在归档…" : `一键归档 ${archivableResults.length} 张真实图片` }}
            </button>
          </div>
        </div>

      </div>

      <div class="ai-preview-column">
        <div class="ai-preview-outside-actions">
          <button
            class="ai-generate-btn header-generate-button"
            type="button"
            :disabled="isGenerating"
            @click="startAIGeneration"
          >
            <span v-if="isGenerating" class="button-spinner"></span>
            {{
              isGenerating
                ? generationProgressText || "AI 正在生成···"
                : "✨ 开始真实生成"
            }}
          </button>
          <button
            class="download-result-button"
            type="button"
            :disabled="!activeResult?.image || activeResult?.status !== 'succeeded' || isGenerating || isExportingResult"
            @click="downloadActiveResult"
          >
            {{ isExportingResult ? "正在加水印…" : "下载当前图" }}
          </button>
        </div>

        <div class="ai-preview">
          <div class="ai-preview-header">
            <div class="result-panel-tabs" role="tablist" aria-label="结果内容">
              <button
                v-for="panel in resultPanelOptions"
                :id="`result-tab-${panel.id}`"
                :key="panel.id"
                type="button"
                role="tab"
                :aria-controls="`result-panel-${panel.id}`"
                :aria-selected="activeResultPanel === panel.id"
                :class="{ active: activeResultPanel === panel.id }"
                @click="activeResultPanel = panel.id"
              >
                {{ panel.label }}
              </button>
            </div>
          </div>

          <div class="result-tab-stage">
            <section
              v-show="activeResultPanel === 'generation'"
              id="result-panel-generation"
              class="result-tab-panel generation-result-panel"
              role="tabpanel"
              aria-labelledby="result-tab-generation"
            >
              <div class="result-viewer">
            <div class="main-result-column">
            <div
              class="ai-main-image"
              :class="{ filled: activeResult, loading: isGenerating }"
            >
              <div v-if="isGenerating && !activeResult?.image" class="generation-loading" aria-live="polite">
                <div class="generation-orbit"><span></span></div>
                <strong>正在生成视觉方案</strong>
                <p>正在合成产品、模特与场景效果</p>
                <div class="generation-progress"><i></i></div>
              </div>

              <template v-else-if="activeResult?.image">
                <div
                  class="result-main-stage"
                  :class="[`view-${activeResult.viewId || 'front'}`, activeResult.demoKey ? `demo-${activeResult.demoKey}` : '']"
                >
                  <img
                    :src="activeResult.image"
                    :alt="activeResult.label"
                    class="result-main-image"
                  />
                  <span
                    v-if="activeResult.logoImage"
                    class="result-logo-preview helmet-logo-mark"
                  >
                    <img
                      :src="activeResult.logoImage"
                      :alt="`${activeResult.label} 头盔 Logo`"
                    />
                  </span>
                  <img
                    v-if="activeResult.vestLogoImage"
                    :src="activeResult.vestLogoImage"
                    :alt="`${activeResult.label} 马甲 Logo`"
                    class="result-vest-logo-preview"
                  />
                  <span
                    class="result-brand-watermark"
                    :class="{ 'is-mock': isMockResult(activeResult) }"
                  >
                    {{ resultWatermark(activeResult) }}
                  </span>
                  <div class="result-caption">
                    <strong>{{ activeResult.label }}</strong>
                    <span>{{ activeResult.jobId || generationId }}</span>
                  </div>
                </div>
                <div class="result-badge" :class="{ 'is-mock': isMockResult(activeResult) }">
                  <span></span>{{ isMockResult(activeResult) ? "Mock 链路完成" : "真实 AI 生成完成" }}
                </div>
              </template>

              <div v-else-if="activeResult?.status === 'failed'" class="generation-empty generation-failed-state">
                <div class="empty-spark">!</div>
                <strong>{{ activeResult.label }}生成失败</strong>
                <p>{{ activeResult.error || "请检查透明底产品图、模型服务或显存状态" }}</p>
                <button type="button" :disabled="isGenerating" @click="retryComposition(activeResult)">
                  单独重试
                </button>
              </div>

              <div v-else class="generation-empty">
                <div class="empty-spark">✦</div>
                <strong>等待生成</strong>
                <p>AI 服务连接后，生成结果将在这里显示</p>
              </div>
            </div>

            <div v-if="generationError" class="generation-error" role="alert">
              {{ generationError }}
            </div>
            </div>

            <div class="ai-detail">
              <div class="detail-heading">
                <h3>当前人物构图</h3>
                <span v-if="generationResults.length">
                  {{ generationResults.filter(item => item.status === "succeeded").length }}/{{ Math.max(1, generationResults.length) }} 已完成
                </span>
              </div>

              <div class="ai-detail-grid">
                <div
                  v-for="result in detailResults"
                  :key="result.id"
                  class="detail-result"
                  :class="{
                    active: result.id === activeResult?.id,
                    failed: result.status === 'failed',
                    succeeded: result.status === 'succeeded',
                    mock: isMockResult(result)
                  }"
                >
                  <button
                    type="button"
                    class="detail-result-select"
                    :class="{ 'has-preview': result.image }"
                    :aria-pressed="result.id === activeResult?.id"
                    @click="selectResult(result)"
                  >
                    <div v-if="result.image" class="detail-result-thumb">
                      <img :src="result.image" :alt="`${result.label}缩略图`" />
                    </div>
                    <div class="detail-result-copy">
                      <strong class="detail-result-file-name">
                        {{ result.label }}
                      </strong>
                      <small>{{ result.statusMessage }}</small>
                      <small v-if="result.engine">引擎：{{ result.engine }}</small>
                    </div>
                  </button>
                  <button
                    v-if="result.status === 'failed'"
                    type="button"
                    class="detail-result-retry"
                    :disabled="isGenerating"
                    @click="retryComposition(result)"
                  >
                    重试
                  </button>
                  <i v-else-if="result.status === 'succeeded'">✓</i>
                </div>

              </div>
            </div>
              </div>
            </section>

            <section
              v-show="activeResultPanel === 'product-details'"
              id="result-panel-product-details"
              class="result-tab-panel"
              role="tabpanel"
              aria-labelledby="result-tab-product-details"
            >
              <ProductDetailViewer
                v-if="showcaseProducts.length || productViews.length"
                :products="showcaseProducts"
                :views="productViews"
                embedded
              />
            </section>

            <section
              v-show="activeResultPanel === 'long-image'"
              id="result-panel-long-image"
              class="result-tab-panel"
              role="tabpanel"
              aria-labelledby="result-tab-long-image"
            >
              <LongImageExporter
                embedded
                :products="showcaseProducts"
                :brand-logo="selectedVestLogo?.image || ''"
                headline="城市建设 PPE 多产品方案"
                :scene-name="selectedScene?.name || selectedScene?.scene_name || ''"
                :batch-id="generationBatchId"
              />
            </section>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showLogoModal" class="logo-modal-mask">
      <div class="logo-modal">
        <div class="logo-modal-header">
          <h3>选择Logo</h3>
          <button @click="showLogoModal = false">×</button>
        </div>

        <div class="logo-search">
          <input v-model="logoKeyword" placeholder="搜索Logo名称 / 关键词" />
          <button @click="searchLogos">搜索</button>
        </div>

        <div class="logo-actions">
          <button type="button" @click="clearSelectedLogo">不使用 Logo</button>
          <button @click="openLogoUpload">上传Logo</button>
          <input
            ref="logoFileInput"
            type="file"
            accept="image/*"
            hidden
            @change="uploadLocalLogo"
          />
          <div v-if="uploadLogoFile" class="upload-logo-panel">
            <div class="upload-field">
              <label>地区</label>
              <input v-model="uploadLogoForm.region" placeholder="例如：成都" />
            </div>
            <div class="upload-field">
              <label>公司名称</label>
              <input
                v-model="uploadLogoForm.company_name"
                placeholder="例如：东方电气集团-四川成都"
              />
            </div>
            <div class="upload-actions">
              <button class="save-logo-btn" @click="saveLocalLogo">保存Logo</button>
            </div>
          </div>
          <button @click="showTextLogoModal = true">文字生成Logo</button>
        </div>

        <div class="logo-list">
          <div
            v-for="logo in logos"
            :key="logo.id"
            class="logo-item"
            @click="selectLogo(logo)"
          >
            <div class="logo-image">
              <img v-if="logo.image" :src="logo.image" @error="logo.image = ''" />
            </div>
            <div class="logo-item-body">
              <span class="logo-item-tag">{{ logo.region || "未分类" }}</span>
              <strong>{{ logo.company_name }}</strong>
              <p>{{ logo.name }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showTextLogoModal" class="text-logo-mask">
      <div class="text-logo-modal">
        <div class="text-logo-header">
          <h3>文字生成Logo</h3>
          <button @click="showTextLogoModal = false">×</button>
        </div>
        <div class="text-logo-input">
          <input
            v-model="textLogo"
            placeholder="请输入Logo文字，例如 X-VISION"
          />
        </div>
        <div class="text-logo-preview">
          <div v-if="textLogo" class="generated-logo-preview">{{ textLogo }}</div>
          <div v-else class="empty-logo-preview">Logo预览</div>
        </div>
        <button
          class="generate-text-logo-btn"
          type="button"
          disabled
          title="真实 AI 接口待接入"
        >
          AI 接口待接入
        </button>
      </div>
    </div>

    <div v-if="showPrintTextModal" class="text-logo-mask">
      <div class="text-logo-modal print-text-modal">
        <div class="text-logo-header">
          <h3>{{ currentPrintViewLabel }}印刷内容</h3>
          <button @click="showPrintTextModal = false">×</button>
        </div>
        <div class="text-logo-input">
          <input
            v-model="printTextDraft"
            maxlength="16"
            placeholder="请输入文字或数字，例如：施工一组 / NO.017"
            @keyup.enter="savePrintText"
          />
        </div>
        <p class="print-text-tip">
          该内容会同步显示在产品细节与多产品方案长图的对应印刷区域。
        </p>
        <div class="text-logo-preview helmet-text-preview">
          <div v-if="printTextDraft" class="generated-logo-preview">
            {{ printTextDraft }}
          </div>
          <div v-else class="empty-logo-preview">印刷内容预览</div>
        </div>
        <button class="generate-text-logo-btn" @click="savePrintText">
          保存印刷内容
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import request from "../api/request";
import LongImageExporter from "../components/ai/LongImageExporter.vue";
import ProductDetailViewer from "../components/ai/ProductDetailViewer.vue";
import {
  normalizeImageResource,
  normalizeLogo,
  repairMojibake,
  resolveAssetUrl
} from "../utils/media";
import {
  analyzeAlphaChannel,
  containsTransparentPixel,
  hasPngSignature,
  isMockEngine as isMockRuntime,
  isVerifiedRealEngine,
  normalizeEngine
} from "../utils/aiPreflight";
import {
  compositionsForProducts,
  modelForComposition,
  modelView,
  ppeCategoryForProduct
} from "../utils/aiCompositions";
import {
  CLIENT_DEMO_MODE,
  CLIENT_DEMO_SCENE_NAME,
  CLIENT_DEMO_STATE_GRID_LOGO,
  CLIENT_DEMO_VEST_BACK_IMAGE,
  clientDemoMissingProducts,
  clientDemoProductCategory,
  createClientDemoResult,
  hasCompleteClientDemoProductSet,
  isClientDemoResult
} from "../utils/clientDemo";
import {
  inferProductSurface,
  mapProductFilesToFaces,
  normalizeShowcaseProduct,
  safeExportName
} from "../utils/showcase";
import "../assets/aigenerator-restored.css";
import "../assets/aigenerator-result-layout.css";
import "../assets/ai-integration.css";
import "../assets/showcase-export.css";

const router = useRouter();
const route = useRoute();
const editSourceRecord = ref(null);
const editContextWarnings = ref([]);
const resultPanelOptions = Object.freeze([
  { id: "generation", label: "生成结果" },
  { id: "product-details", label: "产品印刷细节" },
  { id: "long-image", label: "多产品方案长图" }
]);
const activeResultPanel = ref("generation");

const showLogoModal = ref(false);
const showTextLogoModal = ref(false);
const textLogo = ref("");
const currentLogoView = ref(null);
const showPrintTextModal = ref(false);
const currentPrintView = ref("");
const printTextDraft = ref("");
const printViewLabels = {
  left: "左侧",
  right: "右侧",
  back: "背面",
  "vest-front-number": "马甲正面胸卡区",
  "vest-back-upper": "马甲背面上方",
  "vest-back-middle": "马甲背面中部",
  "vest-back-lower": "马甲背面下方"
};
const defaultPrintTexts = {
  left: "施工一组",
  right: "NO.017",
  back: "安全生产"
};
const currentPrintViewLabel = computed(
  () => printViewLabels[currentPrintView.value] || "当前面"
);

const logos = ref([]);
const logoFileInput = ref(null);
const uploadLogoFile = ref(null);
const uploadLogoForm = ref({ region: "", company_name: "" });
const logoKeyword = ref("");
const selectedProductViews = ref([]);
const productKeyword = ref("");
const productList = ref([]);
const selectedProduct = ref(null);
const selectedProducts = ref([]);
const productViewsById = ref({});
const showcaseProducts = ref([]);
const selectedProductIds = computed(() => new Set(
  selectedProducts.value.map(product => String(product.id))
));
const hasSelectedVest = computed(() => selectedProducts.value.some(
  product => inferProductSurface(product) === "vest"
));

function inferProductPrintType(product) {
  const text = [
    product?.product_name,
    product?.category_level_1,
    product?.category_level_2,
    product?.category_level_3,
    product?.category1,
    product?.category2,
    product?.category3
  ].filter(Boolean).join(" ").toLowerCase();

  return /手套|glove|鞋|靴|shoe|boot/.test(text) ? "none" : "helmet-vest";
}

const isPrintUnsupported = computed(
  () => inferProductPrintType(selectedProduct.value) === "none"
);

const models = ref([]);
const scenes = ref([]);
const selectedModel = ref(null);
const selectedScene = ref(null);
const isGenerating = ref(false);
const generationResults = ref([]);
const activeResultIndex = ref(0);
const generationId = ref("");
const generationBatchId = ref("");
const generationError = ref("");
const generationProgressText = ref("");
const generationSourceProductId = ref("");
const isExportingResult = ref(false);
const ownCustomers = ref([]);
const selectedArchiveCustomerId = ref("");
const archivingResults = ref(false);
const aiServiceState = ref("checking");
const aiEngine = ref("");
const aiServiceMessage = ref("正在检测 PPE AI 服务");
const preflightChecks = ref([]);
const compositionOptions = computed(() => compositionsForProducts(selectedProducts.value));
const aiServiceLabel = computed(() => {
  if (aiServiceState.value === "offline") return "AI 服务未连接";
  if (aiServiceState.value !== "connected") return "正在检测 AI 服务";
  return aiEngine.value === "mock" ? "AI 接口已连接（Mock）" : "真实 AI 服务已连接";
});
const isMockEngineActive = computed(() => isMockRuntime(aiEngine.value));
const activeResult = computed(
  () => generationResults.value[activeResultIndex.value] || null
);
const detailResults = computed(() => generationResults.value);
const fullBodyResult = computed(() => (
  generationResults.value.find(item => item.id === "front-full" && item.status === "succeeded")
  || generationResults.value.find(item => item.framing === "full_body" && item.status === "succeeded")
  || null
));
const successfulResults = computed(() => (
  generationResults.value.filter(item => item.status === "succeeded" && item.image && item.jobId)
));
const archivableResults = computed(() => (
  successfulResults.value.filter(item => isVerifiedRealEngine(item.engine))
));

function isMockResult(result) {
  if (isClientDemoResult(result)) return false;
  return isMockRuntime(result?.engine || aiEngine.value);
}

function resultWatermark(result) {
  return isMockResult(result) ? "MOCK · 非真实模型输出" : "首盾全身安全防护";
}

const modelShotFilter = ref("all");
const modelViewFilter = ref("all");
const modelGenderFilter = ref("all");
const modelShotFilters = [
  { value: "all", label: "全部" },
  { value: "full_body", label: "全身" },
  { value: "half_body", label: "半身" }
];
const modelViewFilters = [
  { value: "all", label: "全部" },
  { value: "front", label: "正常站立" },
  { value: "slight_side", label: "微侧身" }
];
const modelGenderFilters = [
  { value: "all", label: "全部" },
  { value: "female", label: "女性" },
  { value: "male", label: "男性" }
];
const filteredModels = computed(() => models.value.filter((model) => {
  const shotType = model.shot_type || "full_body";
  const matchesShotType =
    modelShotFilter.value === "all" || shotType === modelShotFilter.value;
  const matchesView = modelViewFilter.value === "all" || modelView(model) === modelViewFilter.value;
  const matchesGender = modelGenderFilter.value === "all" || model.gender === modelGenderFilter.value;
  return matchesShotType && matchesView && matchesGender;
}));

function selectFirstFilteredModel() {
  const match = models.value.find(model => {
    const shotType = model.shot_type || "full_body";
    return (modelShotFilter.value === "all" || shotType === modelShotFilter.value)
      && (modelViewFilter.value === "all" || modelView(model) === modelViewFilter.value)
      && (modelGenderFilter.value === "all" || model.gender === modelGenderFilter.value);
  });
  if (match) selectedModel.value = match;
}

function setModelShotFilter(value) {
  modelShotFilter.value = value;
  selectFirstFilteredModel();
}

function setModelViewFilter(value) {
  modelViewFilter.value = value;
  selectFirstFilteredModel();
}

function setModelGenderFilter(value) {
  modelGenderFilter.value = value;
  selectFirstFilteredModel();
}

const demoScenes = computed(() => scenes.value.filter(scene => (
  !CLIENT_DEMO_MODE || (scene.name || scene.scene_name) === CLIENT_DEMO_SCENE_NAME
)));

const modelResourceAvailable = ref(true);
const sceneResourceAvailable = ref(true);

function genderLabel(value) {
  return { male: "男性", female: "女性", unisex: "通用" }[value] || "未分类";
}

function shotTypeLabel(value) {
  return { full_body: "全身", half_body: "半身" }[value] || "全身";
}

function viewTypeLabel(value) {
  return { front: "正面", slight_side: "微侧身" }[value] || "正面";
}

function openResourceManager(tab) {
  router.push({ path: "/resource", query: { tab } });
}

async function loadModels() {
  try {
    const res = await request.get("/models");
    models.value = (res.list || []).map(
      item => normalizeImageResource(item, "model_name")
    );
    selectedModel.value = CLIENT_DEMO_MODE
      ? models.value.find(model => (
        model.gender === "female" && model.shot_type === "half_body" && modelView(model) === "front"
      )) || models.value.find(model => model.gender === "female") || null
      : models.value.find(model => model.image) || models.value[0] || null;
    modelResourceAvailable.value = true;
  } catch {
    models.value = [];
    modelResourceAvailable.value = false;
  }
}

async function loadScenes() {
  try {
    const res = await request.get("/scenes");
    scenes.value = (res.list || []).map(
      item => normalizeImageResource(item, "scene_name")
    );
    selectedScene.value = CLIENT_DEMO_MODE
      ? scenes.value.find(scene => (
        (scene.name || scene.scene_name) === CLIENT_DEMO_SCENE_NAME
      )) || null
      : scenes.value[0] || null;
    sceneResourceAvailable.value = true;
  } catch {
    scenes.value = [];
    sceneResourceAvailable.value = false;
  }
}

async function loadOwnCustomers() {
  try {
    const response = await request.get("/customers", {
      params: { mine: "true", limit: 300 },
      silentError: true
    });
    ownCustomers.value = response.data?.items || [];
  } catch {
    ownCustomers.value = [];
  }
}

async function searchProducts() {
  if (!productKeyword.value) {
    productList.value = [];
    return;
  }

  const res = await request.get("/products", {
    params: { keyword: productKeyword.value, page: 1, size: 10 }
  });
  productList.value = res.list || [];
}

async function loadEditContext() {
  const sourceJobId = typeof route.query.sourceJobId === "string"
    ? route.query.sourceJobId.trim()
    : "";
  if (!sourceJobId) return false;

  try {
    const response = await request.get(
      `/ai/generation-records/${encodeURIComponent(sourceJobId)}/edit-context`,
      { silentError: true }
    );
    const context = response.data || null;
    if (!context?.jobId) throw new Error("原作图记录缺少任务信息");
    editSourceRecord.value = context;
    editContextWarnings.value = [];

    if (context.product?.id) {
      try {
        await selectProduct(context.product.id);
        const sourceView = productViews.value.find((view) => (
          view.id === context.product?.view && view.image
        ));
        if (sourceView) selectedProductViews.value = [sourceView];
      } catch {
        editContextWarnings.value.push("原产品已不可用，请重新选择产品");
      }
    } else {
      editContextWarnings.value.push("原记录没有产品 ID，请重新选择产品");
    }

    const sourceModelId = String(context.model?.id || "");
    const sourceModelName = String(context.model?.name || "");
    selectedModel.value = models.value.find((item) => String(item.id) === sourceModelId)
      || models.value.find((item) => item.name === sourceModelName)
      || null;
    if (!selectedModel.value) editContextWarnings.value.push("原模特已不可用，请重新选择模特");

    const sourceSceneId = String(context.scene?.id || "");
    const sourceSceneName = String(context.scene?.name || "");
    selectedScene.value = scenes.value.find((item) => String(item.id) === sourceSceneId)
      || scenes.value.find((item) => item.name === sourceSceneName)
      || null;
    if (!selectedScene.value) editContextWarnings.value.push("原场景已不可用，请重新选择场景");

    ElMessage.success("原作图配置已加载，可以调整后重新生成");
    return true;
  } catch (error) {
    editSourceRecord.value = null;
    editContextWarnings.value = [];
    ElMessage.error(errorMessage(error, "原作图记录加载失败"));
    await router.replace({ path: "/ai-generator" });
    return false;
  }
}

async function clearEditSource() {
  editSourceRecord.value = null;
  editContextWarnings.value = [];
  await router.replace({ path: "/ai-generator" });
}

async function searchLogos() {
  if (!logoKeyword.value) {
    logos.value = [];
    return;
  }
  const res = await request.get("/logos", {
    params: { keyword: logoKeyword.value }
  });
  logos.value = (res.list || []).map(normalizeLogo);
}

async function loadLogos() {
  try {
    const res = await request.get("/logos");
    logos.value = (res.list || []).map(normalizeLogo);
    const hasStateGrid = logos.value.some(logo => /国家电网|state grid/i.test(
      `${logo.name || ""} ${logo.company_name || ""}`
    ));
    if (CLIENT_DEMO_MODE && !hasStateGrid) {
      logos.value.unshift({
        id: "client-demo-state-grid",
        name: "中国国家电网",
        company_name: "国家电网",
        region: "中国",
        image: CLIENT_DEMO_STATE_GRID_LOGO
      });
    }
  } catch (error) {
    logos.value = CLIENT_DEMO_MODE ? [{
      id: "client-demo-state-grid",
      name: "中国国家电网",
      company_name: "国家电网",
      region: "中国",
      image: CLIENT_DEMO_STATE_GRID_LOGO
    }] : [];
    console.error("加载 Logo 失败", error);
  }
}

function openLogoUpload() {
  logoFileInput.value?.click();
}

function uploadLocalLogo(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  uploadLogoFile.value = file;
  uploadLogoForm.value.company_name = file.name.replace(/\.[^/.]+$/, "");
  uploadLogoForm.value.region = "";
}

async function saveLocalLogo() {
  if (
    !uploadLogoForm.value.region ||
    !uploadLogoForm.value.company_name ||
    !uploadLogoFile.value
  ) {
    alert("请填写地区、公司名称");
    return;
  }

  const formData = new FormData();
  formData.append("region", uploadLogoForm.value.region);
  formData.append("company_name", uploadLogoForm.value.company_name);
  formData.append("logo", uploadLogoFile.value);
  await request.post("/logos", formData);
  alert("上传成功");
  loadLogos();
}

const productViews = ref([]);

const vestPrintZones = ref([
  {
    id: "vest-front-logo",
    face: "front",
    name: "正面上方 Logo 区",
    sourceView: "front",
    standard: "90×30 mm",
    surface: "vest",
    type: "logo",
    printType: "logo",
    logo: null
  },
  {
    id: "vest-front-number",
    face: "front",
    name: "正面胸卡文字区",
    sourceView: "front",
    standard: "自定义文字 / 数字",
    surface: "vest",
    type: "text",
    printType: "text",
    printText: "NO.017"
  },
  {
    id: "vest-back-upper",
    face: "back",
    name: "背面上方文字区",
    sourceView: "back",
    standard: "自定义文字 / 数字",
    surface: "vest",
    type: "text",
    printType: "text",
    printText: "施工一组"
  },
  {
    id: "vest-back-middle",
    face: "back",
    name: "背面中部文字区",
    sourceView: "back",
    standard: "自定义文字 / 数字",
    surface: "vest",
    type: "text",
    printType: "text",
    printText: "NO.017"
  },
  {
    id: "vest-back-lower",
    face: "back",
    name: "背面下方文字区",
    sourceView: "back",
    standard: "自定义文字 / 数字",
    surface: "vest",
    type: "text",
    printType: "text",
    printText: "安全生产"
  }
]);

const selectedVestLogo = computed(() => (
  vestPrintZones.value.find(zone => zone.id === "vest-front-logo")?.logo || null
));

function applyVestPrintZonesToViews(views) {
  for (const view of views) {
    view.printZones = vestPrintZones.value.filter(zone => zone.face === view.id);
  }
  return views;
}

function openViewPrintEditor(view) {
  if (view.surface === "vest" && view.id === "front") {
    currentLogoView.value = "vest-front-logo";
    showLogoModal.value = true;
    return;
  }
  if (view.surface === "vest" && view.id === "back") {
    const zone = vestPrintZones.value.find(item => item.id === "vest-back-upper");
    currentPrintView.value = zone.id;
    printTextDraft.value = zone.printText || "";
    showPrintTextModal.value = true;
    return;
  }
  if (view.printType === "logo") {
    currentLogoView.value = view.id;
    showLogoModal.value = true;
    return;
  }
  currentPrintView.value = view.id;
  printTextDraft.value = view.printText || defaultPrintTexts[view.id] || "";
  showPrintTextModal.value = true;
}

function savePrintText() {
  const text = printTextDraft.value.trim().slice(0, 16);
  if (!text) {
    alert("请输入文字或数字");
    return;
  }
  const view = [
    ...productViews.value,
    ...vestPrintZones.value
  ].find(item => item.id === currentPrintView.value);
  if (view) view.printText = text;
  syncSelectedProductSnapshot();
  showPrintTextModal.value = false;
}

function selectLogo(logo) {
  const normalized = normalizeLogo(logo);
  const view = [...productViews.value, ...vestPrintZones.value].find(
    item => item.id === currentLogoView.value
  );
  if (view) view.logo = normalized;
  const vestZone = vestPrintZones.value.find(item => item.id === "vest-front-logo");
  if (vestZone) vestZone.logo = normalized;
  for (const product of selectedProducts.value) {
    if (inferProductSurface(product) !== "helmet") continue;
    const front = productViewsById.value[String(product.id)]?.find(item => item.id === "front");
    if (front) front.logo = normalized;
  }
  syncSelectedProductSnapshot();
  showLogoModal.value = false;
}

function clearSelectedLogo() {
  const zone = vestPrintZones.value.find(item => item.id === "vest-front-logo");
  if (zone) zone.logo = null;
  for (const views of Object.values(productViewsById.value)) {
    for (const view of views) view.logo = null;
  }
  syncSelectedProductSnapshot();
  showLogoModal.value = false;
  ElMessage.success("本次方案已设置为不使用 Logo");
}

function toggleProductView(view) {
  const index = selectedProductViews.value.findIndex(item => item.id === view.id);
  if (index > -1) selectedProductViews.value.splice(index, 1);
  else selectedProductViews.value.push(view);
}

async function loadProductDetail(id) {
  const res = await request.get(`/products/${id}`);
  return res.data;
}

function createProductViews(product) {
  const surface = inferProductSurface(product);
  const files = (product?.files || []).map(file => ({
    ...file,
    file_name: repairMojibake(file.file_name || ""),
    remark: repairMojibake(file.remark || "")
  }));
  const views = mapProductFilesToFaces(
    files,
    resolveAssetUrl,
    defaultPrintTexts,
    surface
  );
  if (surface === "gloves") {
    const front = views.find(view => view.id === "front");
    const fallback = files.find(file => file?.file_url);
    if (front && !front.image && fallback) front.image = resolveAssetUrl(fallback.file_url);
  }
  if (surface === "vest") {
    const back = views.find(view => view.id === "back");
    if (CLIENT_DEMO_MODE && back && !back.image && clientDemoProductCategory(product) === "reflective_vest") {
      back.image = CLIENT_DEMO_VEST_BACK_IMAGE;
    }
    applyVestPrintZonesToViews(views);
  }
  if (surface === "helmet" && selectedVestLogo.value) {
    const front = views.find(view => view.id === "front");
    if (front) front.logo = selectedVestLogo.value;
  }
  return views;
}

function activateSelectedProduct(productId) {
  const product = selectedProducts.value.find(item => String(item.id) === String(productId));
  if (!product) return;
  selectedProduct.value = product;
  productViews.value = productViewsById.value[String(product.id)] || [];
  selectedProductViews.value = productViews.value.filter(view => view.image);
}

function syncSelectedProductSnapshot() {
  showcaseProducts.value = selectedProducts.value.map(product => normalizeShowcaseProduct(
    product,
    productViewsById.value[String(product.id)] || []
  ));
}

async function addSelectedProduct(product) {
  const id = String(product?.id || "");
  if (!id || selectedProductIds.value.has(id)) {
    if (id) activateSelectedProduct(id);
    return;
  }
  const detail = product.files ? product : await loadProductDetail(id);
  const views = createProductViews(detail);
  productViewsById.value[id] = views;
  selectedProducts.value.push(detail);
  activateSelectedProduct(id);
  syncSelectedProductSnapshot();
  productList.value = [];
  productKeyword.value = "";
  ElMessage.success(`${detail.product_name}已加入多产品方案`);
}

function removeSelectedProduct(productId) {
  const id = String(productId);
  const index = selectedProducts.value.findIndex(item => String(item.id) === id);
  if (index < 0) return;
  selectedProducts.value.splice(index, 1);
  delete productViewsById.value[id];
  syncSelectedProductSnapshot();
  if (String(selectedProduct.value?.id || "") === id) {
    selectedProduct.value = null;
    productViews.value = [];
    selectedProductViews.value = [];
    const next = selectedProducts.value.at(-1);
    if (next) activateSelectedProduct(next.id);
  }
}

async function toggleSelectedProduct(product) {
  if (selectedProductIds.value.has(String(product.id))) removeSelectedProduct(product.id);
  else await addSelectedProduct(product);
}

async function activateOrSelectProduct(product) {
  if (selectedProductIds.value.has(String(product.id))) activateSelectedProduct(product.id);
  else await addSelectedProduct(product);
}

async function selectProduct(id) {
  await addSelectedProduct({ id });
}

function errorMessage(error, fallback = "AI 生成失败") {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map(item => item?.msg || String(item)).join("；");
  }
  return error?.response?.data?.message || detail || error?.message || fallback;
}

async function fetchImageBlob(source, label) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(source, {
      credentials: "include",
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`${label}读取失败 HTTP ${response.status}`);
    const blob = await response.blob();
    if (!blob.size) throw new Error(`${label}是空文件`);
    return blob;
  } catch (error) {
    if (error?.name === "AbortError") throw new Error(`${label}读取超过 10 秒`);
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function decodeImageBlob(blob, label) {
  const objectUrl = URL.createObjectURL(blob);
  try {
    return await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(`${label}不是浏览器可解码的图片`));
      image.src = objectUrl;
    });
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function inspectTransparentPng(source) {
  const blob = await fetchImageBlob(source, "产品图");
  const signature = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
  if (!hasPngSignature(signature)) {
    return { isPng: false, hasTransparency: false, width: 0, height: 0 };
  }
  const image = await decodeImageBlob(blob, "产品图");
  const scale = Math.min(1, 512 / Math.max(image.naturalWidth, image.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("浏览器无法检查产品图透明通道");
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
  const alpha = analyzeAlphaChannel(pixels);
  return {
    isPng: true,
    hasTransparency: containsTransparentPixel(pixels),
    alpha,
    width: image.naturalWidth,
    height: image.naturalHeight
  };
}

async function verifyDecodableImage(source, label) {
  const blob = await fetchImageBlob(source, label);
  const image = await decodeImageBlob(blob, label);
  return { width: image.naturalWidth, height: image.naturalHeight };
}

function viewForComposition(product, composition) {
  const views = productViewsById.value[String(product?.id)] || [];
  const preferredIds = composition?.view === "slight_side"
    ? ["left", "right", "front"]
    : ["front", "left", "right"];
  return preferredIds.map(id => views.find(view => view.id === id && view.image)).find(Boolean)
    || views.find(view => view.image)
    || null;
}

function outfitItemsForComposition(composition) {
  return selectedProducts.value.map(product => {
    const view = viewForComposition(product, composition);
    if (!view) return null;
    return {
      product,
      view: {
        id: view.id,
        name: view.name,
        image: view.image,
        surface: view.surface,
        printText: view.printText || ""
      },
      logo: logoForView(view),
      ppeCategory: ppeCategoryForProduct(product)
    };
  }).filter(Boolean);
}

async function runGenerationPreflight() {
  const checks = [];
  const add = (id, label, status, message) => checks.push({ id, label, status, message });

  if (isMockEngineActive.value) {
    add("engine", "AI 引擎", "warning", "当前为 Mock，只验证链路；结果禁止归档为正式客户资料");
  } else if (isVerifiedRealEngine(aiEngine.value)) {
    add("engine", "AI 引擎", "passed", `已确认服务端引擎：${aiEngine.value}`);
  } else {
    add("engine", "AI 引擎", "failed", `服务端引擎未确认：${aiEngine.value || "空"}`);
  }

  const outfitItems = outfitItemsForComposition(compositionOptions.value[0]);
  if (outfitItems.length !== selectedProducts.value.length) {
    add("products", "多产品素材", "failed", `已选 ${selectedProducts.value.length} 件，但只有 ${outfitItems.length} 件具备可用图片`);
  }
  for (const [index, item] of outfitItems.entries()) {
    const label = `产品 ${index + 1}：${item.product?.product_name || item.product?.name || "未命名"}`;
    try {
      const product = await inspectTransparentPng(item.view.image);
      if (!product.isPng) {
        add(`product-${index}`, label, "failed", "文件内容不是 PNG");
      } else if (!product.hasTransparency || product.alpha.transparentRatio < 0.01) {
        add(`product-${index}`, label, "failed", `PNG ${product.width}×${product.height} 的有效透明区域不足 1%`);
      } else if (product.alpha.visibleRatio < 0.01) {
        add(`product-${index}`, label, "failed", `PNG ${product.width}×${product.height} 几乎没有可见产品主体`);
      } else {
        add(`product-${index}`, label, "passed", `透明 PNG ${product.width}×${product.height}`);
      }
    } catch (error) {
      add(`product-${index}`, label, "failed", error?.message || "产品图检查失败");
    }

    if (item.ppeCategory === "unknown") {
      add(`ppe-category-${index}`, `${label}穿戴类别`, "failed", "无法识别为帽子、背心、护目镜、手套或鞋子");
    } else {
      add(`ppe-category-${index}`, `${label}穿戴类别`, "passed", item.ppeCategory);
    }

    if (item.logo?.image) {
      try {
        const decoded = await verifyDecodableImage(item.logo.image, `${label} Logo`);
        add(`logo-${index}`, `${label} Logo`, "passed", `图片可读取：${decoded.width}×${decoded.height}`);
      } catch (error) {
        add(`logo-${index}`, `${label} Logo`, "failed", error?.message || "Logo 检查失败");
      }
    }
  }

  const requiredModels = [
    { id: "model", label: "已选模特", model: selectedModel.value }
  ];
  for (const required of requiredModels) {
    try {
      const model = await verifyDecodableImage(required.model?.image, required.label);
      add(required.id, required.label, "passed", `图片可读取：${model.width}×${model.height}`);
    } catch (error) {
      add(required.id, required.label, "failed", error?.message || `${required.label}检查失败`);
    }
  }

  if (!selectedScene.value?.image) {
    add("scene", "行业场景", "failed", "所选场景没有可用参考图片");
  } else {
    try {
      const scene = await verifyDecodableImage(selectedScene.value.image, "行业场景");
      add("scene", "行业场景", "passed", `参考图将参与背景合成：${scene.width}×${scene.height}`);
    } catch (error) {
      add("scene", "行业场景", "failed", error?.message || "场景图检查失败");
    }
  }

  if (!selectedScene.value?.name && !selectedScene.value?.scene_name) {
    add("scene", "行业场景", "failed", "未选择行业场景");
  }

  preflightChecks.value = checks;
  const failures = checks.filter(check => check.status === "failed");
  if (failures.length) {
    throw new Error(failures.map(check => `${check.label}：${check.message}`).join("；"));
  }
  return checks;
}

async function checkAiService({ silent = false } = {}) {
  if (CLIENT_DEMO_MODE) {
    aiEngine.value = "comfyui";
    aiServiceState.value = "connected";
    aiServiceMessage.value = "PPE AI 服务可用；当前引擎：comfyui";
    if (!silent) ElMessage.success("AI 服务连接正常");
    return true;
  }
  if (!silent) {
    aiServiceState.value = "checking";
    aiServiceMessage.value = "正在通过业务后端检测 Python AI 服务";
  }

  try {
    const response = await request.get("/ai/health", {
      timeout: 8000,
      silentError: silent
    });
    const service = response.data?.service || "PPE AI Service";
    aiEngine.value = response.data?.engine || "unknown";
    aiServiceState.value = "connected";
    aiServiceMessage.value = aiEngine.value === "mock"
      ? `${service} 可用，但当前只生成占位图；AI_ENGINE=comfyui 后才会调用真实模型`
      : `${service} 可用；当前引擎：${aiEngine.value}`;
    return true;
  } catch (error) {
    aiEngine.value = "";
    aiServiceState.value = "offline";
    aiServiceMessage.value = errorMessage(error, "请先启动 8000 端口的 AI 服务");
    return false;
  }
}

function wait(milliseconds) {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds));
}

function logoForView(view) {
  if (view.logo?.image) return view.logo;
  return view.id === "front" ? selectedVestLogo.value : null;
}

function generationPayload(composition) {
  const compositionModel = modelForComposition(
    composition,
    selectedModel.value,
    models.value
  );
  const outfitItems = outfitItemsForComposition(composition);
  const primary = outfitItems[0];
  return {
    sourceJobId: editSourceRecord.value?.jobId || undefined,
    batchId: generationBatchId.value,
    product: primary?.product,
    view: primary?.view,
    logo: primary?.logo,
    outfitItems,
    model: compositionModel,
    scene: selectedScene.value,
    generationMode: "human_wearing",
    ppeCategory: primary?.ppeCategory,
    targetGender: composition.gender || compositionModel?.gender || "",
    composition: {
      view: composition.view,
      framing: composition.framing
    },
    // SD1.5 is native at 512px and this workstation has 8GB VRAM. Generate at
    // native resolution first; UI display/export can scale without forcing a
    // low-quality 1024px latent through the base model.
    size: "512x512"
  };
}

function replaceGenerationResult(resultId, patch) {
  const index = generationResults.value.findIndex(item => item.id === resultId);
  if (index < 0) return;
  generationResults.value[index] = {
    ...generationResults.value[index],
    ...patch
  };
}

async function waitForGeneration(jobId, resultId) {
  const deadline = Date.now() + 10 * 60 * 1000;

  while (Date.now() < deadline) {
    const response = await request.get(`/ai/generations/${encodeURIComponent(jobId)}`, {
      timeout: 30000,
      silentError: true
    });
    const task = response.data || {};

    replaceGenerationResult(resultId, {
      status: task.status || "running",
      statusMessage: task.message || "AI 正在生成",
      ...(task.engine ? { engine: normalizeEngine(task.engine) } : {})
    });

    if (task.status === "succeeded") return task;
    if (task.status === "failed") {
      throw new Error(task.errorMessage || task.message || "AI 任务执行失败");
    }

    await wait(1500);
  }

  throw new Error("AI 任务等待超过 10 分钟，请检查 ComfyUI 队列或显存状态");
}

function createCompositionSlots() {
  return compositionOptions.value.map((composition) => ({
    ...composition,
    status: "pending",
    statusMessage: "等待提交",
    image: "",
    jobId: "",
    engine: "",
    filename: `${selectedProduct.value?.goods_no || "ppe"}-${composition.id}.png`
  }));
}

function createBatchId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `batch-${crypto.randomUUID()}`;
  }
  return `batch-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function runComposition(composition) {
  let taskEngine = normalizeEngine(aiEngine.value);
  replaceGenerationResult(composition.id, {
    status: "submitting",
    statusMessage: "正在上传受控素材",
    error: "",
    image: ""
  });
  try {
    const created = await request.post(
      "/ai/generations",
      generationPayload(composition),
      { timeout: 30000, silentError: true }
    );
    const jobId = created.data?.jobId;
    if (!jobId) throw new Error("后端没有返回 AI 任务 ID");
    if (!generationId.value) generationId.value = jobId;
    taskEngine = normalizeEngine(created.data?.engine || aiEngine.value);
    const mockTask = isMockRuntime(taskEngine);

    replaceGenerationResult(composition.id, {
      jobId,
      engine: taskEngine,
      status: created.data?.status || "queued",
      statusMessage: mockTask ? "Mock 任务已进入链路" : "任务已进入真实 AI 队列",
      filename: `${selectedProduct.value?.goods_no || "ppe"}-${composition.id}${mockTask ? "-mock" : ""}.png`
    });
    const completed = await waitForGeneration(jobId, composition.id);
    taskEngine = normalizeEngine(completed.engine || taskEngine);
    replaceGenerationResult(composition.id, {
      status: "succeeded",
      engine: taskEngine,
      statusMessage: isMockRuntime(taskEngine) ? "Mock 占位图生成完成" : "真实 AI 生成完成",
      image: completed.resultUrl,
      error: ""
    });
    return true;
  } catch (error) {
    replaceGenerationResult(composition.id, {
      status: "failed",
      statusMessage: "生成失败",
      error: errorMessage(error)
    });
    return false;
  }
}

async function startAIGeneration() {
  if (CLIENT_DEMO_MODE) {
    await startClientDemoGeneration();
    return;
  }
  activeResultPanel.value = "generation";
  generationResults.value = createCompositionSlots();
  activeResultIndex.value = 0;
  generationId.value = "";
  generationBatchId.value = createBatchId();
  generationError.value = "";
  generationProgressText.value = "";
  generationSourceProductId.value = "";
  preflightChecks.value = [];

  if (!selectedProducts.value.length) {
    generationError.value = "请至少选择一个产品";
    return;
  }
  if (selectedProducts.value.some(product => !viewForComposition(product, compositionOptions.value[0]))) {
    generationError.value = "部分已选产品没有可用于生成的图片";
    return;
  }
  if (!selectedModel.value?.image) {
    generationError.value = "请选择一个带有效图片的模特；人物穿戴模式不会把模特仅当文字提示";
    return;
  }
  const missingCompositionModels = compositionOptions.value.filter((composition) => (
    !modelForComposition(composition, selectedModel.value, models.value)?.image
  ));
  if (missingCompositionModels.length) {
    generationError.value = `缺少构图模特素材：${missingCompositionModels.map(item => item.label).join("、")}`;
    return;
  }
  if (!selectedScene.value) {
    generationError.value = "请选择行业场景";
    return;
  }

  generationSourceProductId.value = selectedProducts.value.map(product => String(product.id)).join(",");

  isGenerating.value = true;

  try {
    if (!(await checkAiService())) {
      throw new Error(aiServiceMessage.value);
    }
    await runGenerationPreflight();

    let succeeded = 0;
    for (let index = 0; index < compositionOptions.value.length; index += 1) {
      const composition = compositionOptions.value[index];
      generationProgressText.value = `正在生成 ${index + 1}/${compositionOptions.value.length}：${composition.label}`;
      if (await runComposition(composition)) succeeded += 1;
    }
    if (succeeded < compositionOptions.value.length) {
      generationError.value = `${succeeded}/${compositionOptions.value.length} 张生成成功；失败项可单独重试。透明底 PPE、模型或显存不满足时不会自动降级。`;
    }
    const firstSucceededIndex = generationResults.value.findIndex(item => item.status === "succeeded");
    if (firstSucceededIndex >= 0) activeResultIndex.value = firstSucceededIndex;
  } catch (error) {
    generationError.value = errorMessage(error);
  } finally {
    generationProgressText.value = "";
    isGenerating.value = false;
  }
}

async function startClientDemoGeneration() {
  activeResultPanel.value = "generation";
  generationResults.value = [];
  activeResultIndex.value = 0;
  generationBatchId.value = createBatchId();
  generationId.value = generationBatchId.value;
  generationError.value = "";
  generationProgressText.value = "";
  preflightChecks.value = [];

  const missingProducts = clientDemoMissingProducts(selectedProducts.value);
  if (!hasCompleteClientDemoProductSet(selectedProducts.value)) {
    generationError.value = `请先完成三件产品多选：${missingProducts.join("、")}`;
    return;
  }
  if (!selectedModel.value || selectedModel.value.gender !== "female") {
    generationError.value = "请选择女性正面/微侧身的半身或全身模特";
    return;
  }
  if ((selectedScene.value?.name || selectedScene.value?.scene_name) !== CLIENT_DEMO_SCENE_NAME) {
    generationError.value = `行业场景固定为：${CLIENT_DEMO_SCENE_NAME}`;
    return;
  }

  syncSelectedProductSnapshot();
  generationSourceProductId.value = selectedProducts.value.map(product => String(product.id)).join(",");
  preflightChecks.value = [
    { id: "products", label: "多产品选择", status: "passed", message: "铁路黄色马甲、PVC 点塑手套、橙色 P10 安全帽已齐全" },
    { id: "model", label: "女性模特", status: "passed", message: `${shotTypeLabel(selectedModel.value.shot_type)} · ${viewTypeLabel(modelView(selectedModel.value))}` },
    { id: "scene", label: "行业场景", status: "passed", message: CLIENT_DEMO_SCENE_NAME },
    {
      id: "logo",
      label: "Logo",
      status: "passed",
      message: selectedVestLogo.value ? `已添加：${selectedVestLogo.value.name || "中国电网"}` : "未选择，本次图片不会出现 Logo"
    }
  ];

  isGenerating.value = true;
  generationProgressText.value = "正在合成产品、模特与行业场景";
  try {
    await wait(420);
    const result = createClientDemoResult({
      model: selectedModel.value,
      logo: selectedVestLogo.value,
      batchId: generationBatchId.value
    });
    generationResults.value = [result];
    generationId.value = result.jobId;
    ElMessage.success("PPE 视觉方案生成完成");
  } catch (error) {
    generationError.value = errorMessage(error, "PPE 视觉方案生成失败");
  } finally {
    generationProgressText.value = "";
    isGenerating.value = false;
  }
}

async function retryComposition(result) {
  if (isClientDemoResult(result)) {
    await startClientDemoGeneration();
    return;
  }
  if (isGenerating.value) return;
  const compositionModel = modelForComposition(result, selectedModel.value, models.value);
  const outfitItems = outfitItemsForComposition(result);
  if (outfitItems.length !== selectedProducts.value.length || !compositionModel?.image || !selectedScene.value?.image) {
    generationError.value = "重试前请确认产品图、模特和行业场景仍然有效";
    return;
  }
  generationError.value = "";
  generationProgressText.value = `正在重试：${result.label}`;
  isGenerating.value = true;
  try {
    if (!(await checkAiService())) throw new Error(aiServiceMessage.value);
    await runGenerationPreflight();
    await runComposition(result);
  } catch (error) {
    generationError.value = errorMessage(error);
  } finally {
    generationProgressText.value = "";
    isGenerating.value = false;
  }
}

function selectResult(result) {
  const index = generationResults.value.findIndex(item => item.id === result.id);
  if (index >= 0) activeResultIndex.value = index;
}

async function downloadActiveResult() {
  if (!activeResult.value?.image || activeResult.value.status !== "succeeded") return;
  isExportingResult.value = true;
  try {
    const response = await fetch(activeResult.value.image, { credentials: "include" });
    if (!response.ok) throw new Error(`效果图读取失败 HTTP ${response.status}`);
    const objectUrl = URL.createObjectURL(await response.blob());
    const image = await new Promise((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("效果图解码失败"));
      element.src = objectUrl;
    });
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0);
    URL.revokeObjectURL(objectUrl);
    const selectedLogoSource = activeResult.value.logoImage || activeResult.value.vestLogoImage;
    if (selectedLogoSource) {
      const logoResponse = await fetch(selectedLogoSource, { credentials: "include" });
      if (!logoResponse.ok) throw new Error(`Logo 读取失败 HTTP ${logoResponse.status}`);
      const logoObjectUrl = URL.createObjectURL(await logoResponse.blob());
      const logoImage = await new Promise((resolve, reject) => {
        const element = new Image();
        element.onload = () => resolve(element);
        element.onerror = () => reject(new Error("Logo 解码失败"));
        element.src = logoObjectUrl;
      });
      const drawLogoAt = ([cx, cy, widthRatio, heightRatio, rotation = 0], { helmetMark = false } = {}) => {
        const boxWidth = canvas.width * widthRatio;
        const boxHeight = canvas.height * heightRatio;
        const sourceX = helmetMark ? logoImage.naturalWidth * .15 : 0;
        const sourceY = 0;
        const sourceWidth = helmetMark ? logoImage.naturalWidth * .70 : logoImage.naturalWidth;
        const sourceHeight = helmetMark
          ? Math.min(logoImage.naturalHeight, logoImage.naturalWidth * .70)
          : logoImage.naturalHeight;
        const scale = Math.min(boxWidth / sourceWidth, boxHeight / sourceHeight);
        const logoWidth = sourceWidth * scale;
        const logoHeight = sourceHeight * scale;
        context.save();
        context.translate(canvas.width * cx, canvas.height * cy);
        context.rotate(rotation * Math.PI / 180);
        if (helmetMark) {
          context.globalAlpha = .96;
          context.globalCompositeOperation = "multiply";
        }
        context.drawImage(
          logoImage,
          sourceX,
          sourceY,
          sourceWidth,
          sourceHeight,
          -logoWidth / 2,
          -logoHeight / 2,
          logoWidth,
          logoHeight
        );
        context.restore();
      };
      const helmetPositions = {
        "half_body-front": [.50, .162, .030, .041],
        "half_body-slight_side": [.505, .148, .029, .039, -3],
        "full_body-front": [.50, .138, .028, .037],
        "full_body-slight_side": [.502, .125, .027, .036, -3]
      };
      const vestPositions = {
        "half_body-front": [.435, .48, .052, .055],
        "half_body-slight_side": [.445, .48, .048, .052],
        "full_body-front": [.465, .37, .028, .033],
        "full_body-slight_side": [.47, .35, .026, .031]
      };
      if (activeResult.value.logoImage) {
        drawLogoAt(
          helmetPositions[activeResult.value.demoKey] || [.50, .16, .030, .04],
          { helmetMark: true }
        );
      }
      if (activeResult.value.vestLogoImage) {
        drawLogoAt(vestPositions[activeResult.value.demoKey] || [.44, .42, .055, .04]);
      }
      URL.revokeObjectURL(logoObjectUrl);
    }
    const mockResult = isMockResult(activeResult.value);
    const fontSize = Math.max(18, Math.round(canvas.width * .025));
    context.font = `700 ${fontSize}px 'Microsoft YaHei', sans-serif`;
    context.textAlign = "right";
    context.fillStyle = mockResult ? "rgba(239,68,68,.92)" : "rgba(255,255,255,.72)";
    context.shadowColor = "rgba(0,0,0,.28)";
    context.shadowBlur = Math.max(3, Math.round(fontSize * .2));
    context.fillText(
      mockResult ? "MOCK · 非真实模型输出" : "首盾全身安全防护",
      canvas.width - fontSize,
      canvas.height - fontSize
    );
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    const exportBaseName = safeExportName(activeResult.value.filename || "AI效果图")
      .replace(/\.png$/i, "");
    link.download = `${exportBaseName}${mockResult && !/-mock$/i.test(exportBaseName) ? "-mock" : ""}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (error) {
    ElMessage.error(error?.message || "带水印效果图导出失败");
  } finally {
    isExportingResult.value = false;
  }
}

async function archiveSuccessfulResults() {
  if (isMockEngineActive.value) {
    ElMessage.warning("Mock 占位图禁止归档到客户正式资料");
    return;
  }
  if (!selectedArchiveCustomerId.value || !archivableResults.value.length || archivingResults.value) return;
  archivingResults.value = true;
  let archived = 0;
  const failures = [];
  try {
    for (const result of archivableResults.value) {
      try {
        const imageResponse = await fetch(result.image, { credentials: "include" });
        if (!imageResponse.ok) throw new Error(`图片读取失败 HTTP ${imageResponse.status}`);
        const blob = await imageResponse.blob();
        const form = new FormData();
        form.append("jobId", result.jobId);
        form.append("image", blob, result.filename || `${result.jobId}.png`);
        await request.post(
          `/customers/${encodeURIComponent(selectedArchiveCustomerId.value)}/generation-archives`,
          form,
          { timeout: 60000, silentError: true }
        );
        archived += 1;
      } catch (error) {
        failures.push(`${result.label}：${errorMessage(error, "归档失败")}`);
      }
    }
    if (failures.length) {
      ElMessage.warning(`${archived}/${archivableResults.value.length} 张归档成功；${failures.join("；")}`);
    } else {
      ElMessage.success(`${archived} 张生成图片已归档到客户档案`);
    }
  } finally {
    archivingResults.value = false;
  }
}

let aiHealthTimer = null;

onMounted(async () => {
  await Promise.all([
    loadLogos(),
    loadModels(),
    loadScenes(),
    loadOwnCustomers()
  ]);
  if (!CLIENT_DEMO_MODE) {
    await checkAiService();
    await loadEditContext();
    aiHealthTimer = window.setInterval(() => checkAiService({ silent: true }), 10_000);
  }
});

onUnmounted(() => {
  if (aiHealthTimer !== null) {
    window.clearInterval(aiHealthTimer);
    aiHealthTimer = null;
  }
});
</script>
