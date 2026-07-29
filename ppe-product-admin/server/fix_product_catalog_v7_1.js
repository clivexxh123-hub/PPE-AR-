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


// 商品名称清洗

function cleanName(name){

    if(!name)
        return "";


    let n=name;


    // 清理括号

    n=n.replace(
        /（.*?）/g,
        ""
    );


    n=n.replace(
        /\(\)/g,
        ""
    );


    // 删除鞋码

    n=n.replace(
        /-\d+码/g,
        ""
    );


    // 删除左右规格

    [
        "右单只",
        "左单只",
        "单只",
        "左",
        "右"
    ]
    .forEach(w=>{

        n=n.replace(
            new RegExp(w,"g"),
            ""
        );

    });



    // 删除备注

    [
        "和尺码",
        "尺码",
        "颜色备注",
        "颜色可选",
        "备注颜色"
    ]
    .forEach(w=>{

        n=n.replace(
            new RegExp(w,"g"),
            ""
        );

    });



    n=n
    .replace(/[-_]+$/g,"")
    .replace(/\s+/g," ")
    .trim();


    return n;

}



async function main(){


const conn=await pool.getConnection();


try{


console.log(
"开始 V7.1 修复"
);



const [rows]=await conn.query(

`
SELECT *
FROM product_catalog
`

);



console.log(
"当前:",
rows.length
);



const map=new Map();



for(const row of rows){


const name=cleanName(
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

JSON.parse(row.colors||"[]")
.forEach(c=>{

p.colors.add(c);

});

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


let colors=[...p.colors];


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

JSON.stringify(colors),

colors.length,

p.source_count

]

);


}



console.log(
"V7.1完成"
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
