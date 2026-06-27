const DEFAULT_BACKEND_API_BASE = "http://127.0.0.1:8000/api/v1";
const BROWSER_API_BASE = "/api/v1";

export function getBrowserApiBaseUrl(): string {
  // Browser must stay same-origin: session cookie lives on the Next.js host (:3000),
  // not on FastAPI (:8000). The /api/v1 route handler forwards X-Session-Token.
  if (typeof window !== "undefined") {
    return BROWSER_API_BASE;
  }

  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_BACKEND_API_BASE;
}

export function getServerApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_BACKEND_API_BASE;
}

export async function readApiErrorDetail(response: Response): Promise<string> {
  let detail = `Request failed: ${response.status}`;
  try {
    const payload = (await response.json()) as {
      detail?: string | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
    if (Array.isArray(payload.detail) && payload.detail.length > 0) {
      const message = payload.detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join("；");
      if (message) {
        return message;
      }
    }
  } catch {
    // ignore json parse errors
  }
  return detail;
}
