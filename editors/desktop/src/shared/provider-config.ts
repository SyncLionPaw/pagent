export const DEFAULT_MODEL = "deepseek-v4-flash";
const DEFAULT_PROVIDER_NAME = "deepseek";
const DEFAULT_PROVIDER_KIND = "deepseek";

export type ProviderSetup = {
  apiKey: string;
  model: string;
  baseUrl?: string;
};

export function providerFieldFromToml(text: string, field: string): string {
  const legacy = fieldFromSection(text, "provider", field);
  if (legacy) {
    return legacy;
  }
  const selected = fieldFromSection(text, "agent", "provider");
  if (!selected) {
    return "";
  }
  return fieldFromSection(text, `provider.${selected}`, field);
}

function fieldFromSection(text: string, section: string, field: string): string {
  const range = sectionRange(text, section);
  if (!range) {
    return "";
  }
  const [start, end] = range;
  const match = text
    .slice(start, end)
    .match(new RegExp(`^[ \\t]*${field}[ \\t]*=[ \\t]*(.*)$`, "m"));
  if (!match) {
    return "";
  }
  let raw = match[1].trim();
  if (raw.startsWith('"') && raw.endsWith('"')) {
    raw = raw.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  } else if (raw.startsWith("'") && raw.endsWith("'")) {
    raw = raw.slice(1, -1);
  }
  return raw.trim();
}

function tomlEscape(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function sectionRange(text: string, section: string): [number, number] | undefined {
  const pattern = new RegExp(`^\\[${section.replace(".", "\\.")}\\]\\s*$`, "m");
  const match = pattern.exec(text);
  if (!match) {
    return undefined;
  }
  const start = match.index + match[0].length;
  const next = /^\[/m.exec(text.slice(start));
  return [start, next ? start + next.index : text.length];
}

function upsertSectionField(
  text: string,
  section: string,
  field: string,
  value: string,
): string {
  const keyLine = `${field} = "${tomlEscape(value)}"`;
  const range = sectionRange(text, section);
  if (!range) {
    const suffix = text.endsWith("\n") || !text ? "" : "\n";
    return text + suffix + `\n[${section}]\n${keyLine}\n`;
  }
  const [start, end] = range;
  const block = text.slice(start, end);
  const pattern = new RegExp(`^[ \\t]*${field}[ \\t]*=[ \\t]*.*$`, "m");
  if (pattern.test(block)) {
    return text.slice(0, start) + block.replace(pattern, keyLine) + text.slice(end);
  }
  return text.slice(0, start) + "\n" + keyLine + text.slice(start);
}

function removeSectionField(text: string, section: string, field: string): string {
  const range = sectionRange(text, section);
  if (!range) {
    return text;
  }
  const [start, end] = range;
  const block = text
    .slice(start, end)
    .replace(new RegExp(`^[ \\t]*${field}[ \\t]*=[ \\t]*.*\\n?`, "m"), "");
  return text.slice(0, start) + block + text.slice(end);
}

function writeProvider(text: string, setup: ProviderSetup): string {
  const baseUrl = setup.baseUrl?.trim() ?? "";
  if (/^\[provider\]\s*$/m.test(text)) {
    let next = upsertProviderField(text, "api_key", setup.apiKey.trim());
    next = upsertProviderField(next, "model", setup.model.trim() || DEFAULT_MODEL);
    return baseUrl
      ? upsertProviderField(next, "base_url", baseUrl)
      : removeProviderField(next, "base_url");
  }

  const section = `provider.${DEFAULT_PROVIDER_NAME}`;
  let next = upsertSectionField(text, section, "kind", DEFAULT_PROVIDER_KIND);
  next = upsertSectionField(next, section, "api_key", setup.apiKey.trim());
  next = upsertSectionField(
    next,
    section,
    "model",
    setup.model.trim() || DEFAULT_MODEL,
  );
  next = baseUrl
    ? upsertSectionField(next, section, "base_url", baseUrl)
    : removeSectionField(next, section, "base_url");
  return upsertSectionField(next, "agent", "provider", DEFAULT_PROVIDER_NAME);
}

export function upsertProviderField(
  text: string,
  field: string,
  value: string,
): string {
  return upsertSectionField(text, "provider", field, value);
}

export function removeProviderField(text: string, field: string): string {
  return removeSectionField(text, "provider", field);
}

export function buildProviderToml(setup: ProviderSetup): string {
  return writeProvider("# pagent home 配置\n", setup);
}

export function mergeProviderToml(existing: string, setup: ProviderSetup): string {
  return writeProvider(existing.trim() ? existing : "# pagent home 配置\n", setup);
}
