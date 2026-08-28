const assetHost = String(
  import.meta.env.VITE_FILE_HOST || ""
).replace(/\/+$/, "");

export function resolveAssetUrl(value) {
  const path = String(value || "").trim();

  if (!path) {
    return "";
  }

  if (/^(?:https?:|data:|blob:)/i.test(path)) {
    return path;
  }

  const localAssetPrefixes = [
    "/uploads/generation-demo/",
    "/uploads/models/",
    "/uploads/scenes/"
  ];

  if (localAssetPrefixes.some((prefix) => path.startsWith(prefix))) {
    return path;
  }

  const normalizedPath = path.startsWith("/")
    ? path
    : `/${path}`;

  return assetHost
    ? `${assetHost}${normalizedPath}`
    : normalizedPath;
}

export function repairMojibake(value) {
  if (typeof value !== "string" || !value) {
    return value;
  }

  const characters = Array.from(value);

  if (characters.some((character) => character.charCodeAt(0) > 255)) {
    return value;
  }

  try {
    const bytes = Uint8Array.from(
      characters,
      (character) => character.charCodeAt(0)
    );

    return new TextDecoder("utf-8", {
      fatal: true
    }).decode(bytes);
  } catch {
    return value;
  }
}

export function normalizeLogo(logo = {}) {
  const name = repairMojibake(
    logo.logo_name || logo.name || ""
  );

  return {
    ...logo,
    logo_name: name,
    name,
    image: resolveAssetUrl(
      logo.logo_url || logo.image
    )
  };
}

export function normalizeImageResource(resource = {}, nameField = "name") {
  const name = repairMojibake(
    resource[nameField] || resource.name || ""
  );

  return {
    ...resource,
    [nameField]: name,
    name,
    image_name: repairMojibake(resource.image_name || ""),
    image: resolveAssetUrl(
      resource.image_url || resource.image
    )
  };
}
