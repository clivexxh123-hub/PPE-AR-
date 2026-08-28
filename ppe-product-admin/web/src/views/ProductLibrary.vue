<template>
  <div class="product-page">

    <!-- 顶部 -->
    <div class="page-header">

      <div>
        <h1>产品库</h1>
        <p>管理企业 PPE 产品数字资产</p>
      </div>


      <button class="primary-btn">
        ＋ 新增产品
      </button>

    </div>


    <!-- 搜索区域 -->

    <div class="filter-box">

      <input
        placeholder="搜索产品名称 / SKU"
      />


      <button>
        全部分类
      </button>


      <button>
        全部品牌
      </button>


    </div>



    <!-- 分类统计 -->

    <div class="category-panel">


      <div>
        <span>安全帽</span>
        <strong>320</strong>
      </div>


      <div>
        <span>护目镜</span>
        <strong>120</strong>
      </div>


      <div>
        <span>防护手套</span>
        <strong>86</strong>
      </div>


      <div>
        <span>防护服</span>
        <strong>54</strong>
      </div>


    </div>



    <!-- 产品列表 -->


    <div class="products">


      <div
        class="card"
        v-for="item in products"
        :key="item.id"
      >


        <div class="image-box">

          <img :src="item.image">

        </div>


        <div class="info">


          <h3>
            {{item.name}}
          </h3>


          <p>
            SKU:
            {{item.sku}}
          </p>


          <div class="tags">

            <span>
              {{item.category}}
            </span>


            <span>
              AI素材 {{item.assets}}
            </span>


          </div>


          <button class="view">
            查看详情
          </button>


        </div>



      </div>


    </div>



  </div>
</template>



<script setup>


const products=[

{
id:1,
name:"V型安全帽",
sku:"SM-HELMET-V01",
category:"安全帽",
assets:24,
image:"https://images.unsplash.com/photo-1504307651254-35680f356dfd"
},


{
id:2,
name:"工业防护眼镜",
sku:"SM-EYE-002",
category:"护目镜",
assets:12,
image:"https://images.unsplash.com/photo-1581092921461-eab62e97a780"
},


{
id:3,
name:"防割手套",
sku:"SM-GLOVE-003",
category:"手套",
assets:8,
image:"https://images.unsplash.com/photo-1586864387967-d02ef85d25b4"
}


]


</script>



<style scoped>


.product-page{

padding:32px;

background:#f7f9fc;

min-height:100%;

}



/* header */

.page-header{

display:flex;

justify-content:space-between;

align-items:center;

}


.page-header h1{

font-size:26px;

margin:0;

}


.page-header p{

color:#64748b;

}



.primary-btn{

background:#3848ff;

color:white;

border:0;

padding:12px 24px;

border-radius:10px;

}



/* filter */


.filter-box{

margin-top:25px;

background:white;

padding:20px;

border-radius:14px;

display:flex;

gap:15px;

}


.filter-box input{

width:320px;

padding:12px;

border:1px solid #ddd;

border-radius:8px;

}


/* category */


.category-panel{

display:grid;

grid-template-columns:repeat(4,1fr);

gap:20px;

margin:25px 0;

}


.category-panel div{

background:white;

padding:20px;

border-radius:14px;

display:flex;

justify-content:space-between;

}



/* products */


.products{

display:grid;

grid-template-columns:repeat(3,1fr);

gap:22px;

}



.card{

background:white;

border-radius:18px;

overflow:hidden;

}


.image-box{

height:220px;

background:#eef2ff;

}


.image-box img{

width:100%;

height:100%;

object-fit:cover;

}


.info{

padding:20px;

}


.info h3{

margin:0 0 10px;

}


.info p{

color:#64748b;

}


.tags span{

background:#eef2ff;

padding:5px 10px;

border-radius:20px;

font-size:12px;

margin-right:8px;

}


.view{

margin-top:18px;

width:100%;

height:38px;

border-radius:8px;

border:1px solid #3155ff;

background:white;

color:#3155ff;

}



</style>