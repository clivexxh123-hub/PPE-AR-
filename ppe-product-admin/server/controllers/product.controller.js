const pool = require("../db");


// ===============================
// 分类
// ===============================

exports.getCategories = async(req,res)=>{

    try{


        const [rows]=await pool.query(`

        SELECT

        category_level_2,

        category_level_3,

        COUNT(*) total


        FROM product_catalog


        GROUP BY

        category_level_2,

        category_level_3


        ORDER BY total DESC


        `);



        const result={};


        rows.forEach(item=>{


            if(!result[item.category_level_2]){

                result[item.category_level_2]=[];

            }


            result[item.category_level_2].push({

                name:item.category_level_3,

                count:item.total

            });


        });



        res.json({

            success:true,

            data:Object.keys(result).map(k=>({

                name:k,

                children:result[k]

            }))

        });



    }catch(e){

        console.error(e);

        res.status(500).json({

            success:false,

            message:e.message

        });

    }

};





// ===============================
// 商品列表
// ===============================

exports.getProducts = async(req,res)=>{


    try{


        let {

            page=1,

            size=50,

            level2,

            level3,

            keyword


        }=req.query;


        // 修复中文查询编码

        function fixDecode(value){

            if(!value) return value;

            try{

                return decodeURIComponent(
                    escape(value)
                );

            }catch(e){

                return value;

            }

        }


        level2=fixDecode(level2);
        level3=fixDecode(level3);
        keyword=fixDecode(keyword);




        page=parseInt(page);

        size=parseInt(size);



        let where=[];

        let params=[];



        if(level2){

            where.push(
                "category_level_2=?"
            );

            params.push(level2);

        }


        if(level3){

            where.push(
                "category_level_3=?"
            );

            params.push(level3);

        }



        if(keyword){

            where.push(
                "product_name LIKE ?"
            );

            params.push(
                `%${keyword}%`
            );

        }



        let condition="";


        if(where.length){

            condition=
            "WHERE "+
            where.join(" AND ");

        }



        console.log("QUERY CONDITION:", condition);
        console.log("QUERY PARAMS:", params);


        const [count]=await pool.query(`

        SELECT COUNT(*) total

        FROM product_catalog

        ${condition}


        `,params);



        const [rows]=await pool.query(`

        SELECT

        id,

        goods_id,

        goods_no,

        product_name,

        category_level_1,

        category_level_2,

        category_level_3,

        brand_name,

        colors,

        has_files


        FROM product_catalog


        ${condition}


        ORDER BY id DESC


        LIMIT ?,?


        `,

        [

            ...params,

            (page-1)*size,

            size

        ]);



        rows.forEach(item=>{

            try{

                item.colors=
                JSON.parse(item.colors || "[]");

            }catch{

                item.colors=[];

            }

        });



        res.json({

            success:true,

            total:count[0].total,

            page,

            size,

            list:rows

        });



    }catch(e){

        console.error(e);

        res.status(500).json({

            success:false,

            message:e.message

        });

    }


};
