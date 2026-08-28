const pool = require("../db");


// Logo列表
exports.getLogos = async(req,res)=>{

try{

const keyword=req.query.keyword || "";


let sql=`

SELECT *

FROM ai_logo_assets

`;

let params=[];


if(keyword){

sql += `

WHERE

region LIKE ?

OR company_name LIKE ?

OR logo_key LIKE ?

`;


const v=`%${keyword}%`;

params=[
v,
v,
v
];

}


sql += `

ORDER BY id DESC

`;


const [rows]=await pool.query(
sql,
params
);


res.json({

success:true,

list:rows

});


}catch(error){

res.status(500).json({

success:false,

message:error.message

});

}

};



// 新增Logo

exports.createLogo = async(req,res)=>{

try{


const {
region,
company_name,
remark
}=req.body;


const logo_url=req.file
? "/uploads/logos/"+req.file.filename
:null;


const logo_name=req.file
? req.file.originalname
:null;


const logo_key=
`${region}-${company_name}`;



const [result]=await pool.query(

`
INSERT INTO ai_logo_assets
(
logo_key,
region,
company_name,
logo_name,
logo_url,
remark
)

VALUES(?,?,?,?,?,?)

`,
[
logo_key,
region,
company_name,
logo_name,
logo_url,
remark
]

);


res.json({

success:true,

id:result.insertId

});


}catch(error){

console.error(error);

res.status(500).json({
success:false,
message:error.message
});

}


};