// 서버 상태 확인 API
import client from './client'

// GET /health/ → { status: 'ok' }
export async function getHealth() {
  const { data } = await client.get('/health/')
  return data
}
