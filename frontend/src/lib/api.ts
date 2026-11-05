let csrf = "";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    ...init,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrf,
      ...init?.headers,
    },
  });
  const data = await response.json().catch(() => ({
    detail: "The service could not be reached. Please retry.",
  }));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string" ? data.detail : JSON.stringify(data),
    );
  return data;
}

export function setCSRF(value: string) {
  csrf = value;
}
