const express=require("express");

const router=express.Router();

const multer=require("multer");

const controller=require("../controllers/logo.controller");
const { requirePermission } = require("../services/iam/access");



const storage=multer.diskStorage({

destination(req,file,cb){

cb(null,"uploads/logos");

},


filename(req,file,cb){

const ext =
file.originalname.substring(
file.originalname.lastIndexOf(".")
);


cb(
null,
Date.now()+ext
);

}

});


const upload=multer({
storage
});



router.get(
"/",
controller.getLogos
);



router.post(
"/",
requirePermission("catalog.manage"),
upload.single("logo"),
controller.createLogo
);



module.exports=router;
