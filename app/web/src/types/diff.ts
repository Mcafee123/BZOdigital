export interface DiffPayload {
  unified_diff: string
  left_filename: string
  right_filename: string
}

export type DiffMode = 'split' | 'unified'
