const TOKEN_KEY = 'llm_deploy_token'
const USER_KEY = 'llm_deploy_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getRole() {
  const u = getUser()
  return u ? u.role : null
}

export function isLoggedIn() {
  return !!getToken()
}
