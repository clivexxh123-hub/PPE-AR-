import request from "./request";

export function loginWithPassword(phone, password) {
  return request.post("/auth/login", { phone, password }, { silentError: true });
}

export function getCurrentUser() {
  return request.get("/auth/me", { silentError: true });
}

export function logoutSession() {
  return request.post("/auth/logout");
}

export function getIamUsers() {
  return request.get("/iam/users");
}

export function getIamOrgUnits() {
  return request.get("/iam/org-units");
}

export function getIamRoles() {
  return request.get("/iam/roles");
}

export function createIamUser(payload) {
  return request.post("/iam/users", payload);
}

export function updateIamUser(userId, payload) {
  return request.patch(`/iam/users/${encodeURIComponent(userId)}`, payload);
}
