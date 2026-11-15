const {chromium}=require('playwright');const fs=require('fs');
const CSS=`<style>body{font:11pt/1.45 Helvetica,Arial,sans-serif;margin:0;padding:34px 42px;color:#111}
h1{font-size:18pt;margin:0 0 2px}h2{font-size:11.5pt;margin:15px 0 5px}h3{font-size:11pt;margin:10px 0 2px}
.muted{color:#555}ul{margin:4px 0 8px 16px;padding:0}table{border-collapse:collapse;width:100%}
td{vertical-align:top;padding:0 10px 8px 0}.lab{width:28%;color:#555}.r{float:right;font-weight:normal}</style>`;
const C={};
/* A LinkedIn profile export: contact block, a headline, then sections, with a page footer. */
C.linkedin=`${CSS}<div class="muted" style="font-size:9pt">Contact<br>montreal, QC<br>www.linkedin.com/in/example (LinkedIn)</div>
<h2>Top Skills</h2>Inventory control<br>Demand forecasting<br>SAP
<h1>Dana Example</h1><div class="muted">Production Coordinator at Northwind Manufacturing</div><div class="muted">Montreal, Quebec, Canada</div>
<h2>Summary</h2>Industrial engineer working in purchasing and production planning.
<h2>Experience</h2>
<h3>Northwind Manufacturing</h3><div class="muted">Production Coordinator</div><div class="muted">March 2023 - Present (3 years 8 months)</div><div class="muted">Montreal, Quebec, Canada</div>
<ul><li>Request supplier quotes and handle purchasing within the bill of materials.</li><li>Monitor inventory levels and resolve production bottlenecks.</li></ul>
<h3>Lakeside Pharma</h3><div class="muted">Supply Chain Intern</div><div class="muted">January 2022 - April 2022 (4 months)</div>
<ul><li>Ran MRP for high moving inventory and prepared purchase orders.</li></ul>
<h2>Education</h2><h3>Concordia University</h3><div class="muted">B.Eng. Industrial Engineering · (2018 - 2022)</div>`;
/* Europass: a two-column table, the label on the left and the value on the right. */
C.europass=`${CSS}<h1>Curriculum Vitae</h1>
<table><tr><td class="lab">Personal information</td><td>Dana Example, Montreal, QC</td></tr>
<tr><td class="lab">Work experience</td><td></td></tr>
<tr><td class="lab">Dates</td><td>March 2023 - Present</td></tr>
<tr><td class="lab">Occupation or position held</td><td>Production Coordinator</td></tr>
<tr><td class="lab">Name of employer</td><td>Northwind Manufacturing, Montreal</td></tr>
<tr><td class="lab">Main activities</td><td>Supplier quotes, purchasing within the bill of materials, shipments with vendors and subcontractors, inventory levels, production bottlenecks.</td></tr>
<tr><td class="lab">Dates</td><td>January 2022 - April 2022</td></tr>
<tr><td class="lab">Occupation or position held</td><td>Supply Chain Intern</td></tr>
<tr><td class="lab">Name of employer</td><td>Lakeside Pharma, Laval</td></tr>
<tr><td class="lab">Education and training</td><td></td></tr>
<tr><td class="lab">Dates</td><td>2018 - 2022</td></tr>
<tr><td class="lab">Qualification awarded</td><td>B.Eng. Industrial Engineering, Concordia University</td></tr>
<tr><td class="lab">Personal skills</td><td>Inventory control, demand forecasting, SAP, Power BI, Lean Six Sigma, quality inspection.</td></tr></table>`;
/* Icon characters from a private range, the way Font Awesome and Wingdings export. */
C.icons=`${CSS}<h1>Dana Example</h1>
<div class="muted"> 514-555-0100 &nbsp;  example@example.com &nbsp;  Montreal, QC</div>
<h2>WORK EXPERIENCE</h2><b>Production Coordinator</b> <span class="r">March 2023 - Present</span><br><span class="muted">Northwind Manufacturing</span>
<div> Request supplier quotes and handle purchasing within the bill of materials.</div>
<div> Monitor inventory levels and resolve production bottlenecks.</div>
<h2>EDUCATION</h2>B.Eng. Industrial Engineering, Concordia University, 2018 - 2022
<h2>SKILLS</h2>Inventory control, demand forecasting, SAP, Power BI, Lean Six Sigma.`;
/* A three-column grid of skills, the way many CVs lay that section out. */
C.grid=`${CSS}<h1>Dana Example</h1>
<h2>WORK EXPERIENCE</h2><b>Production Coordinator</b> <span class="r">March 2023 - Present</span><br><span class="muted">Northwind Manufacturing</span>
<ul><li>Request supplier quotes and handle purchasing within the bill of materials.</li><li>Monitor inventory levels and resolve production bottlenecks.</li></ul>
<h2>EDUCATION</h2>B.Eng. Industrial Engineering, Concordia University, 2018 - 2022
<h2>SKILLS</h2><table><tr><td>Inventory control<br>Demand forecasting<br>SAP</td><td>Power BI<br>AutoCAD<br>SolidWorks</td><td>Lean Six Sigma<br>Quality inspection<br>Preventive maintenance</td></tr></table>`;
/* A photo beside the header, which must not be taken for a column of text. */
C.photo=`${CSS}<table><tr><td style="width:120px"><div style="width:100px;height:120px;background:linear-gradient(135deg,#9ab,#456)"></div></td>
<td><h1>Dana Example</h1><div class="muted">Production Coordinator · Montreal, QC</div></td></tr></table>
<h2>WORK EXPERIENCE</h2><b>Production Coordinator</b> <span class="r">March 2023 - Present</span><br><span class="muted">Northwind Manufacturing</span>
<ul><li>Request supplier quotes and handle purchasing within the bill of materials.</li><li>Coordinate shipments with vendors and subcontractors.</li><li>Monitor inventory levels and resolve production bottlenecks.</li></ul>
<b>Supply Chain Intern</b> <span class="r">January 2022 - April 2022</span><br><span class="muted">Lakeside Pharma</span>
<ul><li>Ran MRP for high moving inventory and prepared purchase orders.</li></ul>
<h2>EDUCATION</h2>B.Eng. Industrial Engineering, Concordia University, 2018 - 2022
<h2>SKILLS</h2>Inventory control, demand forecasting, SAP, Power BI, Lean Six Sigma.`;
(async()=>{const b=await chromium.launch();
for(const k of Object.keys(C)){const p=await b.newPage();await p.setContent(C[k],{waitUntil:'load'});
  await p.pdf({path:k+'.pdf',format:'Letter',printBackground:true,
    displayHeaderFooter:k==='linkedin',headerTemplate:'<div></div>',
    footerTemplate:'<div style="font-size:8px;width:100%;text-align:center;color:#888">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
    margin:k==='linkedin'?{top:'30px',bottom:'40px'}:undefined});
  await p.close();}
await b.close();console.log('made:',Object.keys(C).join(' '));})();
