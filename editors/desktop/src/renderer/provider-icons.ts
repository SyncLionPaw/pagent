import baichuanIcon from "@lobehub/icons-static-svg/icons/baichuan-color.svg";
import chatGlmIcon from "@lobehub/icons-static-svg/icons/chatglm-color.svg";
import claudeIcon from "@lobehub/icons-static-svg/icons/claude-color.svg";
import cohereIcon from "@lobehub/icons-static-svg/icons/cohere-color.svg";
import deepSeekIcon from "@lobehub/icons-static-svg/icons/deepseek-color.svg";
import doubaoIcon from "@lobehub/icons-static-svg/icons/doubao-color.svg";
import geminiIcon from "@lobehub/icons-static-svg/icons/gemini-color.svg";
import grokIcon from "@lobehub/icons-static-svg/icons/grok.svg";
import metaIcon from "@lobehub/icons-static-svg/icons/meta-color.svg";
import minimaxIcon from "@lobehub/icons-static-svg/icons/minimax-color.svg";
import mistralIcon from "@lobehub/icons-static-svg/icons/mistral-color.svg";
import moonshotIcon from "@lobehub/icons-static-svg/icons/moonshot.svg";
import ollamaIcon from "@lobehub/icons-static-svg/icons/ollama.svg";
import openAiIcon from "@lobehub/icons-static-svg/icons/openai.svg";
import openRouterIcon from "@lobehub/icons-static-svg/icons/openrouter-color.svg";
import qwenIcon from "@lobehub/icons-static-svg/icons/qwen-color.svg";
import yiIcon from "@lobehub/icons-static-svg/icons/yi-color.svg";

const PROVIDER_ICONS: Array<{ pattern: RegExp; svg: string }> = [
  { pattern: /openrouter/, svg: openRouterIcon },
  { pattern: /deepseek/, svg: deepSeekIcon },
  { pattern: /claude|anthropic/, svg: claudeIcon },
  { pattern: /gemini|gemma/, svg: geminiIcon },
  { pattern: /qwen|qwq/, svg: qwenIcon },
  { pattern: /doubao|(^|[/_-])seed([/_-]|$)/, svg: doubaoIcon },
  { pattern: /moonshot|kimi/, svg: moonshotIcon },
  { pattern: /minimax|abab/, svg: minimaxIcon },
  { pattern: /chatglm|(^|[/_-])glm|zhipu/, svg: chatGlmIcon },
  { pattern: /grok|(^|[/_-])xai([/_-]|$)/, svg: grokIcon },
  { pattern: /mistral|mixtral|codestral/, svg: mistralIcon },
  { pattern: /llama|(^|[/_-])meta([/_-]|$)/, svg: metaIcon },
  { pattern: /cohere|command-r/, svg: cohereIcon },
  { pattern: /baichuan/, svg: baichuanIcon },
  { pattern: /(^|[/_-])yi([/_-]|$)/, svg: yiIcon },
  { pattern: /ollama/, svg: ollamaIcon },
  { pattern: /gpt|chatgpt|(^|[/_-])o[134]([/_-]|$)|codex|openai/, svg: openAiIcon },
];

export function providerIconForModel(model: string): string | undefined {
  const normalized = model.trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }
  return PROVIDER_ICONS.find(({ pattern }) => pattern.test(normalized))?.svg;
}
