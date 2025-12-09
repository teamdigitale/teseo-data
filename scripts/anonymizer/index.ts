import { readdir, mkdir } from "node:fs/promises";
import { INPUT_DIR, OUTPUT_DIR } from "./config";
import { anonymizeTextChunked } from "./anonymizer";
import { resetMaps } from "./faker";

async function ensureOutputDir(): Promise<void> {
  await mkdir(OUTPUT_DIR, { recursive: true });
}

async function anonymizeFile(
  inputPath: string,
  outputPath: string
): Promise<void> {
  console.log(`\nReading file: ${inputPath}`);

  const file = Bun.file(inputPath);
  const text = await file.text();

  console.log(`File size: ${text.length} characters`);

  const anonymized = anonymizeTextChunked(text);

  await Bun.write(outputPath, anonymized);
  console.log(`Anonymized file saved to: ${outputPath}`);
}

async function anonymizeFirstNLines(
  inputPath: string,
  outputPath: string,
  n: number
): Promise<void> {
  console.log(`\nReading first ${n} lines from: ${inputPath}`);

  const file = Bun.file(inputPath);
  const text = await file.text();
  const lines = text.split("\n").slice(0, n);
  const partialText = lines.join("\n");

  console.log(`Processing ${lines.length} lines (${partialText.length} chars)`);

  const anonymized = anonymizeTextChunked(partialText);

  await Bun.write(outputPath, anonymized);
  console.log(`Anonymized file saved to: ${outputPath}`);
}

async function getInputFiles(): Promise<string[]> {
  try {
    const files = await readdir(INPUT_DIR);
    return files.filter(
      (f) => f.endsWith(".csv") || f.endsWith(".txt") || f.endsWith(".json")
    );
  } catch {
    console.error(`Input directory not found: ${INPUT_DIR}`);
    return [];
  }
}

function getTimestamp(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}_${month}_${day}`;
}

function getOutputFileName(inputFile: string): string {
  const parts = inputFile.split(".");
  const ext = parts.pop();
  const name = parts.join(".");
  const timestamp = getTimestamp();
  return `${name}_anonymized_${timestamp}.${ext}`;
}

async function main() {
  console.log("=== Anonymizer ===\n");

  await ensureOutputDir();

  const inputFiles = await getInputFiles();

  if (inputFiles.length === 0) {
    console.log(`No files found in ${INPUT_DIR}`);
    console.log("Supported formats: .csv, .txt, .json");
    console.log(`\nPlace your files in the '${INPUT_DIR}' folder and run again.`);
    return;
  }

  console.log(`Found ${inputFiles.length} file(s) to process:\n`);

  for (const inputFile of inputFiles) {
    // Reset le mappe per ogni file (coerenza solo all'interno dello stesso file)
    resetMaps();

    const inputPath = `${INPUT_DIR}/${inputFile}`;
    const outputFile = getOutputFileName(inputFile);
    const outputPath = `${OUTPUT_DIR}/${outputFile}`;

    await anonymizeFile(inputPath, outputPath);
  }

  console.log("\n=== Done! ===");
}

// Per testare con le prime N righe
async function testMode(n: number = 100) {
  console.log(`=== Anonymizer (TEST MODE - first ${n} lines) ===\n`);

  await ensureOutputDir();

  const inputFiles = await getInputFiles();

  if (inputFiles.length === 0) {
    console.log(`No files found in ${INPUT_DIR}`);
    return;
  }

  for (const inputFile of inputFiles) {
    resetMaps();

    const inputPath = `${INPUT_DIR}/${inputFile}`;
    const outputFile = getOutputFileName(inputFile).replace(
      "_anonymized",
      `_anonymized_test_${n}`
    );
    const outputPath = `${OUTPUT_DIR}/${outputFile}`;

    await anonymizeFirstNLines(inputPath, outputPath, n);
  }

  console.log("\n=== Test Done! ===");
}

// Entry point
const args = process.argv.slice(2);

if (args.includes("--test")) {
  const nIndex = args.indexOf("-n");
  const nValue = nIndex !== -1 ? args[nIndex + 1] : undefined;
  const n = nValue ? parseInt(nValue, 10) : 100;
  testMode(n);
} else {
  main();
}

