import axios from "axios";

const apiBaseUrl = import.meta.env?.VITE_API_URL ?? (import.meta.env?.DEV ? "http://localhost:8000/api" : "/api");

export const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 10_000
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("firesight_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const message = error.response?.data?.message ?? error.message ?? "Network request failed";
    return Promise.reject({ ...error, status, userMessage: message });
  }
);
