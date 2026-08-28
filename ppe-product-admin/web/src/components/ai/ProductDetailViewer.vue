<script setup>
import { computed, ref, watch } from "vue";

import {
  FACE_LABELS,
  FACE_ORDER,
  facePrintInstruction,
  facesForSurface
} from "../../utils/showcase";

const props = defineProps({
  products: {
    type: Array,
    default: () => []
  },
  views: {
    type: Array,
    default: () => []
  },
  embedded: { type: Boolean, default: false }
});

const activeProductId = ref("");
const activeFace = ref("front");
const availableProducts = computed(() => {
  if (props.products.length) return props.products;
  return props.views.length ? [{
    id: "current-product",
    productName: "当前产品",
    goodsNo: "",
    surface: props.views.find(view => view?.surface)?.surface || "ppe",
    views: props.views
  }] : [];
});
const activeProduct = computed(() => (
  availableProducts.value.find(product => String(product.id) === activeProductId.value)
  || availableProducts.value[0]
  || null
));
const sourceViews = computed(() => activeProduct.value?.views || props.views);
const activeSurface = computed(() => (
  activeProduct.value?.surface
  || sourceViews.value.find(view => view?.surface)?.surface
  || "ppe"
));
const orderedViews = computed(() => facesForSurface(activeSurface.value).map((id) => {
  const source = sourceViews.value.find(view => view.id === id) || {};
  return { ...source, id, name: FACE_LABELS[id] };
}));
const activeView = computed(() => (
  orderedViews.value.find(view => view.id === activeFace.value) || orderedViews.value[0]
));
const missingFaces = computed(() => orderedViews.value.filter(view => !view.image));

let knownProductIds = new Set();
watch(() => availableProducts.value.map(product => String(product.id)), (ids) => {
  const products = availableProducts.value;
  if (!products.length) {
    activeProductId.value = "";
    knownProductIds = new Set();
    return;
  }
  const newVest = products.find(product => (
    product.surface === "vest" && !knownProductIds.has(String(product.id))
  ));
  if (newVest || !products.some(product => String(product.id) === activeProductId.value)) {
    const preferred = newVest || products.find(product => product.surface === "vest") || products[0];
    activeProductId.value = String(preferred.id);
  }
  knownProductIds = new Set(ids);
}, { immediate: true });

watch([sourceViews, activeSurface], () => {
  if (!orderedViews.value.some(view => view.id === activeFace.value && view.image)) {
    activeFace.value = orderedViews.value.find(view => view.image)?.id || "front";
  }
}, { deep: true, immediate: true });

function overlay(view) {
  const logoImage = view?.logo?.image || view?.logo?.logo_url || "";
  const logoName = view?.logo?.name || view?.logo?.logo_name || "";
  return {
    logoImage,
    logoName,
    text: view?.printText || "",
    zones: Array.isArray(view?.printZones)
      ? view.printZones.filter(zone => zone.face === view.id)
      : []
  };
}

function zoneLogo(zone) {
  return zone?.logo?.image || zone?.logo?.logo_url || "";
}
</script>

