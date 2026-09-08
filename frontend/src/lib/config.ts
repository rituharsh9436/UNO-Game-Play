/**
 * Resolves Backend API and WebSocket URLs.
 * In production / Vercel, uses NEXT_PUBLIC_API_URL and NEXT_PUBLIC_WS_URL.
 * In local development, falls back cleanly to http://127.0.0.1:8000.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000";
