import { LangfuseClient } from "@langfuse/client";
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";
import { readdir, mkdir } from "node:fs/promises";

const publicKey = process.env.LANGFUSE_PUBLIC_KEY;
const secretKey = process.env.LANGFUSE_SECRET_KEY;
const baseUrl = "https://cloud.langfuse.com";
const langfuse = new LangfuseClient({
  publicKey,
  secretKey,
  baseUrl,
});

const DATA_DIR = "data/exp";
const STATE_FILE = `${DATA_DIR}/fetch_state.json`;

async function ensureDataDir(): Promise<void> {
  await mkdir(DATA_DIR, { recursive: true });
}

interface FetchState {
  lastProcessedTimestamp: string | null;
  totalQuestionsProcessed: number;
}

async function loadState(): Promise<FetchState> {
  try {
    const file = Bun.file(STATE_FILE);
    if (await file.exists()) {
      return await file.json();
    }
  } catch {
    console.log("No previous state found, starting fresh");
  }
  return { lastProcessedTimestamp: null, totalQuestionsProcessed: 0 };
}

async function saveState(state: FetchState): Promise<void> {
  await Bun.write(STATE_FILE, JSON.stringify(state, null, 2));
}

async function fetchLangfuseData(
  page: number,
  limit: number,
  fromTimestamp?: string
) {
  const response = await langfuse.api.trace.list({
    page: page,
    limit: limit,
    ...(fromTimestamp && { fromTimestamp }),
  });
  return response;
}

async function fetchNewTraces(fromTimestamp: string | null) {
  let allTraces: any[] = [];
  let page = 1;
  const limit = 100;

  while (true) {
    const response = await fetchLangfuseData(
      page,
      limit,
      fromTimestamp || undefined
    );
    allTraces = [...allTraces, response.data];
    if (response.data.length < limit) {
      break;
    }
    page++;
  }

  return allTraces.flat();
}

function getDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}_${month}_${day}`;
}

const BATCH_SIZE = 30;

async function classifyBatch(
  client: OpenAI,
  questions: string[]
): Promise<{ category: string; question: string }[]> {
  const Results = z.object({
    results: z.array(
      z.object({
        category: z.string().describe("Nome della categoria creata"),
        questions: z.array(z.string()),
      })
    ),
  });

  const response = await client.responses.parse({
    model: process.env.OPENAI_MODEL || "gpt-4o",
    input: [
      {
        role: "system",
        content: `Sei un esperto classificatore di domande per un chatbot interno di un dipartimento digitale collegato a tematiche e servizi legati alle misure PNRR.

Il tuo compito è ANALIZZARE le domande e CREARE AUTONOMAMENTE le categorie più appropriate per raggrupparle.

