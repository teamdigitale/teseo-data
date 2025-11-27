import { STATE_FILE } from "./config";

export interface FetchState {
  lastProcessedTimestamp: string | null;
  totalQuestionsProcessed: number;
}

export async function loadState(): Promise<FetchState> {
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

export async function saveState(state: FetchState): Promise<void> {
  await Bun.write(STATE_FILE, JSON.stringify(state, null, 2));
}

