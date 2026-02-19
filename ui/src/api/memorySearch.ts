import axios from 'axios'

const API_BASE = 'http://localhost:8000/api'

export interface MemorySearchConfig {
  enabled: boolean
  embedding_provider: string   // local | auto | openai | litellm | custom | noop
  embedding_model: string
  embedding_device: string     // auto | cpu | cuda
  embedding_api_key: string
  embedding_api_base: string
  embedding_dimension: number
  embedding_batch_size: number
  vector_weight: number        // 0~1
  keyword_weight: number       // 0~1
  max_chunk_size: number
  min_chunk_size: number
  top_k: number
  min_score: number            // 0~1
  auto_index_on_start: boolean
}

export async function getMemorySearchConfig(): Promise<MemorySearchConfig> {
  const response = await axios.get(`${API_BASE}/config/memory-search`)
  return response.data
}

export async function updateMemorySearchConfig(config: MemorySearchConfig): Promise<void> {
  await axios.post(`${API_BASE}/config/memory-search`, config)
}
