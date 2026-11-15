const {chromium}=require('playwright');const fs=require('fs');
const BODY=`<style>body{font:11pt/1.45 Helvetica,Arial,sans-serif;margin:0;padding:34px 42px;color:#111}
h1{font-size:19pt;margin:0 0 2px}h2{font-size:11.5pt;margin:16px 0 5px;letter-spacing:.5px}
ul{margin:4px 0 8px 16px;padding:0}li{margin:2px 0}.r{float:right;font-weight:normal}
table{border-collapse:collapse;width:100%}td{vertical-align:top;padding:0 10px 10px 0}
.side{width:30%}.main{width:70%}.muted{color:#555}</style>`;
const EXP=`<h2>WORK EXPERIENCE</h2>
<b>Production Coordinator</b> <span class="r">March 2023 – Present</span><br><span class="muted">Northwind Manufacturing, Montreal, QC</span>
<ul><li>Request supplier quotes and handle purchasing within the bill of materials.</li>
<li>Coordinate shipments with vendors and subcontractors.</li>
<li>Monitor inventory levels and resolve production bottlenecks.</li></ul>
<b>Supply Chain Intern</b> <span class="r">January 2022 – April 2022</span><br><span class="muted">Lakeside Pharma, Laval, QC</span>
<ul><li>Ran MRP for high moving inventory and prepared purchase orders.</li>
<li>Analysed inventory accuracy and KPIs in Excel.</li></ul>`;
const EDU=`<h2>EDUCATION</h2><b>B.Eng. Industrial Engineering</b> <span class="r">2018 – 2022</span><br><span class="muted">Concordia University, Montreal, QC</span>`;
const SK=`<h2>SKILLS</h2>Inventory control, demand forecasting, SAP, Power BI, AutoCAD, SolidWorks, Lean Six Sigma, quality inspection, preventive maintenance, technical documentation.`;
const INT=`<h2>INTERESTS</h2>Cooking, basketball, snowboarding, travel.`;
const C={};
C.plain=`${BODY}<h1>Dana Example</h1><div class="muted">Montreal, QC</div>${EXP}${EDU}${SK}${INT}`;
C.sidebar=`${BODY}<h1>Dana Example</h1><table><tr><td class="side"><h2>SKILLS</h2>Inventory control<br>Demand forecasting<br>SAP<br>Power BI<br>AutoCAD<br>SolidWorks<br>Lean Six Sigma<br>Quality inspection<br>Preventive maintenance<h2>LANGUAGES</h2>English<br>French<h2>INTERESTS</h2>Cooking<br>Basketball</td><td class="main">${EXP}${EDU}</td></tr></table>`;
C.table=`${BODY}<h1>Dana Example</h1><h2>WORK EXPERIENCE</h2>
<table><tr><td style="width:26%" class="muted">March 2023 – Present</td><td><b>Production Coordinator</b>, Northwind Manufacturing<ul><li>Request supplier quotes and handle purchasing within the bill of materials.</li><li>Monitor inventory levels and resolve production bottlenecks.</li></ul></td></tr>
<tr><td class="muted">January 2022 – April 2022</td><td><b>Supply Chain Intern</b>, Lakeside Pharma<ul><li>Ran MRP for high moving inventory and prepared purchase orders.</li></ul></td></tr></table>
<h2>EDUCATION</h2><table><tr><td style="width:26%" class="muted">2018 – 2022</td><td><b>B.Eng. Industrial Engineering</b>, Concordia University</td></tr></table>${SK}`;
C.custom=`${BODY}<h1>Dana Example</h1><h2>WHAT I DO BEST</h2>Inventory control, demand forecasting, SAP, Power BI, Lean Six Sigma.
<h2>PLACES I HAVE WORKED</h2><b>Production Coordinator</b> <span class="r">March 2023 – Present</span><br>Northwind Manufacturing
<ul><li>Request supplier quotes and handle purchasing within the bill of materials.</li><li>Monitor inventory and resolve production bottlenecks.</li></ul>
<h2>SCHOOLING</h2><b>B.Eng. Industrial Engineering</b>, Concordia University <span class="r">2018 – 2022</span>
<h2>THINGS I LIKE</h2>Cooking, basketball, snowboarding.`;
C.twopage=`${BODY}<h1>Dana Example</h1>${EXP}${EXP.replace(/Northwind/g,'Eastport').replace(/2023/g,'2019').replace(/2022/g,'2018')}<div style="page-break-before:always"></div>${EDU}${SK}${INT}`;
C.bullets=`${BODY}<h1>Dana Example</h1><h2>WORK EXPERIENCE</h2><b>Production Coordinator</b> | Northwind Manufacturing | March 2023 – Present
<div>&#9642;Request supplier quotes and handle purchasing within the bill of materials.</div>
<div>&#9642;Coordinate shipments with vendors and subcontractors.</div>
<div>&#9642;Monitor inventory levels and resolve production bottlenecks.</div>${EDU}${SK}`;
C.narrow=`${BODY}<h1>Dana Example</h1><div style="column-count:2;column-gap:26px">${EXP}${EDU}${SK}</div>`;
(async()=>{
const b=await chromium.launch();
for(const k of Object.keys(C)){
  const p=await b.newPage();
  await p.setContent(C[k],{waitUntil:'load'});
  await p.pdf({path:k+'.pdf',format:'Letter',printBackground:true,
    displayHeaderFooter:k==='twopage',headerTemplate:'<div style="font-size:8px;width:100%;text-align:right;padding-right:30px">Dana Example — CV</div>',
    footerTemplate:'<div style="font-size:8px;width:100%;text-align:center">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
    margin:k==='twopage'?{top:'40px',bottom:'40px'}:undefined});
  await p.close();
}
// a scanned CV: a picture of the plain CV, no text layer
const p=await b.newPage({viewport:{width:816,height:1056},deviceScaleFactor:2});
await p.setContent(C.plain,{waitUntil:'load'});await p.screenshot({path:'scan.png',fullPage:true});
const img=fs.readFileSync('scan.png').toString('base64');
const q=await b.newPage();
await q.setContent('<style>body{margin:0}img{width:100%}</style><img src="data:image/png;base64,'+img+'">',{waitUntil:'load'});
await q.pdf({path:'scanned.pdf',format:'Letter'});
await b.close();console.log('made:',Object.keys(C).join(' '),'scanned');
})();
