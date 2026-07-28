require("dotenv").config();


const express=require("express");

const cors=require("cors");


const productRoutes=require("./routes/product");


const app=express();


app.use(cors());

app.use(express.json());



app.use(
"/api",
productRoutes
);



app.get("/",(req,res)=>{

    res.send(
        "PPE Product Admin API Running"
    );

});



const PORT=process.env.PORT||9530;


app.listen(PORT,()=>{

    console.log(
        "Server running:",
        PORT
    );

});
