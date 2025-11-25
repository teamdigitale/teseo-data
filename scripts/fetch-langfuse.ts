import { LangfuseClient } from "@langfuse/client";
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const publicKey = process.env.LANGFUSE_PUBLIC_KEY;
const secretKey = process.env.LANGFUSE_SECRET_KEY;
const baseUrl = "https://cloud.langfuse.com";
const langfuse = new LangfuseClient({
  publicKey,
  secretKey,
  baseUrl,
});

async function fetchLangfuseData(page: number, limit: number) {
  const response = await langfuse.api.trace.list({
    page: page,
    limit: limit,
  });
  return response;
}

async function fetchAllTraces() {
  let allTraces: any[] = [];
  let page = 1;
  const limit = 100; // Number of traces per page

  while (true) {
    const response = await fetchLangfuseData(page, limit);
    allTraces = [...allTraces, response.data];
    if (response.data.length < limit) {
      break; // No more pages to fetch
    }
    page++;
  }

  return allTraces.flat();
}

const BATCH_SIZE = 30; // Numero di domande per batch

const CATEGORIES = [
  "Scadenze e Tempistiche",
  "Asseverazione",
  "Contratti e Fornitori",
  "Gestione e Utilizzo Fondi",
  "FAQ e Manuali",
  "Migrazione e Cloud",
  "Candidature e Progetti",
  "Dichiarazioni e Documentazione",
  "Portali e Sistemi Digitali",
  "Ruoli e Governance",
  "Controlli e Verifiche",
  "Progetti e Status",
  "Linee Guida e Requisiti",
  "Pagamenti e Rimborsi",
  "Feedback e Suggerimenti",
] as const;

async function classifyBatch(
  client: OpenAI,
  questions: string[]
): Promise<{ category: string; question: string }[]> {
  const Results = z.object({
    results: z.array(
      z.object({
        category: z.enum(CATEGORIES),
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

Il tuo compito è assegnare a ciascuna domanda UNA delle seguenti categorie PREDEFINITE:
${CATEGORIES.map((c) => `- ${c}`).join("\n")}

REGOLE IMPORTANTI:
- Usa SOLO le categorie elencate sopra, esattamente come scritte
- Se una domanda NON rientra chiaramente in nessuna categoria, NON classificarla (omettila dal risultato)
- NON inventare nuove categorie
- NON usare "Altro" o categorie generiche`,
      },
      {
        role: "user",
        content: `Classifica le seguenti ${
          questions.length
        } domande nelle categorie predefinite:\n\n${questions
          .map((q, i) => `${i + 1}. ${q}`)
          .join("\n")}`,
      },
    ],
    text: { format: zodTextFormat(Results, "Results") },
  });

  // Flatten results: ogni domanda con la sua categoria
  const classified: { category: string; question: string }[] = [];
  for (const item of response?.output_parsed?.results || []) {
    for (const question of item.questions) {
      classified.push({ category: item.category, question });
    }
  }
  return classified;
}

async function main() {
  console.log("Fetching Langfuse data...");

  const traces = await fetchAllTraces();
  console.log("Fetched traces:", traces.length);

  const questions = traces
    .map((trace) => trace.input?.query)
    .filter((q): q is string => q !== undefined);

  console.log("Total questions to classify:", questions.length);

  const client = new OpenAI();

  // Dividi le domande in batch
  const batches: string[][] = [];
  for (let i = 0; i < questions.length; i += BATCH_SIZE) {
    batches.push(questions.slice(i, i + BATCH_SIZE));
  }

  console.log(
    `Processing ${batches.length} batches of ~${BATCH_SIZE} questions each...`
  );

  // Classifica ogni batch
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

  // Aggrega per categoria
  const categoryMap = new Map<string, number>();
  for (const item of allClassified) {
    const current = categoryMap.get(item.category) || 0;
    categoryMap.set(item.category, current + 1);
  }

  // Converti in array e ordina per numero di domande (decrescente)
  const data = Array.from(categoryMap.entries())
    .map(([category, num_questions]) => ({ category, num_questions }))
    .sort((a, b) => b.num_questions - a.num_questions);

  console.log("\nStats data:", data);

  const stats = [
    "category,num_questions",
    ...data.map((row) => `${row.category},${row.num_questions}`),
  ];

  await Bun.write(`data/categories_stats.csv`, stats.join("\n"));
  console.log("\nSaved to data/categories_stats.csv");
}

(async () => {
  await main();
})();
