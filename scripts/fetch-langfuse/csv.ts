import { readdir } from "node:fs/promises";
import { DATA_DIR, UNCATEGORIZED_FILE } from "./config";

export function getDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}_${month}_${day}`;
}

export function escapeCSV(str: string): string {
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export async function saveUncategorizedQuestions(
  questions: { question: string; date: string }[]
): Promise<void> {
  if (questions.length === 0) return;

  let existingContent = "";
  const file = Bun.file(UNCATEGORIZED_FILE);

  if (await file.exists()) {
    existingContent = await file.text();
  } else {
    existingContent = "domanda,data\n";
  }

  const newLines = questions
    .map((q) => `${escapeCSV(q.question)},${q.date}`)
    .join("\n");

  await Bun.write(UNCATEGORIZED_FILE, existingContent + newLines + "\n");
  console.log(
    `\nSaved ${questions.length} uncategorized questions to ${UNCATEGORIZED_FILE}`
  );
}

export async function saveDailyStats(
  data: { category: string; num_questions: number }[],
  dateString: string
): Promise<void> {
  const stats = [
    "category,num_questions",
    ...data.map((row) => `${row.category},${row.num_questions}`),
  ];

  const dailyFile = `${DATA_DIR}/categories_stats_${dateString}.csv`;
  await Bun.write(dailyFile, stats.join("\n"));
  console.log(`\nSaved to ${dailyFile}`);
}

export async function aggregateAllCsvFiles(): Promise<void> {
  console.log("\nAggregating all CSV files...");

  const files = await readdir(DATA_DIR);
  const csvFiles = files.filter(
    (f) => f.startsWith("categories_stats_") && f.endsWith(".csv")
  );

  if (csvFiles.length === 0) {
    console.log("No dated CSV files found to aggregate");
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

  // Sort by count descending
  const aggregated = Array.from(categoryTotals.entries())
    .map(([category, num_questions]) => ({ category, num_questions }))
    .sort((a, b) => b.num_questions - a.num_questions);

  const stats = [
    "category,num_questions",
    ...aggregated.map((row) => `${row.category},${row.num_questions}`),
  ];

  await Bun.write(`${DATA_DIR}/categories_stats.csv`, stats.join("\n"));
  console.log(
    `Aggregated ${csvFiles.length} files into data/categories_stats.csv`
  );
  console.log("Aggregated totals:", aggregated);
}

