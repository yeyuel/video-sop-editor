import { describe, expect, it } from "vitest";

import { mediaKindFromAssetType, mediaKindFromExtension } from "@/lib/media-preview-utils";

describe("mediaKindFromAssetType", () => {
  it("maps photo and drone video types", () => {
    expect(mediaKindFromAssetType("photo")).toBe("image");
    expect(mediaKindFromAssetType("drone_video")).toBe("video");
    expect(mediaKindFromAssetType("audio")).toBe("audio");
  });

  it("falls back to file extension", () => {
    expect(mediaKindFromAssetType("unknown", "clip/sample.mp4")).toBe("video");
    expect(mediaKindFromAssetType("unknown", "clip/sample.jpg")).toBe("image");
  });
});

describe("mediaKindFromExtension", () => {
  it("detects common media extensions", () => {
    expect(mediaKindFromExtension("folder/clip.MP4")).toBe("video");
    expect(mediaKindFromExtension("folder/cover.webp")).toBe("image");
    expect(mediaKindFromExtension("bgm/track.wav")).toBe("audio");
  });
});
