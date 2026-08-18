import axios from "axios";
import { ElMessage } from "element-plus";

const request = axios.create({
  baseURL: "/api",
  timeout: 30000
});

request.interceptors.request.use(
  (config) => {
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

    const message =
      error?.response?.data?.message ||
      error?.response?.data?.msg ||
      error?.message ||
      "网络请求失败";

    if (status === 404) {
      ElMessage.error("请求的接口不存在");
    } else if (status === 500) {
      ElMessage.error("服务器内部错误");
    } else {
      ElMessage.error(message);
    }

    return Promise.reject(error);
  }
);

export default request;