<template>
  <section class="face-detail-viewer" :class="{ embedded }">
    <div class="face-detail-heading">
      <div>
        <span>2D PRODUCT DETAILS</span>
        <h3>产品印刷细节</h3>
      </div>
      <small>先切换产品，再点击对应面查看底图和印刷位置。</small>
    </div>

    <div v-if="availableProducts.length > 1" class="face-product-tabs">
      <button
        v-for="product in availableProducts"
        :key="product.id"
        type="button"
        :class="{ active: String(product.id) === String(activeProduct?.id) }"
        @click="activeProductId = String(product.id); activeFace = 'front'"
      >
        <span>{{ product.productName }}</span>
        <small>{{ product.goodsNo || ({ vest: '反光马甲', helmet: '安全帽', gloves: '防护手套' }[product.surface] || 'PPE 产品') }}</small>
      </button>
    </div>

    <div class="face-detail-layout">
      <div class="face-detail-main">
        <div
          v-if="activeView?.image"
          class="face-image-stage"
          :class="[`face-${activeView.id}`, `surface-${activeSurface}`]"
        >
          <img class="face-product-base" :src="activeView.image" :alt="`${activeView.name}产品底图`" />
          <template v-if="overlay(activeView).zones.length">
            <template v-for="zone in overlay(activeView).zones" :key="zone.id">
              <img
                v-if="zone.type === 'logo' && zoneLogo(zone)"
                class="face-print-zone"
                :class="`zone-${zone.id}`"
                :src="zoneLogo(zone)"
                :alt="zone.logo?.name || '印刷 Logo'"
              />
              <span
                v-else-if="zone.type === 'text' && (zone.text || zone.printText)"
                class="face-print-zone face-zone-text"
                :class="`zone-${zone.id}`"
              >
                {{ zone.text || zone.printText }}
              </span>
            </template>
          </template>
          <span
            v-else-if="overlay(activeView).logoImage"
            class="face-logo-overlay"
            :class="{ 'helmet-logo-mark': activeSurface === 'helmet' }"
          >
            <img
              :src="overlay(activeView).logoImage"
              :alt="overlay(activeView).logoName || '印刷 Logo'"
            />
          </span>
          <span v-else-if="overlay(activeView).text" class="face-text-overlay">
            {{ overlay(activeView).text }}
          </span>
        </div>
        <div v-else class="face-image-missing">
          <strong>{{ activeView?.name }}底图缺失</strong>
          <span>请由管理员在商品资料中上传明确标注的该面底图。</span>
        </div>
        <div class="face-main-caption">
          <strong>{{ activeView?.name }}</strong>
          <span>{{ facePrintInstruction(activeView) }}</span>
        </div>
      </div>

      <div class="face-detail-thumbnails" :class="`faces-${orderedViews.length}`">
        <button
          v-for="view in orderedViews"
          :key="view.id"
          type="button"
          :class="{ active: view.id === activeFace, missing: !view.image }"
          @click="activeFace = view.id"
        >
          <div class="face-thumb-stage" :class="[`face-${view.id}`, `surface-${activeSurface}`]">
            <img v-if="view.image" class="face-product-base" :src="view.image" :alt="view.name" />
            <span v-else>缺图</span>
            <template v-if="view.image && overlay(view).zones.length">
              <template v-for="zone in overlay(view).zones" :key="zone.id">
                <img
                  v-if="zone.type === 'logo' && zoneLogo(zone)"
                  class="face-print-zone"
                  :class="`zone-${zone.id}`"
                  :src="zoneLogo(zone)"
                  alt=""
                />
                <i
                  v-else-if="zone.type === 'text' && (zone.text || zone.printText)"
                  class="face-print-zone face-zone-text"
                  :class="`zone-${zone.id}`"
                >
                  {{ zone.text || zone.printText }}
                </i>
              </template>
            </template>
            <span
              v-else-if="view.image && overlay(view).logoImage"
              class="face-logo-overlay"
              :class="{ 'helmet-logo-mark': activeSurface === 'helmet' }"
            >
              <img :src="overlay(view).logoImage" alt="" />
            </span>
            <i v-else-if="view.image && overlay(view).text" class="face-text-overlay">
              {{ overlay(view).text }}
            </i>
          </div>
          <strong>{{ view.name }}</strong>
          <small>{{ facePrintInstruction(view) }}</small>
        </button>
      </div>
    </div>

    <div v-if="missingFaces.length" class="face-missing-warning">
      缺少 {{ missingFaces.map(view => view.name).join("、") }}底图；系统不会使用其他面替代。
    </div>
  </section>
</template>

<style scoped>
.face-detail-viewer {
  margin-top: 24px;
  padding: 22px;
  border: 1px solid #e4e9f2;
  border-radius: 18px;
  background: #fff;
}

.face-detail-viewer.embedded {
  box-sizing: border-box;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  margin-top: 0;
  flex-direction: column;
  overflow: hidden;
  border: 0;
  border-radius: 0;
}

.face-detail-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}

.face-detail-heading span {
  color: #315efb;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .14em;
}

.face-detail-heading h3 {
  margin: 4px 0 0;
  color: #18243f;
  font-size: 16px;
}

.face-detail-heading small {
  max-width: 420px;
  color: #7b879d;
  font-size: 11px;
  line-height: 1.55;
  text-align: right;
}

