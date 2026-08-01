// Backend Configuration

const API_BASE = (typeof window !== "undefined" && window.location.origin && !window.location.origin.includes("file://"))
    ? window.location.origin + "/api"
    : "http://localhost:8000/api";

const STORAGE_KEYS = {
    TOKEN: "conceptx_token",
    USER: "conceptx_user",
    SESSION: "conceptx_session"
};