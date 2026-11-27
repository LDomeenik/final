// 로그인 토큰 저장소
// 토큰을 어디에 저장할지는 이 파일에서만 정함 (나중에 JWT로 바꿀 때 이 파일과 client.js만 수정)

const TOKEN_KEY = 'auth_token'

// 저장된 토큰 꺼내기 (없으면 null)
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

// 로그인·회원가입 성공 시 토큰 저장
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

// 로그아웃·토큰 만료 시 토큰 삭제
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}