REGOLE IMPORTANTI:
- Analizza semanticamente le domande per identificare temi ricorrenti
- Crea categorie chiare, concise e significative
- Ogni categoria deve avere un nome descrittivo in italiano
- Raggruppa domande simili nella stessa categoria
- Crea un numero ragionevole di categorie (non troppo granulari, non troppo generiche)
- I nomi delle categorie devono essere autoesplicativi
- Evita categorie troppo generiche come "Altro" o "Varie"
- Se una domanda non rientra in nessun tema specifico, puoi ometterla`,
      },
      {
        role: "user",
        content: `Analizza le seguenti ${
          questions.length
        } domande, identifica i temi principali e crea le categorie più appropriate per raggrupparle:\n\n${questions
          .map((q, i) => `${i + 1}. ${q}`)
          .join("\n")}`,
      },
    ],
    text: { format: zodTextFormat(Results, "Results") },
  });

  const classified: { category: string; question: string }[] = [];
  for (const item of response?.output_parsed?.results || []) {
    for (const question of item.questions) {
      classified.push({ category: item.category, question });
    }
  }
  return classified;
}

async function aggregateAllCsvFiles(): Promise<void> {
  console.log("\nAggregating all experimental CSV files...");

  const files = await readdir(DATA_DIR);
  const csvFiles = files.filter(
    (f) => f.startsWith("categories_stats_") && f.endsWith(".csv") && f !== "categories_stats.csv"
  );

  if (csvFiles.length === 0) {
    console.log("No dated experimental CSV files found to aggregate");
    return;
  }

  const categoryTotals = new Map<string, number>();

  for (const csvFile of csvFiles) {
    const content = await Bun.file(`${DATA_DIR}/${csvFile}`).text();
    const lines = content.trim().split("\n");

    // Skip header
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      if (!line) continue;
      const [category, countStr] = line.split(",");
      if (!category || !countStr) continue;
      const count = parseInt(countStr, 10);
      if (!isNaN(count)) {
        const current = categoryTotals.get(category) || 0;
        categoryTotals.set(category, current + count);
      }
    }
  }

  // Sort by count descending and take top 10
  const aggregated = Array.from(categoryTotals.entries())
    .map(([category, num_questions]) => ({ category, num_questions }))
    .sort((a, b) => b.num_questions - a.num_questions);

  const top10 = aggregated.slice(0, 10);

  const stats = [
    "category,num_questions",
    ...top10.map((row) => `${row.category},${row.num_questions}`),
  ];

  await Bun.write(`${DATA_DIR}/categories_stats.csv`, stats.join("\n"));
  console.log(
    `Aggregated ${csvFiles.length} files into ${DATA_DIR}/categories_stats.csv (top 10 categories)`
  );
  console.log("Top 10 categories:", top10);
}

async function main() {
  console.log("=== EXPERIMENTAL MODE: Auto-generated categories ===\n");
  
  await ensureDataDir();
  
  console.log("Loading previous state...");
  const state = await loadState();
  console.log(
    `Previous state: ${state.totalQuestionsProcessed} questions processed`
  );
  if (state.lastProcessedTimestamp) {
    console.log(`Last processed timestamp: ${state.lastProcessedTimestamp}`);
  }

  console.log("\nFetching new Langfuse data...");
  const traces = await fetchNewTraces(state.lastProcessedTimestamp);
  console.log("Fetched traces:", traces.length);

  if (traces.length === 0) {
    console.log("No new traces to process");
    await aggregateAllCsvFiles();
    return;
  }

  const questions = traces
    .map((trace) => trace.input?.query)
    .filter((q): q is string => q !== undefined);

  console.log("New questions to classify:", questions.length);

  if (questions.length === 0) {
    console.log("No new questions to classify");
    // Update state with latest timestamp anyway
    const latestTimestamp = traces[0]?.timestamp;
    if (latestTimestamp) {
      state.lastProcessedTimestamp = latestTimestamp;
      await saveState(state);
    }
    await aggregateAllCsvFiles();
    return;
  }

  const client = new OpenAI();

  // Divides questions into batches
  const batches: string[][] = [];
  for (let i = 0; i < questions.length; i += BATCH_SIZE) {
    batches.push(questions.slice(i, i + BATCH_SIZE));
  }

  console.log(
    `Processing ${batches.length} batches of ~${BATCH_SIZE} questions each...`
  );

  // Classifies each batch
  const allClassified: { category: string; question: string }[] = [];
  let batchIndex = 0;
  for (const batch of batches) {
    batchIndex++;
    console.log(`Processing batch ${batchIndex}/${batches.length}...`);
    const batchResults = await classifyBatch(client, batch);
    allClassified.push(...batchResults);
    console.log(
      `  Classified ${batchResults.length}/${batch.length} questions in this batch`
    );
  }

  console.log(
    `\nTotal classified: ${allClassified.length}/${questions.length} questions`
  );

  // Aggregates by category
  const categoryMap = new Map<string, number>();
  for (const item of allClassified) {
    const current = categoryMap.get(item.category) || 0;
    categoryMap.set(item.category, current + 1);
  }

  // Converts to array and sorts by number of questions (descending)
  const data = Array.from(categoryMap.entries())
    .map(([category, num_questions]) => ({ category, num_questions }))
    .sort((a, b) => b.num_questions - a.num_questions);

  console.log("\n=== AUTO-GENERATED CATEGORIES ===");
  console.log("Stats data:", data);

  const stats = [
    "category,num_questions",
    ...data.map((row) => `${row.category},${row.num_questions}`),
  ];

  // Save with date in filename
  const dateString = getDateString();
  const dailyFile = `${DATA_DIR}/categories_stats_${dateString}.csv`;
  await Bun.write(dailyFile, stats.join("\n"));
  console.log(`\nSaved to ${dailyFile}`);

  // Update state
  const latestTimestamp = traces[0]?.timestamp;
  if (latestTimestamp) {
    state.lastProcessedTimestamp = latestTimestamp;
  }
  state.totalQuestionsProcessed += questions.length;
  await saveState(state);
  console.log(`\nState updated: ${state.totalQuestionsProcessed} total questions processed`);

  // Aggregate all CSV files
  await aggregateAllCsvFiles();
}

(async () => {
  await main();
})();

