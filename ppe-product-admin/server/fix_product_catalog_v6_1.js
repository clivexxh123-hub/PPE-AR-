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


// ======================
// 型号保护
// ======================

function extractModels(name){

    let models=[];


    let rules=[

        /\d+D/gi,
        /[A-Z]{1,3}\d+/g,
        /[A-Z]+-\d+/g

    ];


    rules.forEach(r=>{

        let m=name.match(r);

        if(m){

            models.push(...m);

        }

    });


    return [...new Set(models)];

}



// ======================
// 名称修复
// ======================

function fixName(name){


    if(!name)
        return "";


    let models=extractModels(name);


    let n=name;



    // 删除错误残留

    n=n.replace(
        /__MODEL_\d+__/g,
        ""
    );



    // 删除颜色

    [

        "荧光黄色",
        "荧光绿色",
        "黄色",
        "黄",
        "蓝色",
        "蓝",
        "湖蓝",
        "红色",
        "红",
        "绿色",
        "绿",
        "橙色",
        "橙",
        "黑色",
        "黑",
        "白色",
        "白",
        "灰色",
        "灰",
        "粉色",
        "粉",
        "紫色",
        "紫",
        "咖啡色",
        "咖啡"

    ].forEach(c=>{

        n=n.replace(
            new RegExp(c,"g"),
            ""
        );

    });



    // 删除规格

    n=n.replace(
        /(XXXL|XXL|XL|XS|L|M|S)码?/gi,
        ""
    );


    // 删除cm

    n=n.replace(
        /\d+(cm|CM|c)/g,
        ""
    );


    // 删除尾部SKU

    n=n.replace(
        /[-\s]+\d+$/,
        ""
    );



    // 删除备注

    [

        "颜色备注",
        "颜色可选",
        "备注颜色",
        "备注尺码",
        "下单备注颜色",
        "下单备注颜色和尺码",
        "个装",
        "单只"

    ].forEach(w=>{

        n=n.replace(
            new RegExp(w,"g"),
            ""
        );

    });



    n=n
    .replace(/[-_/]+$/g,"")
    .replace(/\s+/g," ")
    .trim();



    // 恢复型号

    if(models.length){

        n=models.join(" ")+n;

    }



    return n;

}



// ======================
// 主程序
// ======================


async function main(){


const conn=await pool.getConnection();


try{


console.log(
"开始修复商品目录"
);



const [rows]=await conn.query(

`
SELECT *
FROM product_catalog
`

);



console.log(
"当前商品:",
rows.length
);



const map=new Map();



for(const row of rows){


    const name=fixName(
        row.product_name
    );


    const key=
    name+
    "|"+
    row.category_level_3;



    if(!map.has(key)){


        map.set(key,{

            ...row,

            product_name:name,

            colors:new Set(),

            source_count:0

        });


    }



    const p=map.get(key);



    try{

        let colors=
        JSON.parse(row.colors||"[]");


        colors.forEach(c=>
            p.colors.add(c)
        );


    }
    catch(e){}



    p.source_count+=
    Number(row.source_count||1);



}



console.log(
"重新聚合:",
map.size
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



for(const p of map.values()){


await conn.execute(

`

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

`

,

[

p.goods_id,

p.goods_no,

p.product_name,

p.category_level_1,

p.category_level_2,

p.category_level_3,

p.cate_full_name,

p.brand_name,

JSON.stringify(
[...p.colors]
),

[...p.colors].length,

p.source_count

]

);


}



console.log(
"修复完成"
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