.face-product-tabs {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
  margin: -2px 0 14px;
  overflow-x: auto;
  padding: 2px 2px 5px;
}

.face-product-tabs button {
  display: flex;
  min-width: 150px;
  max-width: 240px;
  padding: 9px 12px;
  border: 1px solid #dce4f2;
  border-radius: 10px;
  color: #344054;
  background: #f8faff;
  cursor: pointer;
  flex-direction: column;
  text-align: left;
}

.face-product-tabs button.active {
  border-color: #315efb;
  color: #1d46d7;
  background: #eef3ff;
  box-shadow: 0 0 0 2px rgba(49, 94, 251, .1);
}

.face-product-tabs span {
  overflow: hidden;
  font-size: 11px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.face-product-tabs small {
  margin-top: 3px;
  color: #7b879d;
  font-size: 9px;
}

.face-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, .75fr);
  gap: 16px;
  align-items: start;
}

.embedded .face-detail-layout {
  flex: 1 1 auto;
  min-height: 0;
  grid-template-columns: minmax(0, 1.55fr) minmax(220px, .75fr);
}

.face-detail-main,
.face-detail-thumbnails button {
  min-width: 0;
  border: 1px solid #e4e9f2;
  border-radius: 14px;
  background: #f8faff;
}

.embedded .face-detail-main {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

.face-image-stage,
.face-thumb-stage {
  position: relative;
  display: grid;
  overflow: hidden;
  place-items: center;
  background: linear-gradient(145deg, #eef2f9, #fff);
}

.face-image-stage {
  height: clamp(300px, 30vw, 460px);
  min-height: 0;
  border-radius: 14px 14px 0 0;
}

.embedded .face-image-stage,
.embedded .face-image-missing {
  flex: 1 1 auto;
  height: auto;
  min-height: 0;
  max-height: none;
}

.face-image-stage > .face-product-base,
.face-thumb-stage > .face-product-base {
  position: absolute;
  inset: 0;
  display: block;
  width: 100% !important;
  height: 100% !important;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain !important;
  object-position: center;
  transform: none !important;
}

.face-logo-overlay,
.face-text-overlay {
  position: absolute;
  top: 47%;
  left: 50%;
  z-index: 2;
  max-width: 24%;
  max-height: 16%;
  transform: translate(-50%, -50%);
}

.face-logo-overlay {
  display: grid;
  width: 24%;
  height: 16%;
  place-items: center;
}

.face-logo-overlay > img {
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.face-logo-overlay.helmet-logo-mark {
  overflow: hidden;
  height: auto;
  max-height: none;
  aspect-ratio: 1;
  mix-blend-mode: multiply;
  opacity: .96;
  filter: contrast(1.08) saturate(1.04);
}

.face-logo-overlay.helmet-logo-mark > img {
  position: absolute;
  top: 0;
  left: 50%;
  width: 143%;
  height: 143%;
  max-width: none;
  max-height: none;
  object-fit: contain;
  object-position: center top;
  transform: translateX(-50%);
}

.surface-helmet.face-front .face-logo-overlay {
  top: 68%;
  width: 5.8%;
  max-width: 5.8%;
  max-height: none;
}

.face-thumb-stage.surface-helmet.face-front .face-logo-overlay {
  top: 66%;
  width: 6.4%;
  max-width: 6.4%;
  max-height: none;
}

.face-print-zone {
  position: absolute;
  z-index: 3;
  object-fit: contain;
  transform: translate(-50%, -50%);
}

.face-zone-text {
  overflow: hidden;
  max-width: 34%;
  padding: 3px 6px;
  border-radius: 3px;
  color: #162033;
  background: rgba(255, 255, 255, .78);
  font-size: clamp(7px, .8vw, 11px);
  font-style: normal;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.zone-vest-front-logo {
  top: 36%;
  left: 37%;
  width: 14%;
  max-height: 8%;
}

.face-image-stage .zone-vest-front-logo {
  left: 43%;
}

.zone-vest-front-number {
  top: 39%;
  left: 62%;
}

.face-image-stage .zone-vest-front-number {
  left: 56%;
}

.zone-vest-back-upper {
  top: 34%;
  left: 50%;
}

.zone-vest-back-middle {
  top: 58%;
  left: 50%;
}

.zone-vest-back-lower {
  top: 75%;
  left: 50%;
}

.face-thumb-stage .face-zone-text {
  padding: 1px 2px;
  font-size: 4px;
}

.surface-helmet.face-back .face-text-overlay {
  top: 52%;
  left: 50%;
}

.surface-helmet.face-left .face-text-overlay {
  top: 54%;
  left: 50%;
}

.surface-helmet.face-right .face-text-overlay {
  top: 54%;
  left: 50%;
}

.face-text-overlay {
  padding: 3px 6px;
  border-radius: 4px;
  color: #172033;
  background: rgba(255, 255, 255, .82);
  box-shadow: 0 2px 8px rgba(18, 33, 69, .12);
  font-size: clamp(8px, 1vw, 12px);
  font-style: normal;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.surface-helmet .face-text-overlay,
.surface-vest .face-zone-text {
  padding: 0;
  color: #172033;
  background: transparent;
  box-shadow: none;
  text-shadow:
    -1px -1px 0 rgba(255, 255, 255, .88),
    1px -1px 0 rgba(255, 255, 255, .88),
    -1px 1px 0 rgba(255, 255, 255, .88),
    1px 1px 0 rgba(255, 255, 255, .88);
}

.face-image-missing {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: clamp(300px, 30vw, 460px);
  padding: 24px;
  box-sizing: border-box;
  text-align: center;
  color: #a15c00;
  background: #fff8e6;
}

.face-image-missing span {
  margin-top: 8px;
  color: #9b6b25;
  font-size: 12px;
  line-height: 1.6;
}

.face-main-caption {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px 15px;
  color: #344054;
  font-size: 12px;
  line-height: 1.5;
}

.face-main-caption span {
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

.face-detail-thumbnails {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.embedded .face-detail-thumbnails {
  min-height: 0;
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.face-detail-thumbnails.faces-1 {
  grid-template-columns: 1fr;
}

.face-detail-thumbnails.faces-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.embedded .face-detail-thumbnails.faces-1,
.embedded .face-detail-thumbnails.faces-2 {
  grid-template-rows: minmax(0, 1fr);
}

.face-detail-thumbnails button {
  overflow: hidden;
  min-height: 0;
  padding: 0 0 10px;
  color: #344054;
  cursor: pointer;
  text-align: left;
}

.embedded .face-detail-thumbnails button {
  display: flex;
  flex-direction: column;
}

.face-detail-thumbnails button.active {
  border-color: #315efb;
  box-shadow: 0 0 0 2px rgba(49, 94, 251, .12);
}

.face-detail-thumbnails button.missing {
  border-style: dashed;
  color: #9b6b25;
  background: #fffaf0;
}

.face-thumb-stage {
  width: 100%;
  height: auto;
  aspect-ratio: 4 / 3;
  margin-bottom: 7px;
}

.embedded .face-thumb-stage {
  flex: 1 1 auto;
  min-height: 0;
  aspect-ratio: auto;
}

.face-detail-thumbnails strong,
.face-detail-thumbnails small {
  display: block;
  margin: 0 9px;
  overflow-wrap: anywhere;
}

.face-detail-thumbnails strong {
  font-size: 12px;
}

.face-detail-thumbnails small {
  display: -webkit-box;
  min-height: 27px;
  overflow: hidden;
  margin-top: 2px;
  color: #7b879d;
  font-size: 9px;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.face-thumb-stage .face-text-overlay {
  padding: 2px 3px;
  font-size: 5px;
}

.face-missing-warning {
  margin-top: 12px;
  padding: 9px 12px;
  border-radius: 8px;
  color: #8a5800;
  background: #fff8e6;
  font-size: 11px;
}

@media (max-width: 1100px) {
  .face-detail-viewer:not(.embedded) .face-detail-layout {
    grid-template-columns: 1fr;
  }

  .face-detail-viewer:not(.embedded) .face-detail-thumbnails {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .face-detail-viewer {
    padding: 16px;
  }

  .face-detail-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .face-detail-heading small,
  .face-main-caption span {
    text-align: left;
  }

  .face-detail-thumbnails {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
