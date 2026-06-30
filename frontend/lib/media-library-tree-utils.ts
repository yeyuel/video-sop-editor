import type { MediaLibraryNode, MediaLibraryScanResult } from "@/lib/browser-api";

export function collectMediaFiles(node: MediaLibraryNode): MediaLibraryNode[] {
  if (node.nodeType === "file") {
    return [node];
  }
  return (node.children ?? []).flatMap(collectMediaFiles);
}

export function markPathHasAsset(
  node: MediaLibraryNode,
  relativePath: string
): MediaLibraryNode {
  if (node.nodeType === "file" && node.relativePath === relativePath) {
    return { ...node, hasAsset: true };
  }
  if (!node.children?.length) {
    return node;
  }
  return {
    ...node,
    children: node.children.map((child) => markPathHasAsset(child, relativePath))
  };
}

export function patchScanResultHasAsset(
  scanResult: MediaLibraryScanResult,
  relativePath: string
): MediaLibraryScanResult {
  return {
    ...scanResult,
    tree: markPathHasAsset(scanResult.tree, relativePath)
  };
}

export function findNextUnrecordedFile(
  tree: MediaLibraryNode,
  afterPath: string
): MediaLibraryNode | null {
  const files = collectMediaFiles(tree);
  const currentIndex = files.findIndex((file) => file.relativePath === afterPath);
  const startIndex = currentIndex >= 0 ? currentIndex + 1 : 0;

  for (let index = startIndex; index < files.length; index += 1) {
    if (!files[index].hasAsset) {
      return files[index];
    }
  }

  for (let index = 0; index < startIndex; index += 1) {
    if (!files[index].hasAsset && files[index].relativePath !== afterPath) {
      return files[index];
    }
  }

  return null;
}
