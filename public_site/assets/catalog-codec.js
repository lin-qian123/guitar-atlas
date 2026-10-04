"use strict";

// Lossless browser transport; ordinary legacy catalog objects pass through.
const GuitarCatalogCodec = (() => {
  const CODEC = "guitar-atlas-catalog-v1";
  const LIMIT = 128 * 1024 * 1024;

  function unpack(packed) {
    if (!packed || Object.keys(packed).sort().join() !== "shapes,strings,value"
        || !Array.isArray(packed.strings) || packed.strings.some(value => typeof value !== "string")
        || !Array.isArray(packed.shapes) || packed.shapes.some(keys => !Array.isArray(keys)
          || keys.some(key => typeof key !== "string") || new Set(keys).size !== keys.length)) {
      throw new Error("invalid catalog transport tables");
    }
    const {strings, shapes} = packed;
    const usedStrings = new Set();
    const usedShapes = new Set();
    function decode(value) {
      if (typeof value === "number") {
        if (!Number.isInteger(value) || value < 0 || value >= strings.length) throw new Error("invalid catalog string reference");
        usedStrings.add(value);
        return strings[value];
      }
      if (value === null || typeof value === "string" || typeof value === "boolean") return value;
      if (!Array.isArray(value) || !value.length) throw new Error("invalid catalog transport value");
      if (value[0] === 0) return value.slice(1).map(decode);
      if (value[0] === 2 && value.length === 2 && typeof value[1] === "number" && Number.isFinite(value[1])) return value[1];
      if (value[0] !== 1 || !Number.isInteger(value[1]) || !shapes[value[1]]) throw new Error("invalid catalog transport tag");
      usedShapes.add(value[1]);
      const keys = shapes[value[1]];
      if (value.length !== keys.length + 2) throw new Error("catalog transport object arity mismatch");
      const result = {};
      keys.forEach((key, index) => {
        const decoded = decode(value[index + 2]);
        if (key === "__proto__") Object.defineProperty(result, key, {value: decoded, enumerable: true, writable: true, configurable: true});
        else result[key] = decoded;
      });
      return result;
    }
    const result = decode(packed.value);
    if (usedStrings.size !== strings.length || usedShapes.size !== shapes.length) throw new Error("catalog transport contains unused table entries");
    return result;
  }

  async function decode(envelope) {
    if (!envelope || typeof envelope !== "object" || !("codec" in envelope)) return envelope;
    if (Object.keys(envelope).sort().join() !== "codec,encoding,payload,uncompressed_bytes"
        || envelope.codec !== CODEC || envelope.encoding !== "gzip-base64"
        || !Number.isInteger(envelope.uncompressed_bytes) || envelope.uncompressed_bytes <= 0
        || envelope.uncompressed_bytes > LIMIT || typeof envelope.payload !== "string") {
      throw new Error("unsupported catalog transport");
    }
    if (typeof DecompressionStream !== "function") {
      throw new Error("当前浏览器不支持压缩目录，请使用新版 Safari、Chrome 或 Edge。");
    }
    const binary = atob(envelope.payload);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    const reader = stream.getReader();
    const decoder = new TextDecoder("utf-8", {fatal: true});
    const parts = [];
    let length = 0;
    try {
      for (;;) {
        const {done, value} = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > envelope.uncompressed_bytes) throw new Error("catalog transport expanded size mismatch");
        parts.push(decoder.decode(value, {stream: true}));
      }
      if (length !== envelope.uncompressed_bytes) throw new Error("catalog transport expanded size mismatch");
      parts.push(decoder.decode());
      return unpack(JSON.parse(parts.join("")));
    } catch (error) {
      await reader.cancel().catch(() => {});
      throw error;
    } finally {
      reader.releaseLock();
    }
  }

  return {decode, unpack};
})();

if (typeof window !== "undefined") window.GuitarCatalogCodec = GuitarCatalogCodec;
if (typeof module !== "undefined" && module.exports) module.exports = GuitarCatalogCodec;
