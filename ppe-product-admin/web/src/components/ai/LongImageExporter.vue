<script setup>
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import {
  FACE_LABELS,
  chunkShowcaseProducts,
  facePrintInstruction,
  facesForSurface,
  longImageHeight,
  safeExportName
} from "../../utils/showcase";

const props = defineProps({
  embedded: { type: Boolean, default: false },
  products: { type: Array, default: () => [] },
  brandLogo: { type: String, default: "" },
  headline: { type: String, default: "全身安全防护方案" },
  sceneName: { type: String, default: "" },
  batchId: { type: String, default: "" }
});

const rendering = ref(false);
const pages = ref([]);
const activePageIndex = ref(0);
const pageGroups = computed(() => chunkShowcaseProducts(props.products));
const activePage = computed(() => pages.value[activePageIndex.value] || "");
const activePageGroup = computed(() => pageGroups.value[activePageIndex.value] || []);
watch(
  () => [props.products, props.brandLogo, props.headline, props.sceneName, props.batchId],
  () => {
    pages.value = [];
    activePageIndex.value = 0;
  },
  { deep: true }
);

function roundedRect(context, x, y, width, height, radius = 20) {
  const r = Math.min(radius, width / 2, height / 2);
  context.beginPath();
  context.roundRect(x, y, width, height, r);
}

function drawContain(context, image, x, y, width, height) {
  const scale = Math.min(width / image.naturalWidth, height / image.naturalHeight);
  const targetWidth = image.naturalWidth * scale;
  const targetHeight = image.naturalHeight * scale;
  context.drawImage(
    image,
    x + (width - targetWidth) / 2,
    y + (height - targetHeight) / 2,
    targetWidth,
    targetHeight
  );
}

function wrapLines(context, text, maxWidth, maxLines = 2) {
  const characters = Array.from(String(text || ""));
  const lines = [];
  let current = "";
  for (const character of characters) {
    const candidate = current + character;
    if (context.measureText(candidate).width > maxWidth && current) {
      lines.push(current);
      current = character;
      if (lines.length === maxLines) break;
    } else {
      current = candidate;
    }
  }
  if (lines.length < maxLines && current) lines.push(current);
  if (lines.join("").length < characters.length && lines.length) {
    lines[lines.length - 1] = `${lines[lines.length - 1].slice(0, -1)}…`;
  }
  return lines;
}

function drawField(context, label, value, x, y, width, { danger = false, maxLines = 1 } = {}) {
  context.fillStyle = danger ? "#b42318" : "#667085";
  context.font = "600 20px 'Microsoft YaHei', sans-serif";
  context.fillText(`${label}：`, x, y);
  const labelWidth = context.measureText(`${label}：`).width;
  context.fillStyle = danger ? "#b42318" : "#25324a";
  context.font = "20px 'Microsoft YaHei', sans-serif";
  const lines = wrapLines(context, value || "资料缺失", width - labelWidth, maxLines);
  lines.forEach((line, index) => context.fillText(line, x + (index ? 0 : labelWidth), y + index * 27));
  return Math.max(27, lines.length * 27);
}

function loadImage(source, cache) {
  const url = String(source || "").trim();
  if (!url) return Promise.resolve(null);
  if (cache.has(url)) return cache.get(url);
  const promise = fetch(url, { credentials: "include" })
    .then((response) => {
      if (!response.ok) throw new Error(`图片读取失败 HTTP ${response.status}`);
      return response.blob();
    })
    .then((blob) => new Promise((resolve, reject) => {
      const objectUrl = URL.createObjectURL(blob);
      const image = new Image();
      image.onload = () => {
        URL.revokeObjectURL(objectUrl);
        resolve(image);
      };
      image.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        reject(new Error("图片解码失败"));
      };
      image.src = objectUrl;
    }))
    .catch(() => null);
  cache.set(url, promise);
  return promise;
}

