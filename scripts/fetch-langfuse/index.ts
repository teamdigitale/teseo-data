import OpenAI from "openai";
import { BATCH_SIZE } from "./config";
import { loadState, saveState } from "./state";
import { fetchNewTraces } from "./langfuse";
import { classifyBatch } from "./classifier";
import type { ClassifiedQuestion } from "./classifier";
import {
  getDateString,
  saveUncategorizedQuestions,
  saveDailyStats,
  aggregateAllCsvFiles,
} from "./csv";

async function main() {
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
  const allClassified: ClassifiedQuestion[] = [];
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

  // Extract and save "Altro" questions
  const dateString = getDateString();
  const uncategorized = allClassified
    .filter((item) => item.category === "Altro")
    .map((item) => ({ question: item.question, date: dateString }));

  if (uncategorized.length > 0) {
    await saveUncategorizedQuestions(uncategorized);
  }

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

  console.log("\nStats data:", data);

  // Save daily stats
  await saveDailyStats(data, dateString);

  // Update state
  const latestTimestamp = traces[0]?.timestamp;
  if (latestTimestamp) {
    state.lastProcessedTimestamp = latestTimestamp;
  }
  state.totalQuestionsProcessed += questions.length;
  await saveState(state);
  console.log(
    `\nState updated: ${state.totalQuestionsProcessed} total questions processed`
  );

  // Aggregate all CSV files
  await aggregateAllCsvFiles();
}

(async () => {
  await main();
})();

