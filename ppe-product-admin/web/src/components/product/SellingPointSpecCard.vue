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
        <p>维护长图所需的材质、单位、执行标准、产品规格与包装信息</p>
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
        label="执行标准"
        class="span-2"
      >
        <el-input
          v-model="form.execution_standard"
          maxlength="500"
          show-word-limit
          placeholder="例如：GB 2811-2019；必须填写真实来源，不使用默认文案"
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
