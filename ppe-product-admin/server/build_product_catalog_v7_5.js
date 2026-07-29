require("dotenv").config();

const mysql=require("mysql2/promise");


const pool=mysql.createPool({

host:process.env.DB_HOST,
user:process.env.DB_USER,
password:process.env.DB_PASSWORD,
database:process.env.DB_NAME,

waitForConnections:true,
connectionLimit:10

});


// =======================
// 穿戴判断
// =======================

function isWearable(cate){

    return cate &&
    cate.startsWith("个人防护");

}



function parseCategory(full){

    const arr=(full||"").split("/");

    return {

        level1:arr[0]||"",
        level2:arr[1]||"",
        level3:arr[2]||""

    };

}


// =======================
// 颜色
// =======================

const COLOR_MAP=[

["荧光黄","荧光黄色"],
["荧光绿","荧光绿色"],

["黄色","黄色"],
["黄","黄色"],

["蓝色","蓝色"],
["蓝","蓝色"],

["湖蓝","湖蓝色"],
["咖啡","咖啡色"],

["红色","红色"],
["红","红色"],

["绿色","绿色"],
["绿","绿色"],

["橙色","橙色"],
["橙","橙色"],
["桔","橙色"],

["黑色","黑色"],
["黑","黑色"],

["白色","白色"],
["白","白色"],

["灰色","灰色"],
["灰","灰色"],

["粉色","粉色"],
["紫色","紫色"],

["咖啡","咖啡色"]

];



function extractColors(name){

let set=new Set();


COLOR_MAP.forEach(c=>{

    if(name.includes(c[0])){

        set.add(c[1]);

    }

});


return [...set];

}



// =======================
// 型号提取
// =======================

function extractModels(name){

let models=[];


// 300D

let a=name.match(/\d+D/gi);

if(a)
models.push(...a);


// B30

let b=name.match(/\b[A-Z]{1,2}\d+\b/g);

if(b)
models.push(...b);


// H-1828

let c=name.match(/\b[A-Z]+-\d+\b/g);

if(c)
models.push(...c);



return [...new Set(models)];

}



// =======================
// 商品名清洗
// =======================

function cleanName(name){


let models=extractModels(name);


let n=name;


// 删除型号

models.forEach(m=>{

n=n.replace(
m,
""
);

});


// 删除括号

n=n.replace(
/\([^)]*\)/g,
""
);


// 删除颜色

COLOR_MAP.forEach(c=>{

n=n.replace(
new RegExp(c[0],"g"),
""
);

});


// 删除尺码

n=n.replace(
/(XXXL|XXL|XL|XS|3XL|2XL|L|M|S)码?/gi,
""
);


// 删除厘米

n=n.replace(
/\d+(cm|CM|c)/g,
""
);


// 删除包装

n=n.replace(
/\d+(个|只|双|件|套|包|盒|米)装?/g,
""
);


// 删除备注

[
"颜色备注",
"颜色可选",
"下单备注颜色",
"下单备注颜色和尺码",
"备注颜色",
"和尺码",
"左单只",
"右单只",
"个装"
]
.forEach(w=>{

n=n.replace(
new RegExp(w,"g"),
""
);

});


// 删除尾部SKU

n=n.replace(
/[-_ ]\d+码/g,
""
);


n=n.replace(
/[-_ ]\d+$/,
""
);



n=n
.replace(/[-_/]+$/g,"")
.trim();



// 恢复型号

if(models.length){

n=models.join(" ")+n;

}


return n;

}



// =======================
// MAIN
// =======================


async function main(){


const conn=await pool.getConnection();


try{


console.log(
"开始商品聚合 V7"
);



await conn.query(
"SET FOREIGN_KEY_CHECKS=0"
);


await conn.query(
"DELETE FROM product_files"
);


await conn.query(
"TRUNCATE TABLE product_catalog"
);


await conn.query(
"SET FOREIGN_KEY_CHECKS=1"
);



const [rows]=await conn.query(`

SELECT *

FROM ppe_product_source

WHERE

is_delete=0

AND

is_stop_selling=0

`);




console.log(
"有效商品:",
rows.length
);



const map=new Map();


let wearable=0;



for(const row of rows){


if(!isWearable(row.cate_full_name))
continue;


wearable++;


const cate=parseCategory(
row.cate_full_name
);


const name=cleanName(
row.goods_name
);



const key=
name+
"|"+
cate.level3;



if(!map.has(key)){


map.set(key,{

goods_id:row.goods_id,

goods_no:row.goods_no,

product_name:name,

category_level_1:cate.level1,

category_level_2:cate.level2,

category_level_3:cate.level3,

cate_full_name:row.cate_full_name,

brand_name:row.brand_name,

colors:new Set(),

source_count:0

});


}



let p=map.get(key);



extractColors(row.goods_name)
.forEach(c=>
p.colors.add(c)
);



p.source_count++;


}



console.log(
"穿戴商品:",
wearable
);


console.log(
"聚合商品:",
map.size
);



for(const p of map.values()){


let colors=[...p.colors];


await conn.execute(`

INSERT INTO product_catalog

(

goods_id,
goods_no,

product_name,

category_level_1,
category_level_2,
category_level_3,

cate_full_name,

brand_name,

colors,

color_count,

source_count

)

VALUES

(?,?,?,?,?,?,?,?,?,?,?)

`,

[

p.goods_id,
p.goods_no,

p.product_name,

p.category_level_1,
p.category_level_2,
p.category_level_3,

p.cate_full_name,

p.brand_name,

JSON.stringify(colors),

colors.length,

p.source_count

]

);


}


console.log(
"V7完成"
);


}
catch(e){

console.error(e);

}
finally{

conn.release();

process.exit();

}


}


main();
