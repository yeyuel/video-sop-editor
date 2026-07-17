type HeaderReader = Pick<Headers, "get">;

function firstHeaderValue(value: string | null): string {
  return value?.split(",", 1)[0]?.trim() ?? "";
}

export function createPublicRequestUrl(
  requestUrl: string,
  headers: HeaderReader,
  pathname: string
): URL {
  const url = new URL(requestUrl);
  const forwardedHost = firstHeaderValue(headers.get("x-forwarded-host"));
  const requestHost = firstHeaderValue(headers.get("host"));
  const publicHost = forwardedHost || requestHost;

  if (publicHost) {
    url.port = "";
    url.host = publicHost;
  }

  const forwardedProtocol = firstHeaderValue(headers.get("x-forwarded-proto")).toLowerCase();
  if (forwardedProtocol === "http" || forwardedProtocol === "https") {
    url.protocol = `${forwardedProtocol}:`;
  }

  url.pathname = pathname;
  url.search = "";
  url.hash = "";
  return url;
}