function drawHelmetMark(context, image, x, y, width, height) {
  const sourceX = image.naturalWidth * .15;
  const sourceY = 0;
  const sourceWidth = image.naturalWidth * .70;
  const sourceHeight = Math.min(image.naturalHeight, image.naturalWidth * .70);
  const scale = Math.min(width / sourceWidth, height / sourceHeight);
  const drawWidth = sourceWidth * scale;
  const drawHeight = sourceHeight * scale;
  context.save();
  context.globalAlpha = .96;
  context.globalCompositeOperation = "multiply";
  context.drawImage(
    image,
    sourceX,
    sourceY,
    sourceWidth,
    sourceHeight,
    x + (width - drawWidth) / 2,
    y + (height - drawHeight) / 2,
    drawWidth,
    drawHeight
  );
  context.restore();
}

async function drawFace(context, view, x, y, width, height, cache) {
  context.fillStyle = "#f3f6fb";
  roundedRect(context, x, y, width, height, 12);
  context.fill();
  const image = await loadImage(view?.image, cache);
  if (image) {
    context.save();
    roundedRect(context, x, y, width, height - 24, 12);
    context.clip();
    drawContain(context, image, x + 6, y + 6, width - 12, height - 30);
    context.restore();
  }
  else {
    context.fillStyle = "#a15c00";
    context.font = "600 18px 'Microsoft YaHei', sans-serif";
    context.textAlign = "center";
    context.fillText("底图缺失", x + width / 2, y + height / 2);
    context.textAlign = "left";
  }

  const zones = Array.isArray(view?.printZones)
    ? view.printZones.filter(zone => zone.face === view.id)
    : [];
  const zonePositions = {
    "vest-front-logo": [.37, .36, .14, .08],
    "vest-front-number": [.62, .39, .26, .10],
    "vest-back-upper": [.50, .34, .34, .10],
    "vest-back-middle": [.50, .58, .34, .10],
    "vest-back-lower": [.50, .75, .34, .10]
  };
  if (image && zones.length) {
    for (const zone of zones) {
      const [cx, cy, zoneWidth, zoneHeight] = zonePositions[zone.id] || [.5, .45, .3, .12];
      const logo = await loadImage(zone?.logo?.image, cache);
      if (zone.type === "logo" && logo) {
        const logoScale = Math.min(1.2, Math.max(.6, (Number(zone.logoScale) || 100) / 100));
        drawContain(
          context,
          logo,
          x + width * (cx - zoneWidth * logoScale / 2),
          y + height * (cy - zoneHeight * logoScale / 2),
          width * zoneWidth * logoScale,
          height * zoneHeight * logoScale
        );
      } else if (zone.type === "text" && zone.text) {
        context.fillStyle = "#172033";
        context.font = "700 9px 'Microsoft YaHei', sans-serif";
        context.textAlign = "center";
        context.strokeStyle = "rgba(255,255,255,.92)";
        context.lineWidth = 3;
        context.lineJoin = "round";
        context.strokeText(String(zone.text).slice(0, 14), x + width * cx, y + height * cy + 4);
        context.fillText(String(zone.text).slice(0, 14), x + width * cx, y + height * cy + 4);
        context.textAlign = "left";
      }
    }
  } else {
    const logo = await loadImage(view?.logo?.image, cache);
    const logoScale = Math.min(1.2, Math.max(.6, (Number(view?.logoScale) || 100) / 100));
    if (image && logo && view?.surface === "helmet") {
      drawHelmetMark(
        context,
        logo,
        x + width * (.5 - .05 * logoScale),
        y + height * (.615 - .05 * logoScale),
        width * .10 * logoScale,
        height * .10 * logoScale
      );
    } else if (image && logo) {
      drawContain(
        context,
        logo,
        x + width * (.5 - .12 * logoScale),
        y + height * (.44 - .09 * logoScale),
        width * .24 * logoScale,
        height * .18 * logoScale
      );
    }
    else if (image && view?.printText) {
      const textPositions = {
        "helmet:back": [.50, .52],
        "helmet:left": [.50, .54],
        "helmet:right": [.50, .54]
      };
      const [textX, textY] = textPositions[`${view.surface}:${view.id}`] || [.50, .47];
      context.fillStyle = "#172033";
      context.font = "700 11px 'Microsoft YaHei', sans-serif";
      context.textAlign = "center";
      context.strokeStyle = "rgba(255,255,255,.92)";
      context.lineWidth = 3;
      context.lineJoin = "round";
      context.strokeText(String(view.printText).slice(0, 12), x + width * textX, y + height * textY);
      context.fillText(String(view.printText).slice(0, 12), x + width * textX, y + height * textY);
      context.textAlign = "left";
    }
  }
  context.fillStyle = "rgba(11,23,54,.82)";
  context.fillRect(x, y + height - 24, width, 24);
  context.fillStyle = "#fff";
  context.font = "600 13px 'Microsoft YaHei', sans-serif";
  context.textAlign = "center";
  context.fillText(FACE_LABELS[view?.id] || "未知面", x + width / 2, y + height - 7);
  context.textAlign = "left";
}

