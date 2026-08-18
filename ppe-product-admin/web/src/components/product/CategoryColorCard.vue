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
