export interface DiffPayload {
  unified_diff: string
  left_filename: string
  right_filename: string
}

export type DiffMode = 'split' | 'unified'

export interface SectionRow {
  key: string
  title_alt: string | null
  title_neu: string | null
  alt: string
  neu: string
  added: boolean
  removed: boolean
}

export interface SectionsPayload {
  alt_filename: string
  neu_filename: string
  rows: SectionRow[]
}