async function drawProductCard(context, product, y, index, cache) {
  const x = 40;
  const width = 1000;
  const height = 360;
  context.fillStyle = "#fff";
  context.strokeStyle = "#e2e8f2";
  context.lineWidth = 2;
  roundedRect(context, x, y, width, height, 22);
  context.fill();
  context.stroke();

  context.fillStyle = "#315efb";
  roundedRect(context, x + 20, y + 18, 42, 42, 12);
  context.fill();
  context.fillStyle = "#fff";
  context.font = "700 21px 'Microsoft YaHei', sans-serif";
  context.textAlign = "center";
  context.fillText(String(index + 1).padStart(2, "0"), x + 41, y + 47);
  context.textAlign = "left";

  context.fillStyle = "#15213c";
  context.font = "700 30px 'Microsoft YaHei', sans-serif";
  context.fillText(product.productName, x + 76, y + 48);
  context.fillStyle = "#8490a5";
  context.font = "18px 'Microsoft YaHei', sans-serif";
  context.fillText(product.goodsNo || "产品编号缺失", x + 76, y + 78);

  const productFaces = facesForSurface(product.surface);
  const mediaX = x + 22;
  const mediaY = y + 96;
  const mediaWidth = 278;
  const mediaHeight = 238;
  const gap = 10;
  for (let faceIndex = 0; faceIndex < productFaces.length; faceIndex += 1) {
    const faceId = productFaces[faceIndex];
    const view = product.views.find(item => item.id === faceId) || { id: faceId };
    const singleFace = productFaces.length === 1;
    const twoFaces = productFaces.length === 2;
    const faceWidth = singleFace ? mediaWidth : (mediaWidth - gap) / 2;
    const faceHeight = singleFace || twoFaces ? mediaHeight : (mediaHeight - gap) / 2;
    const column = singleFace ? 0 : faceIndex % 2;
    const row = singleFace || twoFaces ? 0 : Math.floor(faceIndex / 2);
    await drawFace(
      context,
      view,
      mediaX + column * (faceWidth + gap),
      mediaY + row * (faceHeight + gap),
      faceWidth,
      faceHeight,
      cache
    );
  }

  const infoX = x + 330;
  let infoY = y + 112;
  infoY += drawField(context, "方案类型", {
    vest: "反光马甲穿戴与印刷",
    helmet: "安全帽穿戴与印刷",
    gloves: "防护手套穿戴"
  }[product.surface] || "PPE 产品方案", infoX, infoY, 685);
  if (product.colors.length) {
    infoY += drawField(context, "产品颜色", product.colors.join("、"), infoX, infoY, 685);
  }

  const printText = productFaces.map((face) => {
    const view = product.views.find(item => item.id === face);
    return `${FACE_LABELS[face]} ${facePrintInstruction(view)}`;
  }).join(" ｜ ");
  drawField(context, "印刷内容", printText, infoX, infoY, 685, { maxLines: 3 });
  context.fillStyle = "#edf3ff";
  roundedRect(context, x + 310, y + height - 54, 665, 34, 8);
  context.fill();
  context.fillStyle = "#315efb";
  context.font = "700 16px 'Microsoft YaHei', sans-serif";
  context.fillText("PPE 产品与印刷方案 · 自动排版输出", x + 344, y + height - 31);
}

