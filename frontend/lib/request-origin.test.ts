import { describe, expect, it } from "vitest";

import { createPublicRequestUrl } from "@/lib/request-origin";

function headers(values: Record<string, string>): Pick<Headers, "get"> {
  return {
    get(name: string) {
      return values[name.toLowerCase()] ?? null;
    }
  };
}

describe("createPublicRequestUrl", () => {
  it("replaces an internal listener host with the browser host", () => {
    const url = createPublicRequestUrl(
      "http://0.0.0.0:3100/api/auth/logout",
      headers({ host: "127.0.0.1:3100" }),
      "/login"
    );

    expect(url.toString()).toBe("http://127.0.0.1:3100/login");
  });

  it("prefers reverse-proxy forwarding headers", () => {
    const url = createPublicRequestUrl(
      "http://0.0.0.0:3100/projects",
      headers({
        host: "127.0.0.1:3100",
        "x-forwarded-host": "editor.example.com",
        "x-forwarded-proto": "https"
      }),
      "/login"
    );

    expect(url.toString()).toBe("https://editor.example.com/login");
  });
});
