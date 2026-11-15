/* Checks on the CV reader. Run: node tests/read.test.js
   Each case is a shape of CV that broke the reader at least once. */
const R=require('../after-1/cvread.js');
let pass=0,fail=0;
const ok=(name,cond,extra)=>{if(cond){pass++;console.log('  ok   '+name);}else{fail++;console.log('  FAIL '+name+(extra?'  → '+extra:''));}};

/* Build a page of text pieces. letterByLetter: one piece per letter, the way some
   design tools export, which is what hid the bug this test exists for. */
function page(lines,letterByLetter){
  const its=[];
  for(const L of lines){
    let x=L.x;
    if(letterByLetter){
      for(const ch of L.t){if(ch!==' ')its.push({s:ch,x:x,y:L.y,w:5.4,h:10});x+=5.6;}
    }else its.push({s:L.t,x:x,y:L.y,w:L.t.length*5.6,h:10});
  }
  return its;
}
/* A sidebar of skills on the left, a paragraph of work history on the right. */
function sidebarPage(letterByLetter){
  const lines=[];
  const side=["LANGUAGES","English","French","SKILLS","Inventory control","SAP","Power BI","AutoCAD","Lean Six Sigma"];
  const main=["WORK EXPERIENCE","Production Coordinator","Northwind Manufacturing","March 2023 - Present",
    "I requested supplier quotes for materials","handled purchasing of components within","the bill of materials and coordinated",
    "shipments with vendors and subcontractors","to keep projects on track and on budget","EDUCATION","B.Eng. Industrial Engineering"];
  side.forEach((t,i)=>lines.push({t:t,x:40,y:740-i*16}));
  main.forEach((t,i)=>lines.push({t:t,x:230,y:740-i*16}));
  return page(lines,letterByLetter);
}

console.log('columns');
for(const mode of [false,true]){
  const label=mode?'one piece per letter':'one piece per line';
  const cuts=R.columnCuts(sidebarPage(mode));
  ok('a sidebar gives exactly one column break ('+label+')',cuts.length===1,'got '+JSON.stringify(cuts));
  ok('the break sits between the two columns ('+label+')',cuts.length===1&&cuts[0]>120&&cuts[0]<230,'got '+JSON.stringify(cuts));
  const text=R.pdfPageLines(sidebarPage(mode)).join('\n');
  ok('no line loses its start ('+label+')',/I requested supplier quotes for materials/.test(text)&&/Production Coordinator/.test(text),
     text.split('\n').slice(0,3).join(' / '));
}
/* A plain CV with its dates pushed to the right edge must NOT be split:
   the empty strip before the dates is not a column. */
const plain=page([{t:"WORK EXPERIENCE",x:40,y:740},{t:"Production Coordinator",x:40,y:724},{t:"March 2023 - Present",x:420,y:724},
 {t:"I requested supplier quotes for materials needed",x:40,y:708},{t:"handled purchasing of components and parts",x:40,y:692},
 {t:"Supply Chain Intern",x:40,y:676},{t:"January 2022 - April 2022",x:420,y:676},
 {t:"Ran MRP for high moving inventory and orders",x:40,y:660},{t:"EDUCATION",x:40,y:644},
 {t:"B.Eng. Industrial Engineering, Concordia",x:40,y:628},{t:"2018 - 2022",x:420,y:628}],false);
ok('right-aligned dates are not read as a column',R.columnCuts(plain).length===0,JSON.stringify(R.columnCuts(plain)));

console.log('the person\'s own section names');
const custom="PLACES I HAVE WORKED\nProduction Coordinator, March 2023 - Present\nSCHOOLING\nB.Eng. Industrial Engineering\nTHINGS I LIKE\nCooking and basketball\n";
const m=R.markSections(custom,["work experience","education","interests"]);
ok('"PLACES I HAVE WORKED" is understood as work',/WORK EXPERIENCE\nPLACES I HAVE WORKED/.test(m.text));
ok('"SCHOOLING" is understood as education',/EDUCATION\nSCHOOLING/.test(m.text));
ok('"THINGS I LIKE" is understood as interests',/INTERESTS\nTHINGS I LIKE/.test(m.text));
ok('a job title is never taken for a section name',R.markSections("PRODUCTION COORDINATOR\nDid things\n",[]).added===0);
ok('nothing is added twice',R.markSections(m.text,["work experience","education","interests"]).added===0);

console.log('tidying');
ok('letters spaced one by one are joined',/French \(mother tongue\)/.test(R.fixLetterSpacing("F r e n c h   ( m o t h e r   t o n g u e )")));
ok('a ligature becomes two letters',R.tidyText("Certiﬁcate")==="Certificate");
ok('a word split across two lines is joined',R.tidyText("mainte-\nnance")==="maintenance");
ok('an invisible character is removed',R.tidyText("Power​BI")==="PowerBI");

console.log('several versions in one file');
const p1="Production Coordinator\nMarch 2023 - Present\nNorthwind Manufacturing\nInventory control and purchasing\nB.Eng. Industrial Engineering 2018 - 2022";
const fr="Coordonnateur de production\nMarch 2023 - Present\nNorthwind Manufacturing\nGestion des stocks et achats\nBaccalaureat en genie industriel 2018 - 2022";
const p2="Sales Representative\nDecember 2019 - January 2021\nCall centre work and customer offers\nVolunteer tutor 2016 - 2017";
ok('the same CV in another language is not counted twice',R.dropRepeatedPages([p1,fr]).dropped===1);
ok('a real second page is kept',R.dropRepeatedPages([p1,p2]).dropped===0);

console.log('did the file give us text');
ok('text one letter at a time is reported',R.readQuality("F r e n c h m o t h e r").singleRatio>0.35);
ok('normal text is fine',R.readQuality("Production Coordinator at Northwind Manufacturing").singleRatio<0.1);

console.log('\n'+pass+' passed, '+fail+' failed');
process.exit(fail?1:0);
