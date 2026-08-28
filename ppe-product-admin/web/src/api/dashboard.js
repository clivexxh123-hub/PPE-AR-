import request from "./request";

export function getDashboardStatistics(days = 30, options = {}) {
  return request.get("/dashboard/statistics", {
    params: { days },
    ...options
  });
}
