require("dotenv").config();

const mysql = require("mysql2/promise");


// ===============================
// DB
// ===============================

const pool = mysql.createPool({

    host: process.env.DB_HOST,

    user: process.env.DB_USER,

    password: process.env.DB_PASSWORD,

    database: process.env.DB_NAME,

    waitForConnections:true,

    connectionLimit:10

});



// ===============================
// 穿戴类判断
// ===============================

function isWearable(cate){

    return cate &&
           cate.startsWith("个人防护");

}



// ===============================
// 分类解析
// ===============================

function parseCategory(full){

    if(!full){

        return {
            level1:"",
            level2:"",
            level3:""
        };

    }


    const arr=full.split("/");


    return {

        level1:arr[0]||"",

        level2:arr[1]||"",

        level3:arr[2]||""

    };

}



// ===============================
// 颜色规则
// ===============================

const COLOR_RULES=[

    {
        keys:["荧光黄"],
        value:"荧光黄色"
    },

    {
        keys:["荧光绿"],
        value:"荧光绿色"
    },

    {
        keys:["黄色","黄"],
        value:"黄色"
    },

    {
        keys:["蓝色","蓝"],
        value:"蓝色"
    },

    {
        keys:["红色","红"],
        value:"红色"
    },

    {
        keys:["绿色","绿"],
        value:"绿色"
    },

    {
        keys:["桔","橙色","橙"],
        value:"橙色"
    },

    {
        keys:["黑色","黑"],
        value:"黑色"
    },

    {
        keys:["白色","白"],
        value:"白色"
    },

    {
        keys:["灰色","灰"],
        value:"灰色"
    },

    {
        keys:["粉色","粉"],
        value:"粉色"
    },

    {
        keys:["紫色","紫"],
        value:"紫色"
    },

    {
        keys:["藏蓝"],
        value:"藏蓝色"
    }

];



function extractColors(text){


    let colors=new Set();


    COLOR_RULES.forEach(rule=>{


        rule.keys.forEach(k=>{


            if(text.includes(k)){

                colors.add(rule.value);

            }


        });


    });


    return [...colors];

}



// ===============================
// 商品名清洗
// ===============================

function cleanName(name){


    if(!name)
        return "";



    let result=name;



    // 删除颜色

    COLOR_RULES.forEach(rule=>{

        rule.keys.forEach(k=>{

            result=result.replace(
                new RegExp(k,"g"),
                ""
            );

        });

    });



    // 删除尺码

    result=result.replace(
        /(XS|S|M|L|XL|XXL|XXXL)/gi,
        ""
    );



    result=result.replace(
        /\d{2,3}码/g,
        ""
    );



    // 删除包装数量

    result=result.replace(
        /\d+(个|只|双|件|套|包|盒|瓶|卷|米)装?/g,
        ""
    );



    // 删除括号规格

    result=result.replace(
        /\([^)]*\)/g,
        ""
    );



    // 删除常见变量

    const removes=[

        "升级款",
        "加厚款",
        "普通款",
        "基础款",
        "颜色可选",
        "下单备注颜色"

    ];



    removes.forEach(word=>{

        result=result.replace(
            new RegExp(word,"g"),
            ""
        );

    });



    result=result
    .replace(/[-_/]+$/g,"")
    .replace(/\s+/g," ")
    .trim();



    return result;

}



// ===============================
// 写分类
// ===============================

async function saveCategory(conn,cate){


    if(!cate.level2)
        return;


    const full=[

        cate.level1,

        cate.level2,

        cate.level3

    ]
    .filter(Boolean)
    .join("/");



    await conn.execute(

`
INSERT INTO product_category
(
category_name,
full_name,
level
)

VALUES(?,?,?)

`,

[

cate.level3||cate.level2,

full,

cate.level3?3:2

]

);


}



// ===============================
// MAIN
// ===============================

async function main(){


    const conn=await pool.getConnection();


    try{


        console.log(
            "开始商品聚合 V2"
        );



        await conn.query(
            "SET FOREIGN_KEY_CHECKS=0"
        );


        await conn.query(
            "TRUNCATE TABLE product_files"
        );


        await conn.query(
            "TRUNCATE TABLE product_catalog"
        );


        await conn.query(
            "TRUNCATE TABLE product_category"
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
            "有效数据:",
            rows.length
        );



        const products=new Map();



        let wearable=0;



        for(const row of rows){



            if(!isWearable(row.cate_full_name)){

                continue;

            }


            wearable++;



            const cate=parseCategory(
                row.cate_full_name
            );



            await saveCategory(
                conn,
                cate
            );



            if(!products.has(row.goods_id)){


                products.set(

                    row.goods_id,

                    {

                        goods_id:row.goods_id,

                        goods_no:row.goods_no,


                        product_name:
                        cleanName(
                            row.goods_name
                        ),


                        category_level_1:
                        cate.level1,


                        category_level_2:
                        cate.level2,


                        category_level_3:
                        cate.level3,


                        cate_full_name:
                        row.cate_full_name,


                        brand_name:
                        row.brand_name,


                        colors:new Set(),


                        source_count:1

                    }

                );


            }


            const p=products.get(row.goods_id);



            extractColors(
                row.goods_name
            )
            .forEach(c=>
                p.colors.add(c)
            );



            p.source_count++;


        }



        console.log(
            "穿戴数据:",
            wearable
        );


        console.log(
            "聚合商品:",
            products.size
        );



        for(const p of products.values()){


            const colors=[
                ...p.colors
            ];



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

p.source_count-1

]

);


        }



        console.log(
            "商品聚合完成"
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
