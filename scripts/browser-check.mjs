import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright-core';

const snapshot = JSON.parse(await readFile(new URL('../public/evaluation.json', import.meta.url), 'utf8'));
const modelComparison = JSON.parse(await readFile(new URL('../public/model-comparison.json', import.meta.url), 'utf8'));
const baseURL = process.env.FRAUDLENS_BROWSER_URL ?? 'http://127.0.0.1:4176';
const output = process.env.FRAUDLENS_BROWSER_OUTPUT ?? 'work/browser-check';
await mkdir(output, {recursive:true});
const launch = process.env.FRAUDLENS_BROWSER_EXECUTABLE ? {executablePath:process.env.FRAUDLENS_BROWSER_EXECUTABLE} : {channel:'chrome'};
const browser = await chromium.launch({...launch, headless:true});
const results = [];
function check(name, condition) { assert.ok(condition, name); results.push({name,passed:true}); }
const widths = [320,390,768,1440];
try {
  for (const width of widths) {
    const context = await browser.newContext({viewport:{width,height:1000}, reducedMotion:'reduce'});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(baseURL, {waitUntil:'networkidle'});
    await page.getByRole('button',{name:/Apply selection policy/}).waitFor();
    const checkBounds = async suffix => {
      const size = await page.evaluate(()=>({width:innerWidth,body:document.body.scrollWidth,document:document.documentElement.scrollWidth}));
      check(`${width}: no page overflow ${suffix}`,size.body<=width+1 && size.document<=width+1);
    };
    await checkBounds('initial');
    await page.screenshot({path:`${output}/fraudlens-model-upgrade-${width}.png`});
    const fresh = page.locator('#model-upgrade');
    check(`${width}: frozen comparison appears before legacy controls`,await page.evaluate(()=>Boolean(document.querySelector('#model-upgrade').compareDocumentPosition(document.querySelector('#strategy'))&Node.DOCUMENT_POSITION_FOLLOWING)));
    check(`${width}: ranking label follows the frozen gate`,await fresh.getAttribute('data-comparison-status')===(modelComparison.comparison.promotion_gate_passed?'validated':'inconclusive'));
    const formatted = value => new Intl.NumberFormat('en-US').format(value);
    for(const name of ['incumbent','challenger']) {
      const expected = modelComparison.models[name].budgets[String(modelComparison.primary_budget)];
      const card = fresh.locator(`[data-model="${name}"]`);
      check(`${width}: ${name} shows fresh paired fraud count`,(await card.locator('.upgrade-found').innerText())===`${formatted(expected.true_positives)} / ${formatted(modelComparison.fresh_evaluation.fraud_rows)}`);
      check(`${width}: ${name} shows fresh false alerts`,(await card.innerText()).includes(formatted(expected.false_positives)));
    }
    check(`${width}: every predeclared budget is shown`,await fresh.locator('tbody tr').count()===Object.keys(modelComparison.models.incumbent.budgets).length);
    for(const [budget, old] of Object.entries(modelComparison.models.incumbent.budgets)) {
      const next = modelComparison.models.challenger.budgets[budget];
      const row = fresh.locator(`[data-budget="${budget}"]`);
      const cells = await row.locator('td').allTextContents();
      check(`${width}: budget ${budget} preserves same-alert paired counts`,cells[0]===formatted(old.alerts)&&old.alerts===next.alerts&&cells[1]===`${formatted(old.true_positives)} → ${formatted(next.true_positives)}`&&cells[3]===`${formatted(old.false_positives)} → ${formatted(next.false_positives)}`);
    }
    check(`${width}: cost regression stays visibly disclosed`,(await fresh.locator('.upgrade-cost-caveat').innerText()).includes('cost policy regressed') && (await fresh.locator('.upgrade-cost-caveat').innerText()).includes('$84,405.00'));
    const freshBeforeLegacyEdits = await fresh.locator('.upgrade-models').innerText();
    await fresh.locator('summary').click();
    const comparisonDownload = page.getByRole('link',{name:'Download model comparison report',exact:true});
    const currentComparison = await page.request.get(new URL(await comparisonDownload.getAttribute('href'),baseURL).href);
    check(`${width}: fresh report download matches frozen plan`,currentComparison.ok() && (await currentComparison.json()).plan_id===modelComparison.plan_id);
    await checkBounds('fresh evidence open');
    await fresh.locator('summary').click();
    const slider = page.getByLabel('Fraud decision threshold',{exact:true});
    for (const [key,index] of [['Home',0],['End',98]]) {
      await slider.press(key);
      const expected = snapshot.models.xgboost.test_thresholds[index];
      await page.waitForFunction(value=>document.querySelector('input[type=range]').value===String(value),expected.threshold);
      const cells = await page.locator('.matrix-cell strong').allTextContents();
      const counts = cells.map(value=>Number(value.replaceAll(',','')));
      check(`${width}: keyboard ${key} uses actual test confusion counts`,JSON.stringify(counts)===JSON.stringify([expected.true_positives,expected.false_negatives,expected.false_positives,expected.true_negatives]));
    }
    await page.getByRole('button',{name:/Apply selection policy/}).click();
    check(`${width}: legacy controls cannot change fresh model results`,await fresh.locator('.upgrade-models').innerText()===freshBeforeLegacyEdits);
    check(`${width}: policy chosen from selection`,await slider.inputValue()===String(snapshot.models.xgboost.selected_threshold));
    for (const [label, betaSquared] of [['Balanced F1',1],['Recall-focused F2',4]]) {
      const score = point => (1+betaSquared)*point.true_positives / ((1+betaSquared)*point.true_positives + betaSquared*point.false_negatives + point.false_positives || 1);
      const expected = [...snapshot.models.xgboost.selection_thresholds].sort((a,b)=>score(b)-score(a)||b.threshold-a.threshold)[0];
      await page.getByRole('button',{name:`Apply ${label} policy`,exact:true}).click();
      check(`${width}: ${label} applies selection-scored threshold`,await slider.inputValue()===String(expected.threshold));
      const test = snapshot.models.xgboost.test_thresholds.find(point=>point.threshold===expected.threshold);
      const counts = (await page.locator('.matrix-cell strong').allTextContents()).map(value=>Number(value.replaceAll(',','')));
      check(`${width}: ${label} displays test confusion counts`,JSON.stringify(counts)===JSON.stringify([test.true_positives,test.false_negatives,test.false_positives,test.true_negatives]));
    }
    await page.getByRole('button',{name:'Apply Cost-focused policy',exact:true}).click();
    check(`${width}: cost preset restores selection cost policy`,await slider.inputValue()===String(snapshot.models.xgboost.selected_threshold));
    check(`${width}: inert topbar actions absent`,await page.getByRole('button',{name:'Notifications',exact:true}).count()===0 && await page.getByRole('button',{name:'Search',exact:true}).count()===0);
    await page.getByRole('button',{name:'Cost assumptions',exact:true}).click();
    for (const [label,invalid,retained] of [['False-positive friction cost','-1','18'],['Test-window review capacity','1.5','1400'],['Fraud recovery rate','150','35']]) {
      const input = page.getByLabel(label,{exact:true});
      await input.fill(invalid);
      check(`${width}: ${label} retains valid value`,await input.inputValue()===retained);
      check(`${width}: ${label} has actionable error`,(await page.locator('.assumption-error').innerText()).includes('last valid calculation is retained'));
    }
    // Make a real value change: filling the already-retained controlled value
    // does not dispatch a React change and cannot clear its validation state.
    await page.getByLabel('False-positive friction cost',{exact:true}).fill('19');
    await page.waitForFunction(()=>document.querySelector('.assumption-error')===null);
    check(`${width}: valid edit clears error`,await page.locator('.assumption-error').count()===0);
    await page.getByLabel('False-positive friction cost',{exact:true}).fill('18');
    await page.getByText('Inspect reproducible evaluation evidence',{exact:true}).click();
    check(`${width}: calibration evidence opens`,await page.getByRole('heading',{name:'Measured calibration on the held-out test window'}).isVisible());
    await checkBounds('evidence open');
    const download = page.getByRole('link',{name:'Download study snapshot',exact:true});
    const evidence = await page.request.get(new URL(await download.getAttribute('href'),baseURL).href);
    check(`${width}: evidence download is current study`,evidence.ok() && (await evidence.json()).study_id===snapshot.study_id);
    await page.getByText('Inspect reproducible evaluation evidence',{exact:true}).click();
    await page.getByLabel('Search transactions',{exact:true}).fill('Nova');
    check(`${width}: authored search filters rows`,await page.locator('.transaction-table tbody tr').count()===1);
    const table = page.getByRole('region',{name:'Authored transaction table, scroll horizontally for all columns',exact:true});
    const needsScroll = await table.evaluate(el=>el.scrollWidth>el.clientWidth+1);
    if (needsScroll) {
      await table.press('ArrowRight');
      await page.waitForFunction(()=>document.querySelector('.transaction-table-wrap').scrollLeft>0);
      check(`${width}: table supports keyboard horizontal scroll`,await table.evaluate(el=>el.scrollLeft)>0);
    }
    await page.getByRole('button',{name:'Explain FL-290874',exact:true}).click();
    check(`${width}: explanation stays explicitly authored`,(await page.locator('.drawer-callout').innerText()).includes('authored demo values'));
    await page.getByRole('button',{name:'Close explanation',exact:true}).click();
    await page.locator('.attack-card').first().getByRole('button',{name:'Evaluate example',exact:true}).click();
    check(`${width}: authored comparison is immediate and threshold stamped`,(await page.locator('.attack-card').first().innerText()).includes(`Flagged at ${snapshot.models.xgboost.selected_threshold.toFixed(2)}`));
    await checkBounds('after interactions');
    await page.getByRole('heading',{name:'Balance fraud loss against customer trust.',exact:true}).scrollIntoViewIfNeeded();
    await page.screenshot({path:`${output}/fraudlens-${width}.png`});
    check(`${width}: no browser exceptions`,errors.length===0);
    await context.close();
  }
  console.log(`${results.length} browser checks passed across ${widths.join(', ')}px`);
} finally {
  await writeFile(`${output}/results.json`,JSON.stringify({baseURL,study_id:snapshot.study_id,checks:results},null,2));
  await browser.close();
}
