export function normalizeMediaRootPath(path: string): string {
  return path.replace(/\\/g, "/").trim().replace(/\/+$/, "").toLowerCase();
}

export function mediaRootsMatch(left: string, right: string): boolean {
  return normalizeMediaRootPath(left) === normalizeMediaRootPath(right);
}
