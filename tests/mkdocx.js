const {Document,Packer,Paragraph,TextRun,HeadingLevel}=require('docx');const fs=require('fs');
const P=(t,b)=>new Paragraph({children:[new TextRun({text:t,bold:b,font:"Calibri",size:22})]});
const doc=new Document({sections:[{children:[
P("Dana Example",true),P("Montreal, QC"),
P("PLACES I HAVE WORKED",true),
P("Production Coordinator — Northwind Manufacturing — March 2023 – Present",true),
P("Request supplier quotes and handle purchasing within the bill of materials."),
P("Coordinate shipments with vendors and subcontractors."),
P("Supply Chain Intern — Lakeside Pharma — January 2022 – April 2022",true),
P("Ran MRP for high moving inventory and prepared purchase orders."),
P("SCHOOLING",true),P("B.Eng. Industrial Engineering, Concordia University, 2018 – 2022"),
P("WHAT I DO BEST",true),P("Inventory control, demand forecasting, SAP, Power BI, Lean Six Sigma, quality inspection."),
P("THINGS I LIKE",true),P("Cooking, basketball, snowboarding.")]}]});
Packer.toBuffer(doc).then(b=>fs.writeFileSync('word.docx',b));
