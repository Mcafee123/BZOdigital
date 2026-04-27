export interface CrossReferenceEntry {
  source_file: string
  source_labels: string[]
  citation_text: string
  paragraph: string
}

export interface CrossReferencesPayload {
  municipality: string
  bzo_filename: string
  bzo_markdown: string
  articles: string[]
  cross_references: Record<string, CrossReferenceEntry[]>
}
