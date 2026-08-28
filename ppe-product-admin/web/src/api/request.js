import axios from "axios";
import { ElMessage } from "element-plus";

const request = axios.create({
  baseURL: "/api",
  timeout: 30000,
  withCredentials: true
});

function cookieValue(name) {
  if (typeof document === "undefined") return "";
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split(";")
    .map(value => value.trim())
    .find(value => value.startsWith(prefix));
  if (!item) return "";
  try {
    return decodeURIComponent(item.slice(prefix.length));
  } catch {
    return item.slice(prefix.length);
  }
}

request.interceptors.request.use(
  (config) => {
    const method = String(config.method || "get").toLowerCase();
    if (!["get", "head", "options"].includes(method)) {
      const csrfToken = cookieValue("ppe_csrf");
      if (csrfToken) config.headers["X-CSRF-Token"] = csrfToken;
    }
    return config;
  },

  (error) => {
    return Promise.reject(error);
  }
);

request.interceptors.response.use(
  (response) => {
    return response.data;
  },

  (error) => {
    const status = error?.response?.status;

    if (
      status === 401 &&
      typeof window !== "undefined" &&
      !String(error?.config?.url || "").includes("/auth/login")
    ) {
      window.dispatchEvent(new CustomEvent("iam:unauthorized"));
    }

    if (error?.config?.silentError) {
      return Promise.reject(error);
    }

    const message =
      error?.response?.data?.message ||
      error?.response?.data?.msg ||
      error?.message ||
      "网络请求失败";

    if (status === 403) {
      ElMessage.error(message || "没有执行该操作的权限");
    } else if (status === 404) {
      ElMessage.error("请求的接口不存在");
    } else if (status === 429) {
      ElMessage.warning(message);
    } else if (status === 503) {
      ElMessage.error(message || "服务尚未配置完成");
    } else if (status === 500) {
      ElMessage.error("服务器内部错误");
    } else {
      ElMessage.error(message);
    }

    return Promise.reject(error);
  }
);

export default request;
