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
