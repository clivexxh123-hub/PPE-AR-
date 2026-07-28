require("dotenv").config();

const mysql = require("mysql2/promise");


// ===============================
// DATABASE
// ===============================

const pool = mysql.createPool({

    host:process.env.DB_HOST,

    user:process.env.DB_USER,

    password:process.env.DB_PASSWORD,

    database:process.env.DB_NAME,

    waitForConnections:true,

    connectionLimit:10

});



// ===============================
// 穿戴类判断
// ===============================

function isWearable(category){

    if(!category) return false;


    return category.startsWith("个人防护");

}



// ===============================
// 分类拆分
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

        level1:arr[0] || "",

        level2:arr[1] || "",

        level3:arr[2] || ""

    };

}



// ===============================
// 商品名称清洗
// ===============================

function cleanProductName(name){

    if(!name)
        return "";


    let result=name;


    // 删除尺码

    result=result.replace(
        /(XS|S|M|L|XL|XXL|XXXL|\d{2,3}码)$/gi,
        ""
    );


    // 删除包装

    result=result.replace(
        /(\d+)(只|双|件|套|个|包|盒|瓶|卷|米)装?/g,
        ""
    );


    // 删除括号内容中的明显规格

    result=result.replace(
        /\(([^)]*(码|装|件|颜色|颜色可选)[^)]*)\)/g,
        ""
    );


    return result.trim();

}



// ===============================
// 颜色提取
// ===============================

function extractColors(name){


    if(!name)
        return [];


    const colors=[

        "黑色",
        "白色",
        "黄色",
        "蓝色",
        "红色",
        "绿色",
        "橙色",
        "灰色",
        "藏蓝",
        "荧光黄",
        "荧光绿",
        "荧光橙",
        "深灰",
        "浅蓝",
        "卡其",
        "粉色"

    ];


    let result=[];


    colors.forEach(c=>{

        if(name.includes(c)){

            result.push(c);

        }

    });


    return [...new Set(result)];

}



// ===============================
// 分类写入
// ===============================

async function saveCategory(conn,cate){


    if(!cate.level1)
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

VALUES
(?,?,?)

`,
[
    cate.level3 || cate.level2 || cate.level1,

    full,

    cate.level3?3:(cate.level2?2:1)

]

);


}



// ===============================
// 主流程
// ===============================

async function main(){


    const conn=await pool.getConnection();


    try{


        console.log("开始商品聚合");



        // 清空旧数据

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
            "有效商品:",
            rows.length
        );



        const products=new Map();



        let wearableCount=0;



        for(const row of rows){


            if(!isWearable(row.cate_full_name)){

                continue;

            }


            wearableCount++;



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
                        cleanProductName(
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


                        colors:
                        new Set(
                            extractColors(
                                row.goods_name
                            )
                        )

                    }

                );


            }else{


                const p=
                products.get(row.goods_id);


                extractColors(
                    row.goods_name
                )
                .forEach(c=>
                    p.colors.add(c)
                );


            }


        }



        console.log(
            "穿戴商品:",
            wearableCount
        );



        console.log(
            "聚合商品:",
            products.size
        );



        for(const p of products.values()){


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

colors

)

VALUES
(?,?,?,?,?,?,?,?,?)

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

JSON.stringify(
    [...p.colors]
)

]

);


        }



        await conn.query(`

UPDATE product_category c

SET product_count=

(

SELECT COUNT(*)

FROM product_catalog p

WHERE

p.category_level_3=c.category_name

)

`);




        console.log(
            "商品聚合完成"
        );



    }
    catch(err){

        console.error(err);

    }
    finally{

        conn.release();

        process.exit();

    }


}



main();
