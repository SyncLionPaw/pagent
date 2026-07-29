import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import css from "highlight.js/lib/languages/css";
import go from "highlight.js/lib/languages/go";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import ruby from "highlight.js/lib/languages/ruby";
import rust from "highlight.js/lib/languages/rust";
import scss from "highlight.js/lib/languages/scss";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

// 注册 artifact 语言映射用得到的高亮语言。toml 没有官方语法，用 ini 近似。
for (const [name, lang] of [
  ["bash", bash],
  ["c", c],
  ["cpp", cpp],
  ["css", css],
  ["go", go],
  ["ini", ini],
  ["toml", ini],
  ["java", java],
  ["javascript", javascript],
  ["json", json],
  ["markdown", markdown],
  ["python", python],
  ["ruby", ruby],
  ["rust", rust],
  ["scss", scss],
  ["sql", sql],
  ["typescript", typescript],
  ["xml", xml],
  ["yaml", yaml],
] as const) {
  hljs.registerLanguage(name, lang);
}

/** 代码文本做语法高亮。语言已知且被 highlight.js 支持时按语言高亮，否则自动识别。 */
export function highlightCode(text: string, language?: string): string {
  if (language && hljs.getLanguage(language)) {
    return hljs.highlight(text, { language }).value;
  }
  return hljs.highlightAuto(text).value;
}
