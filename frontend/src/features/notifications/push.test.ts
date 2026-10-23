import { describe, expect, it } from "vitest";
import { urlBase64ToUint8Array } from "./push";

describe("urlBase64ToUint8Array", () => {
  it("decodes base64url without padding", () => {
    // "hello?>" in base64url is aGVsbG8_Pg
    expect(Array.from(urlBase64ToUint8Array("aGVsbG8_Pg"))).toEqual(Array.from(new TextEncoder().encode("hello?>")));
  });

  it("reads a VAPID-sized key back to 65 bytes starting with 0x04", () => {
    const bytes = new Uint8Array(65).fill(7);
    bytes[0] = 4;
    const encoded = btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const decoded = urlBase64ToUint8Array(encoded);
    expect(decoded).toHaveLength(65);
    expect(decoded[0]).toBe(4);
  });
});
