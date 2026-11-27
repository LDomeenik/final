// 모든 API 요청이 거치는 공통 설정
import axios from 'axios'

import { clearToken, getToken } from './token'

// 백엔드 주소와 기본 설정
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000, // 캡처 인식(최대 20초)을 고려해 30초
})

// 요청을 보내기 전: 토큰이 있으면 헤더에 붙임
client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})

// 응답을 받은 뒤: 에러를 API 명세의 형식으로 정리
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // 서버가 보낸 {"error": {code, message, fields}}를 꺼냄
    const apiError = error.response?.data?.error ?? {
      code: 'network_error',
      message: '서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.',
    }

    // 401: 토큰이 없거나 잘못됨 → 저장된 토큰 삭제
    // (로그인 화면으로 이동하는 처리는 로그인 화면을 만들 때 추가)
    if (error.response?.status === 401) {
      clearToken()
    }

    return Promise.reject({ status: error.response?.status ?? 0, ...apiError })
  },
)

export default client
