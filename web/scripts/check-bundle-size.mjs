// Bundle budget gate: the shipped JS + CSS must stay under 250 KB gzipped.
// Run after `npm run build`; CI fails the `web` job if the budget is blown so a
// size regression (an errant dependency, a lost tree-shake) is caught at review
// time. Uses Node's own gzip — no extra dependency, which is rather the point.
import { readdirSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";

const BUDGET_KB = 250;
const assetsDir = fileURLToPath(new URL("../dist/assets/", import.meta.url));

let files;
try {
  files = readdirSync(assetsDir);
} catch {
  console.error(`No dist/assets — run \`npm run build\` first.`);
  process.exit(1);
}

const shipped = files.filter((f) => f.endsWith(".js") || f.endsWith(".css"));
let totalGz = 0;
const rows = shipped.map((name) => {
  const buf = readFileSync(new URL(name, `file://${assetsDir}`));
  const gz = gzipSync(buf).length;
  totalGz += gz;
  return { name, raw: buf.length, gz };
});

const kb = (n) => (n / 1024).toFixed(2).padStart(8) + " KB";
console.log("Bundle (dist/assets):");
for (const r of rows.sort((a, b) => b.gz - a.gz)) {
  console.log(`  ${kb(r.raw)} raw  ${kb(r.gz)} gz   ${r.name}`);
}
console.log(`  ${" ".repeat(11)}total ${kb(totalGz)} gz  (budget ${BUDGET_KB} KB)`);

if (totalGz > BUDGET_KB * 1024) {
  console.error(
    `\n✗ Bundle over budget: ${(totalGz / 1024).toFixed(2)} KB > ${BUDGET_KB} KB gz`,
  );
  process.exit(1);
}
console.log(
  `\n✓ Within budget: ${(totalGz / 1024).toFixed(2)} KB / ${BUDGET_KB} KB gz`,
);