async function renderPage(group, pageIndex, pageCount) {
  const canvas = document.createElement("canvas");
  canvas.width = 1080;
  canvas.height = longImageHeight(group.length);
  const context = canvas.getContext("2d");
  const cache = new Map();

  context.fillStyle = "#f4f7fb";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#0b1736";
  context.fillRect(0, 0, 1080, 170);
  context.fillStyle = "#7ea3ff";
  context.font = "700 18px 'Microsoft YaHei', sans-serif";
  context.fillText("SHOUDUN PPE VISUAL SOLUTION", 40, 50);
  context.fillStyle = "#fff";
  context.font = "700 38px 'Microsoft YaHei', sans-serif";
  context.fillText(props.headline || "全身安全防护方案", 40, 102);
  context.fillStyle = "rgba(255,255,255,.68)";
  context.font = "19px 'Microsoft YaHei', sans-serif";
  context.fillText(`行业场景：${props.sceneName || "资料缺失"}  ·  第 ${pageIndex + 1}/${pageCount} 张`, 40, 140);
  const brandLogo = await loadImage(props.brandLogo, cache);
  if (brandLogo) drawContain(context, brandLogo, 875, 28, 150, 112);

  for (let index = 0; index < group.length; index += 1) {
    await drawProductCard(context, group[index], 200 + index * 390, pageIndex * 6 + index, cache);
  }

  const footerY = canvas.height - 78;
  context.fillStyle = "#0b1736";
  context.fillRect(0, footerY, 1080, 78);
  context.fillStyle = "rgba(255,255,255,.72)";
  context.font = "17px 'Microsoft YaHei', sans-serif";
  context.fillText(`批次：${props.batchId || "未生成批次"}`, 40, footerY + 47);
  context.textAlign = "right";
  context.fillText("首盾全身安全防护", 1040, footerY + 47);
  context.textAlign = "left";
  return canvas.toDataURL("image/png");
}

async function generatePages() {
  if (!props.products.length) {
    ElMessage.warning("请先把至少一个产品加入长图清单");
    return;
  }
  rendering.value = true;
  try {
    const output = [];
    for (let index = 0; index < pageGroups.value.length; index += 1) {
      output.push(await renderPage(pageGroups.value[index], index, pageGroups.value.length));
    }
    pages.value = output;
    activePageIndex.value = 0;
    ElMessage.success(`已生成 ${output.length} 张 1080px PNG 长图预览`);
  } catch (error) {
    ElMessage.error(error?.message || "长图渲染失败");
  } finally {
    rendering.value = false;
  }
}

