export const DATA_DIR = "data";
export const STATE_FILE = `${DATA_DIR}/fetch_state.json`;
export const UNCATEGORIZED_FILE = `${DATA_DIR}/uncategorized_questions.csv`;
export const BATCH_SIZE = 30;

export const CATEGORIES = [
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
  "Misura 1.1",
  "Misura 1.2",
  "Misura 1.4.1",
  "PA Digitale 2026",
  "U.S3",
  "Altro",
] as const;

export type Category = (typeof CATEGORIES)[number];

