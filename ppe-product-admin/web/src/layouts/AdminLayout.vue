<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAppStore } from "../stores/app";
import { useAuthStore } from "../stores/auth";


const route = useRoute();
const router = useRouter();

const appStore = useAppStore();
const authStore = useAuthStore();



const menuItems = [

  {
    path:"/dashboard",
    title:"仪表盘",
    icon:"DataAnalysis"
  },


  {
    path:"/ai-generator",
    title:"AI生成中心",
    icon:"MagicStick"
  },

  {
    path:"/customers",
    title:"客户档案",
    icon:"OfficeBuilding",
    permission:"records.read_all"
  },

  {
    path:"/generation-records",
    title:"作图记录",
    icon:"PictureFilled",
    permission:"records.read_all"
  },

  {
    title:"资源管理",
    path:"/resource",
    icon:"Folder",
    permission:"catalog.manage"
  },


  {
    path:"/product-library",
    title:"产品与案例库",
    icon:"Box"
  },


  {
    path:"/products",
    title:"商品管理",
    icon:"Goods",
    permission:"catalog.manage"
  },

  {
    path:"/accounts",
    title:"账号管理",
    icon:"UserFilled",
    permission:"system.manage"
  }

];

const visibleMenuItems = computed(() => menuItems.filter((item) => (
  !item.permission || authStore.hasPermission(item.permission)
)));

const userRoleLabel = computed(() => (
  authStore.user?.roles?.map((role) => role.name).join(" / ") || "员工"
));

const userInitial = computed(() => authStore.user?.displayName?.slice(0, 1) || "员");



const currentTitle = computed(()=>{

  return route.meta?.title || "PPE Product Admin";

});

const isAIWorkspace = computed(()=>{

  return route.path === "/ai-generator";

});



function navigate(path){

  router.push(path);

  appStore.closeMobileMenu();

}

async function logout(){
  await authStore.logout();
  await router.replace("/login");
}

</script>


<template>

<div class="admin-layout">

<button
v-if="isAIWorkspace"
class="ai-menu-button"
@click="appStore.toggleMobileMenu"
>
☰
</button>


<aside

class="admin-sidebar"

:class="{
collapsed:appStore.sidebarCollapsed,
'mobile-visible':appStore.mobileMenuVisible,
'ai-sidebar':isAIWorkspace
}"

:style="{
width:appStore.sidebarWidth
}"

>


<div class="sidebar-brand">


<div class="brand-logo">
P
</div>


<div
v-show="!appStore.sidebarCollapsed"
class="brand-text"
>

<strong>
PPE AI
</strong>

<span>
VISUAL PLATFORM
</span>


</div>


</div>




<div class="sidebar-scroll">


<div
v-show="!appStore.sidebarCollapsed"
class="menu-group-title"
>
工作台
</div>



<nav class="sidebar-menu">


<button

v-for="item in visibleMenuItems"

:key="item.path"

class="sidebar-menu-item"

:class="{
active:route.path===item.path
}"

@click="navigate(item.path)"

>


<el-icon :size="19">

<component :is="item.icon"/>

</el-icon>


<span
v-show="!appStore.sidebarCollapsed"
class="menu-item-text"
>

{{item.title}}

</span>


</button>


</nav>



<div
v-show="!appStore.sidebarCollapsed"
class="menu-group-title secondary"
>

系统功能

</div>



<nav class="sidebar-menu">


<button
class="sidebar-menu-item disabled"
>


<el-icon :size="19">

<Refresh/>

</el-icon>



<span
v-show="!appStore.sidebarCollapsed"
class="menu-item-text"
>
ERP同步
</span>



<span
v-show="!appStore.sidebarCollapsed"
class="coming-soon"
>
后续
</span>


</button>



<button
class="sidebar-menu-item disabled"
>


<el-icon :size="19">

<Setting/>

</el-icon>



<span
v-show="!appStore.sidebarCollapsed"
class="menu-item-text"
>
系统设置
</span>



<span
v-show="!appStore.sidebarCollapsed"
class="coming-soon"
>
后续
</span>


</button>


</nav>


</div>




<div class="sidebar-footer">


<div class="system-status">


<span class="system-status-dot"></span>


<div
v-show="!appStore.sidebarCollapsed"
class="system-status-text"
>

<strong>
系统运行正常
</strong>


<span>
API PORT 9530
</span>


</div>


</div>


</div>



</aside>





<div
v-if="appStore.mobileMenuVisible"
class="mobile-overlay"
@click="appStore.closeMobileMenu"
></div>





<section

class="admin-main"

:class="{
'ai-fullscreen':isAIWorkspace
}"

:style="{

marginLeft:isAIWorkspace
?'0px'
:appStore.sidebarWidth

}"

>



<header
v-if="!isAIWorkspace"
class="admin-header"
>


<div class="header-left">


<el-button
text
class="sidebar-toggle desktop-toggle"
@click="appStore.toggleSidebar"
>


<el-icon :size="21">


<Fold
v-if="!appStore.sidebarCollapsed"
/>


<Expand v-else/>


</el-icon>


</el-button>




<el-button
text
class="sidebar-toggle mobile-toggle"
@click="appStore.toggleMobileMenu"
>


<el-icon :size="21">

<Menu/>

</el-icon>


</el-button>





<div class="page-title-area">


<h1>
{{currentTitle}}
</h1>


<el-breadcrumb separator="/">

<el-breadcrumb-item>
PPE AI Platform
</el-breadcrumb-item>


<el-breadcrumb-item>
{{currentTitle}}
</el-breadcrumb-item>


</el-breadcrumb>



</div>


</div>






<div class="header-right">


<div class="api-status">

<span class="api-status-dot"></span>

API 服务正常

</div>




<el-divider direction="vertical"/>




<div class="admin-user">


<div class="admin-avatar">
{{userInitial}}
</div>


<div class="admin-user-info">

<strong>
{{authStore.user?.displayName || "员工"}}
</strong>

<span>
{{userRoleLabel}}
</span>


</div>

<el-button text class="iam-logout-button" @click="logout">
退出
</el-button>


</div>


</div>



</header>





<main
class="admin-content"
:class="{
'ai-content':isAIWorkspace
}"
>

<router-view />

</main>



</section>



</div>


</template>