function downloadPage(page, index) {
  const link = document.createElement("a");
  link.href = page;
  link.download = `${safeExportName(props.sceneName)}-${String(index + 1).padStart(2, "0")}.png`;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function downloadAll() {
  pages.value.forEach(downloadPage);
}

function showPreviousPage() {
  activePageIndex.value = Math.max(0, activePageIndex.value - 1);
}

function showNextPage() {
  activePageIndex.value = Math.min(pages.value.length - 1, activePageIndex.value + 1);
}
</script>

<template>
  <section class="long-image-exporter" :class="{ embedded }">
    <header class="long-image-heading">
      <div>
        <span>1080PX LONG IMAGE</span>
        <h3>多产品方案长图</h3>
        <p>每张最多6个产品；超过后按选择顺序拆分，PNG高度随产品数量变化。</p>
      </div>
      <div class="long-image-actions">
        <button type="button" :disabled="rendering || !products.length" @click="generatePages">
          {{ rendering ? "正在渲染…" : "生成长图预览" }}
        </button>
        <button v-if="pages.length" type="button" class="secondary" @click="downloadAll">
          下载全部 {{ pages.length }} 张
        </button>
      </div>
    </header>


    <div v-if="pages.length" class="long-image-previews">
      <article>
        <div>
          <strong>第 {{ activePageIndex + 1 }} / {{ pages.length }} 张</strong>
          <span>{{ activePageGroup.length }} 个产品 · 1080 × {{ longImageHeight(activePageGroup.length) }} px</span>
          <div class="long-image-page-actions">
            <button type="button" :disabled="activePageIndex === 0" @click="showPreviousPage">上一张</button>
            <button type="button" :disabled="activePageIndex >= pages.length - 1" @click="showNextPage">下一张</button>
            <button type="button" @click="downloadPage(activePage, activePageIndex)">下载本张</button>
          </div>
        </div>
        <img :src="activePage" :alt="`方案长图第${activePageIndex + 1}张`" />
      </article>
    </div>
    <div v-else class="long-image-empty">
      <span>加入产品后可直接生成无人物方案长图</span>
    </div>
  </section>
</template>

<style scoped>
.long-image-exporter {
  margin-top: 18px;
  padding: 22px;
  border: 1px solid #e4e9f2;
  border-radius: 18px;
  background: #fff;
}

.long-image-exporter.embedded {
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

.long-image-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
}

.embedded .long-image-heading {
  flex: 0 0 auto;
}

.long-image-heading span {
  color: #315efb;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .14em;
}

.long-image-heading h3 {
  margin: 5px 0;
  color: #18243f;
  font-size: 19px;
}

.long-image-heading p {
  margin: 0;
  color: #7b879d;
  font-size: 12px;
}

.long-image-actions {
  display: flex;
  gap: 8px;
}

.long-image-actions button,
.long-image-previews button {
  padding: 9px 14px;
  border: 1px solid #315efb;
  border-radius: 9px;
  color: #fff;
  background: #315efb;
  cursor: pointer;
}

.long-image-actions button.secondary,
.long-image-previews button {
  color: #315efb;
  background: #fff;
}

.long-image-actions button:disabled {
  border-color: #cbd3e2;
  color: #8a95a8;
  background: #e8ecf3;
  cursor: not-allowed;
}

.long-image-page-actions button:disabled {
  border-color: #d5dbe6;
  color: #98a2b3;
  background: #edf0f5;
  cursor: not-allowed;
}

.long-image-boundary-warning,
.long-image-missing-list {
  margin-top: 14px;
  padding: 11px 13px;
  border: 1px solid #f2d59b;
  border-radius: 9px;
  color: #805200;
  background: #fff8e6;
  font-size: 11px;
  line-height: 1.6;
}

.long-image-missing-list {
  display: flex;
  flex-direction: column;
  border-color: #f3c7c2;
  color: #9b2c22;
  background: #fff5f4;
}

.long-image-previews {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-top: 18px;
}

.embedded .long-image-previews {
  display: block;
  flex: 1 1 auto;
  min-height: 0;
  margin-top: 12px;
}

.long-image-previews article {
  overflow: hidden;
  border: 1px solid #e4e9f2;
  border-radius: 12px;
  background: #f8faff;
}

.embedded .long-image-previews article {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
}

.long-image-previews article > div {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 3px 10px;
  align-items: center;
  padding: 10px 12px;
}

.long-image-page-actions {
  display: flex;
  grid-row: 1 / span 2;
  grid-column: 2;
  gap: 6px;
}

.long-image-previews article span {
  color: #7b879d;
  font-size: 10px;
}

.long-image-previews button {
  padding: 6px 9px;
  font-size: 11px;
}

.long-image-previews img {
  display: block;
  width: 100%;
  max-height: 620px;
  object-fit: contain;
  object-position: top;
  background: #dfe5ef;
}

.embedded .long-image-previews img {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
}

.long-image-empty {
  display: grid;
  place-items: center;
  min-height: 110px;
  margin-top: 15px;
  border: 1px dashed #d9e0eb;
  border-radius: 11px;
  color: #8a95a8;
  background: #f8faff;
  font-size: 12px;
}

.embedded .long-image-empty {
  flex: 1 1 auto;
  min-height: 0;
}

@media (max-width: 760px) {
  .long-image-heading,
  .long-image-actions {
    align-items: flex-start;
    flex-direction: column;
  }


  .long-image-page-actions {
    grid-row: auto;
    grid-column: 1 / -1;
    flex-wrap: wrap;
  }
}
</style>
