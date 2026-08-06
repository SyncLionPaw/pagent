// 视图层 —— 事件渲染（第 6 课起）。
//
// 把宿主转发来的 Wire 事件流渲染成 DOM。本模块只碰 DOM，不碰 vscode/Node。
//
// 事件语义（见 src/pagentv4/core/events.py）：
//   RunBegin   一轮运行开始（params.user_input）
//   TextDelta  正文增量（params.text），流式拼接
//   TurnResult 一个模型 turn 的完整结果（params.content 等）
//   RunEnd     整轮结束（params.stop_reason）
//
// 第 6 课：把 TextDelta 累积进一个 assistant 气泡，RunEnd 时定稿。
// 第 7 课：打字机式逐字追加 —— TextDelta 先进 pending 队列，用
//   requestAnimationFrame 每帧吐几个字符，让整段回复平滑滚出而非瞬间刷全。
//   正文展示同步走节流的增量 Markdown 渲染，避免等 RunEnd 才看到表格/列表/代码块。
// 第 8 课：ReasoningDelta 累积进一个可折叠的“思考”面板（<details>）。
// 第 11 课：ToolCallBegin/ToolResult 渲染成折叠“工具卡片” —— begin 建卡（显示
//   工具名 + 参数，标“运行中”），result 按 tool_call_id 回填结果并按 ok/fail 配色。
//
// UI 打磨：
//   - 运行态占位：用户发出到首个增量到达之间，在 assistant 位插一个“思考中”动画气泡，
//     首个 TextDelta/ReasoningDelta 或 RunEnd 时撤下，避免界面看起来卡住。
//   - 智能滚动：仅当用户已贴近底部时才自动跟随流式内容；上翻历史不被拽回。
//   - 角色标签 + 空状态：每条消息上方标 you/pagent；无消息时显示一句引导。

import DOMPurify from "dompurify";
import { marked } from "marked";

export type WireEventMessage = {
  method: string;
  params: Record<string, unknown>;
};

type SubagentPanel = {
  root: HTMLElement;
  icon: HTMLElement;
  preview: HTMLElement;
  status: HTMLElement;
};

// 贴底判定阈值（px）：与底部距离小于它就算“在底部”，继续自动跟随。
const STICK_THRESHOLD_PX = 80;
// Markdown 增量渲染节流间隔（ms）：降低 marked + DOMPurify 高频重跑造成的布局抖动。
const MARKDOWN_RENDER_INTERVAL_MS = 48;
const MESSAGE_COLLAPSED_HEIGHT_PX = 240;

type ChatRendererOptions = {
  collapseMessages?: boolean;
  stackActivities?: boolean;
  activityIcon?: () => HTMLElement;
  onArtifactOpen?: (path: string) => void;
  highlightCode?: (code: string, language?: string) => string;
  messageActions?: boolean;
  starterPrompts?: Array<{
    title: string;
    description: string;
    prompt: string;
  }>;
  onStarterPrompt?: (prompt: string) => void;
};

export class ChatRenderer {
  // 当前正在累积的 assistant 气泡正文元素；一轮结束后清空。
  private assistantBody: HTMLElement | undefined;
  // 已经吐到 DOM 上的文本。
  private assistantText = "";
  // 收到但尚未吐出的增量文本；打字机每帧从队头取几个字符。
  private pending = "";
  // 当前打字机帧回调 id；undefined 表示打字机空闲。
  private rafId: number | undefined;
  // Markdown 渲染节流器：流式期间按批次刷新 HTML，RunEnd / 工具卡插入前强制 flush。
  private markdownTimer: ReturnType<typeof setTimeout> | undefined;
  private lastMarkdownRenderAt = 0;
  private lastMarkdownRenderedText = "";
  private markdownShouldStick = false;
  // 当前轮的“思考”面板正文元素；一轮结束后清空。
  private reasoningBody: HTMLElement | undefined;
  // 当前轮的“思考”面板容器（<details>）与折叠行摘要节点，供收尾时折叠 + 写摘要。
  private reasoningPanel: HTMLDetailsElement | undefined;
  private reasoningPreview: HTMLElement | undefined;
  private reasoningText = "";
  // 运行态“思考中”占位行；有内容到达即撤下。
  private placeholder: HTMLElement | undefined;
  // 空状态引导节点；有消息即隐藏。
  private emptyState: HTMLElement | undefined;
  // 会话切换期间的骨架屏及淡出计时器。
  private historySkeleton: HTMLElement | undefined;
  private historyTransitionTimer: ReturnType<typeof setTimeout> | undefined;
  // tool_call_id → 该工具卡片的结果区元素，供 ToolResult 回填配对。
  private toolCards = new Map<string, HTMLElement>();
  private toolCalls = new Map<string, { name: string }>();
  private pendingArtifacts: string[] = [];
  // tool_call_id → 该工具卡片的审批区元素，供决定落定后禁用按钮 / 撤下。
  private permitPrompts = new Map<string, HTMLElement>();
  // sub conversation id → desktop 实验用的子 agent 面板。
  private subagentPanels = new Map<string, SubagentPanel>();
  // 当前主回复前的 thinking / tool / subagent 统一收进一个可折叠过程堆栈。
  private activityStack: HTMLDetailsElement | undefined;
  private activityContent: HTMLElement | undefined;
  private activityMeta: HTMLElement | undefined;
  private activityCount = 0;
  private activityToolCount = 0;
  private activityThinkingCount = 0;
  private assistantTurnLabeled = false;
  private assistantTurnTexts: string[] = [];
  private assistantTurnTimestamp: Date | null = null;

  // onPermit 由入口注入：用户点“批准/拒绝”时回传决定给宿主（视图层不碰 vscode API）。
  constructor(
    private readonly root: HTMLElement,
    private readonly onPermit?: (toolCallId: string, approved: boolean) => void,
    private readonly options: ChatRendererOptions = {},
  ) {
    this.showEmptyState();
  }

  /** 追加一条用户气泡，并立刻挂出“思考中”占位（发出即有反馈）。 */
  addUser(text: string): void {
    this.finishAssistantTurn();
    this.flushArtifacts();
    this.finishActivityStack();
    this.assistantTurnLabeled = false;
    this.hideEmptyState();
    const body = this.appendBubble("user");
    body.textContent = text;
    body.dataset.messageText = text;
    this.applyMessageCollapse(body);
    this.forceScrollToBottom();
    this.showPlaceholder();
  }

  /** 会话历史开始加载：清理旧内容并显示模拟 user/assistant 布局的骨架屏。 */
  showHistorySkeleton(): void {
    this.clear();
    const skeleton = makeHistorySkeleton();
    this.root.replaceChildren(skeleton);
    this.emptyState = undefined;
    this.historySkeleton = skeleton;
    this.root.classList.add("is-loading");
  }

  /** 清空对话：停打字机、复位轮内状态、清 DOM，回到空状态（“新会话”）。 */
  clear(): void {
    this.stopTyping();
    this.cancelMarkdownRender();
    this.pending = "";
    this.assistantBody = undefined;
    this.assistantText = "";
    this.resetMarkdownState();
    this.reasoningBody = undefined;
    this.reasoningPanel = undefined;
    this.reasoningPreview = undefined;
    this.reasoningText = "";
    this.placeholder = undefined;
    if (this.historyTransitionTimer) {
      clearTimeout(this.historyTransitionTimer);
      this.historyTransitionTimer = undefined;
    }
    this.historySkeleton = undefined;
    this.root.classList.remove("is-loading");
    this.root.classList.remove("history-entering");
    this.toolCards.clear();
    this.toolCalls.clear();
    this.pendingArtifacts = [];
    this.permitPrompts.clear();
    this.subagentPanels.clear();
    this.activityStack = undefined;
    this.activityContent = undefined;
    this.activityMeta = undefined;
    this.activityCount = 0;
    this.activityToolCount = 0;
    this.activityThinkingCount = 0;
    this.assistantTurnLabeled = false;
    this.assistantTurnTexts = [];
    this.assistantTurnTimestamp = null;
    this.root.replaceChildren();
    this.showEmptyState();
  }

  /** 消费一条事件。 */
  handleEvent(event: WireEventMessage): void {
    const { method, params } = event;
    if (method === "ReasoningDelta") {
      this.removePlaceholder();
      this.appendReasoning(readString(params, "text"));
      return;
    }
    if (method === "TextDelta") {
      this.removePlaceholder();
      this.enqueueAssistantText(readString(params, "text"));
      return;
    }
    if (method === "ToolCallBegin") {
      this.removePlaceholder();
      this.addToolCard(
        readString(params, "tool_call_id"),
        readString(params, "name"),
        readString(params, "arguments"),
      );
      return;
    }
    if (method === "ToolResult") {
      this.fillToolResult(
        readString(params, "tool_call_id"),
        readString(params, "content"),
        params.ok !== false,
      );
      return;
    }
    if (method === "PermitRequest") {
      this.addPermitPrompt(
        readString(params, "tool_call_id"),
        readString(params, "summary"),
      );
      return;
    }
    if (method === "SubagentEvent") {
      this.removePlaceholder();
      this.handleSubagentEvent(params);
      return;
    }
    if (method === "SlashResult") {
      this.removePlaceholder();
      this.addSlashResult(
        readString(params, "name"),
        readString(params, "text"),
        params.ok !== false,
      );
      return;
    }
    if (method === "HistoryReplay") {
      this.replayHistory(params.messages);
      return;
    }
    if (method === "Error") {
      this.finishActivityStack();
      this.showError(readString(params, "message") || "未知错误");
      this.finishAssistantTurn(new Date());
      this.flushArtifacts();
      return;
    }
    if (method === "RunEnd") {
      this.removePlaceholder();
      const stopReason = readString(params, "stop_reason");
      const pendingToolMessage =
        stopReason === "cancelled" ? "已取消" : "未完成";
      this.settlePendingToolCards(pendingToolMessage, false);
      this.finishAssistant();
      this.finishActivityStack();
      const message = stopReasonNotice(readString(params, "stop_reason"));
      if (message) {
        this.showNotice(message);
      }
      this.finishAssistantTurn(new Date());
      this.flushArtifacts();
      return;
    }
  }

  /** 展示一轮失败：撤掉 loading / 打字机，插入错误气泡。 */
  showError(message: string): void {
    // reset/resume 失败时 wire 会先发空 HistoryReplay 再发 Error；
    // HistoryReplay 的骨架离开动画若晚于 Error，会 clear() 掉错误气泡。
    if (this.historyTransitionTimer) {
      clearTimeout(this.historyTransitionTimer);
      this.historyTransitionTimer = undefined;
    }
    const wasLoading =
      Boolean(this.historySkeleton) || this.root.classList.contains("is-loading");
    this.historySkeleton = undefined;
    this.root.classList.remove("is-loading");
    this.root.classList.remove("history-entering");
    if (wasLoading) {
      this.root.replaceChildren();
      this.emptyState = undefined;
    }
    this.hideEmptyState();
    this.removePlaceholder();
    this.settlePendingToolCards("未完成", false);
    this.finishAssistant();
    const body = this.appendErrorBubble();
    body.textContent = message;
    this.forceScrollToBottom();
  }

  /** 展示非错误状态提示，例如达到最大工具调用轮数。 */
  showNotice(message: string): void {
    this.hideEmptyState();
    const body = this.appendNoticeBubble();
    body.textContent = message;
    this.forceScrollToBottom();
  }

  /** 回放一个会话的历史：先清屏，再按 Python 侧规整的扁平数组逐条重建 DOM。
   *  空数组表示新会话（纯清屏）。数据形状见 wire.py 的 history_messages。 */
  private replayHistory(raw: unknown): void {
    if (this.historySkeleton) {
      const skeleton = this.historySkeleton;
      skeleton.classList.add("leaving");
      this.historyTransitionTimer = setTimeout(() => {
        if (this.historySkeleton !== skeleton) {
          return;
        }
        this.historySkeleton = undefined;
        this.historyTransitionTimer = undefined;
        this.renderHistory(raw);
      }, 160);
      return;
    }
    this.renderHistory(raw);
  }

  private renderHistory(raw: unknown): void {
    this.clear();
    if (!Array.isArray(raw)) {
      return;
    }
    this.hideEmptyState();
    for (const item of raw) {
      if (typeof item !== "object" || item === null) {
        continue;
      }
      const record = item as Record<string, unknown>;
      const kind = readString(record, "kind");
      if (kind === "text") {
        const role = readString(record, "role");
        if (role === "user") {
          this.settlePendingToolCards("已中断", false);
          this.finishAssistantTurn();
        }
        this.replayText(
          role,
          readString(record, "text"),
          readString(record, "created_at") ||
          readString(record, "createdAt") ||
          readString(record, "timestamp"),
        );
      } else if (kind === "thinking") {
        this.replayThinking(readString(record, "text"));
      } else if (kind === "tool_call") {
        this.addToolCard(
          readString(record, "tool_call_id"),
          readString(record, "name"),
          readString(record, "arguments"),
        );
      } else if (kind === "tool_result") {
        this.fillToolResult(
          readString(record, "tool_call_id"),
          readString(record, "content"),
          true,
        );
      }
    }
    this.settlePendingToolCards("已中断", false);
    this.finishAssistantTurn();
    this.flushArtifacts();
    if (raw.length === 0) {
      this.showEmptyState();
    }
    this.forceScrollToBottom();
    this.root.classList.add("history-entering");
    setTimeout(() => this.root.classList.remove("history-entering"), 180);
  }

  /** 回放一条完整文本气泡（user 或 assistant），一次性定稿，不走打字机。
   *  assistant 正文按 markdown 渲染（含表格），user 输入保持纯文本。 */
  private replayText(role: string, text: string, timestamp: string): void {
    if (role !== "user" && role !== "assistant") {
      return;
    }
    if (role === "user") {
      this.flushArtifacts();
    }
    this.finishActivityStack();
    if (role === "user") {
      this.assistantTurnLabeled = false;
    }
    const body = this.appendBubble(role, parseMessageTime(timestamp));
    body.dataset.messageText = text;
    if (role === "assistant") {
      this.assistantTurnTexts.push(text);
      this.assistantTurnTimestamp =
        parseMessageTime(timestamp) ?? this.assistantTurnTimestamp;
      renderMarkdownInto(body, text, this.options.highlightCode);
    } else {
      body.textContent = text;
    }
    this.applyMessageCollapse(body);
  }

  /** 回放一段思考内容到折叠面板（历史默认折叠，折叠行显示摘要预览）。 */
  private replayThinking(text: string): void {
    if (!text) {
      return;
    }
    const body = this.appendThinkingPanel();
    body.textContent = text;
    if (this.reasoningPreview) {
      this.reasoningPreview.textContent = summarizeLine(text);
    }
    if (this.reasoningPanel) {
      this.reasoningPanel.open = false;
    }
    // 回放逐条独立，别让后续 tool_result 之类误用上一条的面板引用。
    this.reasoningPanel = undefined;
    this.reasoningPreview = undefined;
    this.reasoningBody = undefined;
  }

  /** 把思考增量拼进本轮折叠面板；面板不存在则新建（流式时展开）。 */
  private appendReasoning(delta: string): void {
    if (!delta) {
      return;
    }
    if (!this.reasoningBody) {
      this.sealAssistantBubble();
      this.reasoningBody = this.appendThinkingPanel();
      this.reasoningText = "";
    }
    const stick = this.isNearBottom();
    this.reasoningText += delta;
    this.reasoningBody.textContent = this.reasoningText;
    if (this.reasoningPreview) {
      this.reasoningPreview.textContent = summarizeLine(this.reasoningText);
    }
    if (stick) {
      this.forceScrollToBottom();
    }
  }

  /** 把增量文本压进 pending 队列并唤醒打字机；气泡不存在则新建。 */
  private enqueueAssistantText(delta: string): void {
    if (!delta) {
      return;
    }
    if (!this.assistantBody) {
      this.finishActivitySegment();
      this.assistantBody = this.appendBubble("assistant");
      this.assistantText = "";
      this.resetMarkdownState();
    }
    this.pending += delta;
    this.startTyping();
  }

  /** 启动打字机帧循环；已在运行则忽略，避免叠加多条循环。 */
  private startTyping(): void {
    if (this.rafId !== undefined) {
      return;
    }
    const step = () => {
      // 自适应速度：pending 越长每帧吐越多，避免模型一次性吐大段时明显滞后。
      const take = Math.max(1, Math.ceil(this.pending.length / 8));
      this.assistantText += this.pending.slice(0, take);
      this.pending = this.pending.slice(take);
      this.paintAssistant();
      if (this.pending.length > 0) {
        this.rafId = requestAnimationFrame(step);
        return;
      }
      this.rafId = undefined;
    };
    this.rafId = requestAnimationFrame(step);
  }

  private stopTyping(): void {
    if (this.rafId !== undefined) {
      cancelAnimationFrame(this.rafId);
      this.rafId = undefined;
    }
  }

  /** 把当前 assistantText 以 Markdown 形态增量刷到 DOM；贴底时才跟随滚动。 */
  private paintAssistant(): void {
    const stick = this.isNearBottom();
    this.scheduleMarkdownRender(stick);
  }

  /** 定稿当前 assistant 气泡：停打字机、补齐 pending 余量，强制完成最后一次
   *  Markdown 渲染（含 GFM 表格），思考面板折叠，准备下一轮。 */
  private finishAssistant(): void {
    this.stopTyping();
    if (this.pending) {
      this.assistantText += this.pending;
      this.pending = "";
      this.paintAssistant();
    }
    this.flushMarkdownRender();
    this.commitAssistantText();
    if (this.assistantBody) {
      this.applyMessageCollapse(this.assistantBody);
    }
    this.collapseThinkingPanel();
    this.assistantBody = undefined;
    this.assistantText = "";
    this.resetMarkdownState();
    this.reasoningBody = undefined;
    this.reasoningPanel = undefined;
    this.reasoningPreview = undefined;
    this.reasoningText = "";
  }

  /** 本轮思考结束后折叠面板：折叠行保留一段摘要预览，不再额外占用竖向空间。 */
  private collapseThinkingPanel(): void {
    if (this.reasoningPanel) {
      this.reasoningPanel.open = false;
    }
    if (this.reasoningPreview) {
      this.reasoningPreview.textContent = summarizeLine(this.reasoningText);
    }
  }

  /** 封口当前 assistant 气泡：补齐 pending 后让后续文本另起新气泡。
   *  工具卡片插在文字流中间时用它保证 DOM 顺序（前文 → 工具卡 → 后文）。 */
  private sealAssistantBubble(): void {
    this.stopTyping();
    if (this.pending) {
      this.assistantText += this.pending;
      this.pending = "";
      this.paintAssistant();
    }
    this.flushMarkdownRender();
    this.commitAssistantText();
    if (this.assistantBody) {
      this.applyMessageCollapse(this.assistantBody);
    }
    this.assistantBody = undefined;
    this.assistantText = "";
    this.resetMarkdownState();
  }

  private commitAssistantText(): void {
    if (this.assistantText.trim()) {
      this.assistantTurnTexts.push(this.assistantText);
    }
  }

  private finishAssistantTurn(timestamp = this.assistantTurnTimestamp): void {
    const text = this.assistantTurnTexts.join("\n\n").trim();
    if (text && this.options.messageActions) {
      const row = document.createElement("div");
      row.className = "assistant-turn-actions";
      row.appendChild(makeMessageActions(() => text, timestamp, true));
      this.root.appendChild(row);
    }
    this.assistantTurnTexts = [];
    this.assistantTurnTimestamp = null;
  }

  /** 流式 Markdown 渲染：按固定间隔合并多次打字机更新，避免每个字符都重排。
   *  marked 仍解析当前完整缓冲区，这是为了兼容表格、围栏代码块等需要上下文的语法。 */
  private scheduleMarkdownRender(stick: boolean): void {
    if (!this.assistantBody) {
      return;
    }
    this.markdownShouldStick = this.markdownShouldStick || stick;
    if (this.markdownTimer) {
      return;
    }
    const elapsed = performance.now() - this.lastMarkdownRenderAt;
    const delay = Math.max(0, MARKDOWN_RENDER_INTERVAL_MS - elapsed);
    this.markdownTimer = setTimeout(() => {
      this.markdownTimer = undefined;
      this.renderAssistantMarkdown();
    }, delay);
  }

  /** 取消尚未执行的节流渲染。 */
  private cancelMarkdownRender(): void {
    if (!this.markdownTimer) {
      return;
    }
    clearTimeout(this.markdownTimer);
    this.markdownTimer = undefined;
  }

  /** 立即把当前缓冲区渲染成 Markdown。RunEnd 和工具卡插入前调用，保证 DOM 不丢尾巴。 */
  private flushMarkdownRender(): void {
    this.cancelMarkdownRender();
    this.renderAssistantMarkdown();
  }

  /** 执行一次 Markdown 渲染；文本没变化时只处理必要的贴底滚动。 */
  private renderAssistantMarkdown(): void {
    if (!this.assistantBody) {
      return;
    }
    if (this.assistantText !== this.lastMarkdownRenderedText) {
      renderMarkdownInto(
        this.assistantBody,
        this.assistantText,
        this.options.highlightCode,
      );
      this.assistantBody.dataset.messageText = this.assistantText;
      this.lastMarkdownRenderedText = this.assistantText;
      this.lastMarkdownRenderAt = performance.now();
    }
    if (this.markdownShouldStick) {
      this.forceScrollToBottom();
    }
    this.markdownShouldStick = false;
  }

  /** 新气泡/收尾/清屏时重置 Markdown 渲染状态。 */
  private resetMarkdownState(): void {
    this.lastMarkdownRenderAt = 0;
    this.lastMarkdownRenderedText = "";
    this.markdownShouldStick = false;
  }

  private activityHost(kind: "thinking" | "tool" | "subagent"): HTMLElement {
    if (!this.options.stackActivities) {
      return this.root;
    }
    if (!this.activityStack || !this.activityContent || !this.activityMeta) {
      if (!this.assistantTurnLabeled) {
        const turnLabel = makeRoleLabel("assistant");
        turnLabel.classList.add("activity-turn-label");
        this.root.appendChild(turnLabel);
        this.assistantTurnLabeled = true;
      }
      const stack = document.createElement("details");
      stack.className = "activity-stack";
      stack.open = true;

      const summary = document.createElement("summary");
      summary.className = "activity-stack-summary";
      const icon = this.options.activityIcon?.() ?? document.createElement("i");
      if (!this.options.activityIcon) {
        icon.classList.add("codicon", "codicon-run-all");
      }
      icon.classList.add("activity-stack-icon");
      const label = document.createElement("span");
      label.className = "activity-stack-label";
      label.textContent = "执行过程";
      const meta = document.createElement("span");
      meta.className = "activity-stack-meta";
      summary.append(icon, label, meta);

      const content = document.createElement("div");
      content.className = "activity-stack-content";
      stack.append(summary, content);
      this.root.appendChild(stack);
      this.activityStack = stack;
      this.activityContent = content;
      this.activityMeta = meta;
    }

    this.activityCount += 1;
    if (kind === "tool") {
      this.activityToolCount += 1;
    } else if (kind === "thinking") {
      this.activityThinkingCount += 1;
    }
    this.updateActivityMeta();
    return this.activityContent;
  }

  private updateActivityMeta(): void {
    if (!this.activityMeta) {
      return;
    }
    const parts = [`${this.activityCount} 项`];
    if (this.activityToolCount) {
      parts.push(`${this.activityToolCount} 工具`);
    }
    if (this.activityThinkingCount) {
      parts.push(`${this.activityThinkingCount} 思考`);
    }
    this.activityMeta.textContent = parts.join(" · ");
    this.activityStack?.classList.toggle(
      "has-multiple",
      this.activityCount > 1,
    );
  }

  private collapseActivityStack(): void {
    if (this.activityStack) {
      this.activityStack.open = false;
    }
  }

  private finishActivityStack(): void {
    this.collapseActivityStack();
    this.activityStack = undefined;
    this.activityContent = undefined;
    this.activityMeta = undefined;
    this.activityCount = 0;
    this.activityToolCount = 0;
    this.activityThinkingCount = 0;
  }

  private finishReasoningSegment(): void {
    this.collapseThinkingPanel();
    this.reasoningBody = undefined;
    this.reasoningPanel = undefined;
    this.reasoningPreview = undefined;
    this.reasoningText = "";
  }

  private finishActivitySegment(): void {
    this.finishReasoningSegment();
    this.finishActivityStack();
  }

  /** 新建一张工具卡片（折叠，默认展开）：标题工具名，展开区显示参数，末尾留结果占位。 */
  private addToolCard(id: string, name: string, args: string): void {
    this.sealAssistantBubble();
    this.finishReasoningSegment();
    this.hideEmptyState();
    if (id) {
      this.toolCalls.set(id, { name });
    }
    this.appendToolCard(this.activityHost("tool"), this.toolCards, id, name, args);
  }

  private appendToolCard(
    parent: HTMLElement,
    cards: Map<string, HTMLElement>,
    id: string,
    name: string,
    args: string,
  ): void {
    const details = document.createElement("details");
    details.className = "tool-card call";
    details.open = false;

    const summary = document.createElement("summary");
    const icon = document.createElement("i");
    icon.className = "codicon codicon-wrench";
    const label = document.createElement("code");
    label.className = "tool-name";
    label.textContent = name || "tool";
    // 折叠行的内联参数摘要：卡片展开时隐藏（CSS 控制），折叠时一行速览。
    const preview = document.createElement("span");
    preview.className = "tool-preview";
    preview.textContent = summarizeLine(args);
    const status = document.createElement("span");
    status.className = "tool-status";
    setToolStatus(status, "codicon-loading codicon-modifier-spin", "运行中");
    summary.append(icon, label, preview, status);

    const body = document.createElement("div");
    body.className = "tool-body";
    if (args) {
      body.appendChild(makeToolSection("参数", args));
    }
    const resultSlot = document.createElement("div");
    resultSlot.className = "tool-result-slot";
    body.appendChild(resultSlot);

    details.append(summary, body);
    const stick = this.isNearBottom();
    parent.appendChild(details);
    if (id) {
      cards.set(id, resultSlot);
    }
    if (stick) {
      this.forceScrollToBottom();
    }
  }

  /** 结束仍显示「运行中」的工具卡（历史回放缺 result、或 run 被取消时）。 */
  private settlePendingToolCards(message: string, ok: boolean): void {
    for (const id of [...this.toolCards.keys()]) {
      this.fillToolResult(id, message, ok);
    }
  }

  /** 按 tool_call_id 回填结果，更新卡片配色与状态标签。找不到卡片则忽略。 */
  private fillToolResult(id: string, content: string, ok: boolean): void {
    this.captureDeliveredArtifact(id, content, ok);
    this.resolveToolCard(this.toolCards, id, content, ok);
  }

  private captureDeliveredArtifact(id: string, content: string, ok: boolean): void {
    const call = this.toolCalls.get(id);
    this.toolCalls.delete(id);
    if (ok && call?.name === "copy_to_host") {
      const prefix = "delivered file to user at ";
      const path = content.startsWith(prefix) ? content.slice(prefix.length).trim() : "";
      if (path && !this.pendingArtifacts.includes(path)) {
        this.pendingArtifacts.push(path);
      }
    }
  }

  private flushArtifacts(): void {
    if (this.pendingArtifacts.length === 0) {
      return;
    }
    const paths = this.pendingArtifacts;
    this.pendingArtifacts = [];
    if (!this.options.onArtifactOpen) {
      return;
    }
    const group = document.createElement("section");
    group.className = "delivered-artifacts";

    const heading = document.createElement("div");
    heading.className = "delivered-artifacts-heading";
    const headingIcon = document.createElement("i");
    headingIcon.className = "codicon codicon-package";
    const headingLabel = document.createElement("span");
    headingLabel.textContent = "Artifacts";
    const count = document.createElement("span");
    count.className = "delivered-artifacts-count";
    count.textContent = String(paths.length);
    heading.append(headingIcon, headingLabel, count);

    const cards = document.createElement("div");
    cards.className = "delivered-artifact-cards";
    paths.forEach((path) => {
      const name = path.split(/[\\/]/).filter(Boolean).pop() ?? path;
      const visual = deliveredArtifactVisual(name);
      const card = document.createElement("button");
      card.type = "button";
      card.className = "delivered-artifact-card";
      card.title = `在右侧打开 ${path}`;
      card.dataset.kind = visual.kind;
      card.dataset.extension = visual.extension;
      const copy = document.createElement("span");
      copy.className = "delivered-artifact-copy";
      const title = document.createElement("span");
      title.className = "delivered-artifact-name";
      title.textContent = name;
      const meta = document.createElement("span");
      meta.className = "delivered-artifact-meta";
      meta.textContent = "已交付";
      copy.append(title, meta);
      const arrow = document.createElement("i");
      arrow.className = "codicon codicon-chevron-right delivered-artifact-arrow";
      card.append(copy, arrow);
      card.addEventListener("click", () => this.options.onArtifactOpen?.(path));
      cards.appendChild(card);
    });
    group.append(heading, cards);

    const stick = this.isNearBottom();
    this.root.appendChild(group);
    if (stick) {
      this.forceScrollToBottom();
    }
  }

  private resolveToolCard(
    cards: Map<string, HTMLElement>,
    id: string,
    content: string,
    ok: boolean,
  ): void {
    const slot = cards.get(id);
    if (!slot) {
      return;
    }
    cards.delete(id);
    slot.appendChild(makeToolSection("结果", content || "(空)"));

    const details = slot.closest(".tool-card");
    if (details instanceof HTMLElement) {
      details.classList.remove("call");
      details.classList.add("result", ok ? "ok" : "fail");
      const status = details.querySelector(".tool-status");
      if (status) {
        setToolStatus(
          status,
          ok ? "codicon-pass-filled" : "codicon-error",
          ok ? "完成" : "失败",
        );
      }
    }
    if (this.isNearBottom()) {
      this.forceScrollToBottom();
    }
  }

  private handleSubagentEvent(params: Record<string, unknown>): void {
    const conversationId = readString(params, "conversation_id");
    const name = readString(params, "name") || "subagent";
    const wrapped = readRecord(params, "event");
    if (!conversationId || !wrapped) {
      return;
    }
    const method = readString(wrapped, "method");
    const inner = readRecord(wrapped, "params") ?? {};
    if (!method) {
      return;
    }

    const panel = this.ensureSubagentPanel(conversationId, name);
    if (method === "RunBegin") {
      panel.preview.textContent = "思考";
      setSubagentState(panel, "running", "运行中");
      return;
    }
    if (method === "ReasoningDelta") {
      panel.preview.textContent = "思考";
      return;
    }
    if (method === "TextDelta") {
      panel.preview.textContent = "思考";
      return;
    }
    if (method === "ToolCallBegin") {
      panel.preview.textContent = "工具";
      const id = readString(inner, "tool_call_id");
      if (id) {
        this.toolCalls.set(id, { name: readString(inner, "name") });
      }
      return;
    }
    if (method === "ToolResult") {
      panel.preview.textContent = "工具";
      this.captureDeliveredArtifact(
        readString(inner, "tool_call_id"),
        readString(inner, "content"),
        inner.ok !== false,
      );
      return;
    }
    if (method === "RunEnd") {
      setSubagentState(
        panel,
        readString(inner, "stop_reason") === "cancelled" ? "cancelled" : "done",
        readString(inner, "stop_reason") === "cancelled" ? "已取消" : "完成",
      );
      return;
    }
  }

  private ensureSubagentPanel(
    conversationId: string,
    name: string,
  ): SubagentPanel {
    const existing = this.subagentPanels.get(conversationId);
    if (existing) {
      return existing;
    }
    this.sealAssistantBubble();
    this.finishReasoningSegment();
    this.hideEmptyState();

    const row = document.createElement("div");
    row.className = "subagent-panel";
    row.dataset.state = "running";

    const leadIcon = document.createElement("i");
    leadIcon.className = "codicon codicon-hubot";
    const icon = document.createElement("i");
    icon.className = "codicon codicon-loading codicon-modifier-spin";
    const label = document.createElement("code");
    label.className = "subagent-name";
    label.textContent = name;
    const preview = document.createElement("span");
    preview.className = "subagent-preview";
    preview.textContent = "启动中";
    const status = document.createElement("span");
    status.className = "subagent-status";
    status.append(icon);
    row.append(leadIcon, label, preview, status);
    const stick = this.isNearBottom();
    this.activityHost("subagent").appendChild(row);
    if (stick) {
      this.forceScrollToBottom();
    }

    const panel: SubagentPanel = {
      root: row,
      icon,
      preview,
      status,
    };
    this.subagentPanels.set(conversationId, panel);
    return panel;
  }

  /** 渲染一条 slash 命令结果：折叠卡（斜杠图标 + /命令名 + 内联摘要），展开看完整输出。
   *  slash 命令不进对话历史，卡片插在文字流中间前先封口当前 assistant 气泡保证顺序。 */
  private addSlashResult(name: string, text: string, ok: boolean): void {
    this.sealAssistantBubble();
    this.finishActivitySegment();
    this.hideEmptyState();

    const details = document.createElement("details");
    details.className = `slash-card ${ok ? "ok" : "fail"}`;
    details.open = false;

    const summary = document.createElement("summary");
    const icon = makeSlashIcon();
    const label = document.createElement("code");
    label.className = "slash-name";
    label.textContent = `/${name}`;
    const preview = document.createElement("span");
    preview.className = "slash-preview";
    preview.textContent = summarizeLine(text);
    summary.append(icon, label, preview);

    const body = document.createElement("pre");
    body.className = "slash-body";
    body.textContent = text || "(无输出)";

    details.append(summary, body);
    const stick = this.isNearBottom();
    this.root.appendChild(details);
    if (stick) {
      this.forceScrollToBottom();
    }
  }

  /** 危险工具挂起审批：在其卡片里展开一个“批准/拒绝”条，等用户拍板。
   *  卡片由前一条 ToolCallBegin 建好；这里按 tool_call_id 找到并追加审批区。 */
  private addPermitPrompt(id: string, summary: string): void {
    const slot = this.toolCards.get(id);
    if (!slot || !id) {
      return;
    }
    const details = slot.closest(".tool-card");
    if (details instanceof HTMLDetailsElement) {
      if (this.activityStack?.contains(details)) {
        this.activityStack.open = true;
      }
      details.open = true; // 展开卡片，让审批按钮直接可见。
      const status = details.querySelector(".tool-status");
      if (status) {
        setToolStatus(status, "codicon-question", "待审批");
      }
    }
    slot.parentElement
      ?.querySelectorAll(".tool-section")
      .forEach((section) => {
        const title = section.querySelector(".tool-section-title");
        if (title?.textContent === "参数") {
          section.remove();
        }
      });

    const bar = document.createElement("div");
    bar.className = "tool-permit";
    const icon = document.createElement("i");
    icon.className = "codicon codicon-warning tool-permit-icon";
    bar.appendChild(icon);
    if (summary) {
      const hint = document.createElement("div");
      hint.className = "tool-permit-summary";
      hint.textContent = summary;
      bar.appendChild(hint);
    }
    const actions = document.createElement("div");
    actions.className = "tool-permit-actions";
    const approve = makePermitButton("批准", "codicon-check", "approve");
    const deny = makePermitButton("拒绝", "codicon-close", "deny");
    approve.addEventListener("click", () => this.resolvePermit(id, true));
    deny.addEventListener("click", () => this.resolvePermit(id, false));
    actions.append(approve, deny);
    bar.appendChild(actions);

    // 审批条放在结果占位之前，决定落定后 ToolResult 回填到结果区。
    slot.parentElement?.insertBefore(bar, slot);
    this.permitPrompts.set(id, bar);
    if (this.isNearBottom()) {
      this.forceScrollToBottom();
    }
  }

  /** 用户拍板：回调宿主，禁用本卡按钮防重复点击，状态改“执行中/已拒绝”。 */
  private resolvePermit(id: string, approved: boolean): void {
    const bar = this.permitPrompts.get(id);
    if (!bar) {
      return;
    }
    this.permitPrompts.delete(id);
    bar.querySelectorAll("button").forEach((btn) => {
      (btn as HTMLButtonElement).disabled = true;
    });
    bar.classList.add(approved ? "approved" : "denied");

    const details = bar.closest(".tool-card");
    if (details instanceof HTMLDetailsElement) {
      const status = details.querySelector(".tool-status");
      if (status) {
        if (approved) {
          setToolStatus(status, "codicon-loading codicon-modifier-spin", "执行中");
        } else {
          setToolStatus(status, "codicon-circle-slash", "已拒绝");
        }
      }
      details.open = false;
    }
    this.onPermit?.(id, approved);
  }

  /** 挂出“思考中”占位（三点动画）；已存在则复用。 */
  private showPlaceholder(): void {
    if (this.placeholder) {
      return;
    }
    const row = document.createElement("div");
    row.className = "chat-row assistant pending";
    const msg = document.createElement("div");
    msg.className = "msg assistant";
    msg.appendChild(makeRoleLabel("assistant"));
    const bubble = document.createElement("div");
    bubble.className = "bubble assistant typing-indicator";
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement("span");
      dot.className = "dot";
      bubble.appendChild(dot);
    }
    msg.appendChild(bubble);
    row.appendChild(msg);
    this.placeholder = row;
    const stick = this.isNearBottom();
    this.root.appendChild(row);
    if (stick) {
      this.forceScrollToBottom();
    }
  }

  private removePlaceholder(): void {
    this.placeholder?.remove();
    this.placeholder = undefined;
  }

  /** 新建一个折叠“思考”面板（流式时展开），返回其正文元素供填充。
   *  折叠行结构：大脑图标 + thinking 标签 + 内联摘要。 */
  private appendThinkingPanel(): HTMLElement {
    const details = document.createElement("details");
    details.className = "thinking-panel";
    details.open = true;
    const summary = document.createElement("summary");
    const icon = makeBrainIcon();
    const label = document.createElement("span");
    label.className = "thinking-label";
    label.textContent = "thinking";
    const preview = document.createElement("span");
    preview.className = "thinking-preview";
    summary.append(icon, label, preview);
    const body = document.createElement("div");
    body.className = "thinking-body";
    details.appendChild(summary);
    details.appendChild(body);
    const stick = this.isNearBottom();
    this.activityHost("thinking").appendChild(details);
    this.reasoningPanel = details;
    this.reasoningPreview = preview;
    if (stick) {
      this.forceScrollToBottom();
    }
    return body;
  }

  /** 新建一个带角色标签的气泡行，返回其正文元素供填充。 */
  private appendBubble(
    role: "user" | "assistant",
    timestamp: Date | null = new Date(),
  ): HTMLElement {
    const row = document.createElement("div");
    row.className = `chat-row ${role}`;
    const msg = document.createElement("div");
    msg.className = `msg ${role}`;
    if (role === "user" || !this.assistantTurnLabeled) {
      msg.appendChild(makeRoleLabel(role));
    }
    if (role === "assistant") {
      this.assistantTurnLabeled = true;
    }
    const bubble = document.createElement("div");
    bubble.className = `bubble ${role}`;
    const body = document.createElement("div");
    body.className = "bubble-body";
    bubble.appendChild(body);
    msg.appendChild(bubble);
    if (this.options.messageActions && role === "user") {
      const actions = makeMessageActions(
        () => body.dataset.messageText ?? body.innerText,
        timestamp,
      );
      actions.classList.add("user-message-actions");
      msg.appendChild(actions);
    }
    row.appendChild(msg);
    this.root.appendChild(row);
    return body;
  }

  private applyMessageCollapse(body: HTMLElement): void {
    if (!this.options.collapseMessages) {
      return;
    }
    requestAnimationFrame(() => {
      if (!body.isConnected || body.scrollHeight <= MESSAGE_COLLAPSED_HEIGHT_PX) {
        return;
      }
      const bubble = body.parentElement;
      if (!bubble || bubble.querySelector(":scope > .message-toggle")) {
        return;
      }
      bubble.classList.add("message-collapsible", "is-collapsed");
      const toggle = document.createElement("button");
      toggle.className = "message-toggle";
      toggle.type = "button";
      toggle.textContent = "展开";
      toggle.setAttribute("aria-expanded", "false");
      toggle.addEventListener("click", () => {
        const collapsed = bubble.classList.toggle("is-collapsed");
        toggle.textContent = collapsed ? "展开" : "收起";
        toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
      const actions = bubble.querySelector<HTMLElement>(
        ":scope > .message-actions",
      );
      if (actions) {
        actions.prepend(toggle);
      } else {
        bubble.appendChild(toggle);
      }
    });
  }

  /** 错误气泡：左侧 assistant 位，但用 error 样式与角色标签 error。 */
  private appendErrorBubble(): HTMLElement {
    const row = document.createElement("div");
    row.className = "chat-row assistant error";
    const msg = document.createElement("div");
    msg.className = "msg assistant error";
    const label = document.createElement("div");
    label.className = "role-label";
    label.textContent = "error";
    msg.appendChild(label);
    const bubble = document.createElement("div");
    bubble.className = "bubble assistant error";
    const body = document.createElement("div");
    body.className = "bubble-body";
    bubble.appendChild(body);
    msg.appendChild(bubble);
    row.appendChild(msg);
    this.root.appendChild(row);
    return body;
  }

  /** 状态提示气泡：左侧 assistant 位，用普通助手气泡承载解释性文案。 */
  private appendNoticeBubble(): HTMLElement {
    const row = document.createElement("div");
    row.className = "chat-row assistant notice";
    const msg = document.createElement("div");
    msg.className = "msg assistant notice";
    const label = document.createElement("div");
    label.className = "role-label";
    label.textContent = "pagent";
    msg.appendChild(label);
    const bubble = document.createElement("div");
    bubble.className = "bubble assistant notice";
    const body = document.createElement("div");
    body.className = "bubble-body";
    bubble.appendChild(body);
    msg.appendChild(bubble);
    row.appendChild(msg);
    this.root.appendChild(row);
    return body;
  }

  private showEmptyState(): void {
    if (this.emptyState) {
      return;
    }
    const node = document.createElement("div");
    node.className = "empty-state";
    const prompts = this.options.starterPrompts ?? [];
    if (prompts.length === 0) {
      node.textContent = "问点什么开始 —— 回车发送，Shift+Enter 换行。";
    } else {
      const heading = document.createElement("div");
      heading.className = "starter-heading";
      heading.textContent = "从一个案例开始";
      const cards = document.createElement("div");
      cards.className = "starter-cards";
      for (const item of prompts) {
        const card = document.createElement("button");
        card.className = "starter-card";
        card.type = "button";
        const title = document.createElement("span");
        title.className = "starter-card-title";
        title.textContent = item.title;
        const description = document.createElement("span");
        description.className = "starter-card-description";
        description.textContent = item.description;
        card.append(title, description);
        card.addEventListener("click", () => {
          this.options.onStarterPrompt?.(item.prompt);
        });
        cards.appendChild(card);
      }
      node.append(heading, cards);
    }
    this.emptyState = node;
    this.root.appendChild(node);
  }

  private hideEmptyState(): void {
    this.emptyState?.remove();
    this.emptyState = undefined;
  }

  /** 与底部距离是否在阈值内（决定流式内容是否自动跟随）。 */
  private isNearBottom(): boolean {
    const { scrollTop, scrollHeight, clientHeight } = this.root;
    return scrollHeight - scrollTop - clientHeight < STICK_THRESHOLD_PX;
  }

  private forceScrollToBottom(): void {
    this.root.scrollTop = this.root.scrollHeight;
  }
}

/** 构建会话加载骨架：两条助手消息与一条右对齐用户消息，贴近真实对话节奏。 */
function makeHistorySkeleton(): HTMLElement {
  const skeleton = document.createElement("div");
  skeleton.className = "conversation-skeleton";
  skeleton.setAttribute("role", "status");
  skeleton.setAttribute("aria-live", "polite");
  skeleton.setAttribute("aria-label", "正在加载对话");

  const status = document.createElement("div");
  status.className = "skeleton-status";
  const spinner = document.createElement("i");
  spinner.className = "codicon codicon-loading codicon-modifier-spin";
  const label = document.createElement("span");
  label.textContent = "正在加载对话";
  status.append(spinner, label);
  skeleton.appendChild(status);

  appendSkeletonMessage(skeleton, "assistant", ["92%", "74%", "48%"]);
  appendSkeletonMessage(skeleton, "user", ["68%", "42%"]);
  appendSkeletonMessage(skeleton, "assistant", ["86%", "64%"]);
  return skeleton;
}

function appendSkeletonMessage(
  skeleton: HTMLElement,
  role: "user" | "assistant",
  widths: string[],
): void {
  const row = document.createElement("div");
  row.className = `skeleton-row ${role}`;
  const message = document.createElement("div");
  message.className = `skeleton-message ${role}`;
  const roleLine = document.createElement("div");
  roleLine.className = "skeleton-role";
  const bubble = document.createElement("div");
  bubble.className = "skeleton-bubble";
  for (const width of widths) {
    const line = document.createElement("span");
    line.className = "skeleton-line";
    line.style.width = width;
    bubble.appendChild(line);
  }
  message.append(roleLine, bubble);
  row.appendChild(message);
  skeleton.appendChild(row);
}

/** 从 params 里安全取字符串字段。 */
function readString(params: Record<string, unknown>, key: string): string {
  const value = params[key];
  return typeof value === "string" ? value : "";
}

function readRecord(
  params: Record<string, unknown>,
  key: string,
): Record<string, unknown> | undefined {
  const value = params[key];
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : undefined;
}

function stopReasonNotice(stopReason: string): string {
  if (stopReason === "max_turns") {
    return "本轮已达到最大工具调用轮数，先停止在这里。可以补充更明确的指令后继续。";
  }
  if (stopReason === "empty_response") {
    return "这一轮没有收到有效回复。请重试，或换一种更具体的说法。";
  }
  if (stopReason === "cancelled") {
    return "这一轮已取消。";
  }
  return "";
}

function parseMessageTime(value: string): Date | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

async function copyMessageText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  }
}

function makeMessageActions(
  getText: () => string,
  timestamp: Date | null,
  feedback = false,
): HTMLElement {
  const actions = document.createElement("div");
  actions.className = "message-actions";
  if (timestamp) {
    const time = document.createElement("time");
    time.className = "message-time";
    time.dateTime = timestamp.toISOString();
    time.title = timestamp.toLocaleString();
    time.textContent = timestamp.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    actions.appendChild(time);
  }

  if (feedback) {
    const feedbackButtons = [
      { value: "up", label: "点赞", icon: "thumbsup" },
      { value: "down", label: "点踩", icon: "thumbsdown" },
    ];
    for (const item of feedbackButtons) {
      const button = document.createElement("button");
      button.className = "message-action-button message-feedback-button";
      button.type = "button";
      button.dataset.feedback = item.value;
      button.title = item.label;
      button.setAttribute("aria-label", item.label);
      button.setAttribute("aria-pressed", "false");
      button.innerHTML = `<i class="codicon codicon-${item.icon}" aria-hidden="true"></i>`;
      button.addEventListener("click", () => {
        const selected = button.getAttribute("aria-pressed") === "true";
        const peers = Array.from(
          actions.querySelectorAll<HTMLButtonElement>(
            ".message-feedback-button",
          ),
        );
        for (const peer of peers) {
          const active = peer === button && !selected;
          peer.setAttribute("aria-pressed", String(active));
          peer.classList.toggle("is-selected", active);
          const icon = peer.dataset.feedback === "up" ? "thumbsup" : "thumbsdown";
          peer.innerHTML = `<i class="codicon codicon-${icon}${active ? "-filled" : ""}" aria-hidden="true"></i>`;
        }
      });
      actions.appendChild(button);
    }
  }

  const copy = document.createElement("button");
  copy.className = "message-action-button";
  copy.type = "button";
  copy.title = "复制消息";
  copy.setAttribute("aria-label", "复制消息");
  copy.innerHTML = '<i class="codicon codicon-copy" aria-hidden="true"></i>';
  copy.addEventListener("click", async () => {
    const copied = await copyMessageText(getText());
    copy.classList.toggle("is-copied", copied);
    copy.title = copied ? "已复制" : "复制失败";
    copy.setAttribute("aria-label", copy.title);
    copy.innerHTML = copied
      ? '<i class="codicon codicon-check" aria-hidden="true"></i>'
      : '<i class="codicon codicon-warning" aria-hidden="true"></i>';
    window.setTimeout(() => {
      if (!copy.isConnected) {
        return;
      }
      copy.classList.remove("is-copied");
      copy.title = "复制消息";
      copy.setAttribute("aria-label", "复制消息");
      copy.innerHTML =
        '<i class="codicon codicon-copy" aria-hidden="true"></i>';
    }, 1400);
  });
  actions.appendChild(copy);
  return actions;
}

// marked 默认开启 GFM（含表格），关掉 async 拿同步字符串结果。
marked.setOptions({ gfm: true, breaks: false });

/** 把 markdown 文本渲染进元素：marked 解析成 HTML，DOMPurify 消毒后注入。
 *  流式阶段会被节流调用，RunEnd / 历史回放时也复用同一套解析与消毒逻辑。
 *  加 markdown-body class 让 CSS 关掉气泡的 pre-wrap，交给块级元素自然排版。 */
function renderMarkdownInto(
  el: HTMLElement,
  text: string,
  highlightCode?: (code: string, language?: string) => string,
): void {
  const html = marked.parse(text, { async: false });
  el.innerHTML = DOMPurify.sanitize(html);
  el.classList.add("markdown-body");
  if (!highlightCode) {
    return;
  }
  for (const code of Array.from(el.querySelectorAll<HTMLElement>("pre code"))) {
    const language = Array.from(code.classList)
      .find((name) => name.startsWith("language-"))
      ?.slice("language-".length);
    const highlighted = highlightCode(code.textContent ?? "", language);
    code.innerHTML = DOMPurify.sanitize(highlighted, {
      ALLOWED_TAGS: ["span"],
      ALLOWED_ATTR: ["class"],
    });
    code.classList.add("hljs");
  }
}

// 折叠行摘要最长显示的字符数，超出截断加省略号。
const PREVIEW_MAX_CHARS = 80;

/** 把多行文本压成单行摘要，供折叠行内联速览。
 *  换行/连续空白折成单空格，首尾去空白，超长截断加省略号。 */
function summarizeLine(text: string): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  if (oneLine.length <= PREVIEW_MAX_CHARS) {
    return oneLine;
  }
  return oneLine.slice(0, PREVIEW_MAX_CHARS) + "…";
}

function deliveredArtifactVisual(name: string): {
  kind: string;
  extension: string;
} {
  const match = /\.([^.]+)$/.exec(name);
  const extension = (match?.[1] ?? "FILE").slice(0, 4).toUpperCase();
  if (/\.(html?|css|jsx?|tsx?|py|sh|go|rs|java|c|cpp|sql)$/i.test(name)) {
    return { kind: "code", extension };
  }
  if (/\.json$/i.test(name)) {
    return { kind: "data", extension };
  }
  if (/\.(ya?ml|toml|xml)$/i.test(name)) {
    return { kind: "data", extension };
  }
  if (/\.pdf$/i.test(name)) {
    return { kind: "document", extension };
  }
  if (/\.(md|mdx)$/i.test(name)) {
    return { kind: "document", extension };
  }
  if (/\.(txt|log|docx?|rtf|odt|epub|pptx?)$/i.test(name)) {
    return { kind: "document", extension };
  }
  if (/\.(png|jpe?g|gif|webp|svg|ico)$/i.test(name)) {
    return { kind: "image", extension };
  }
  if (/\.(csv|tsv|xlsx?|ods)$/i.test(name)) {
    return { kind: "sheet", extension };
  }
  if (/\.(zip|tar|gz|7z|rar)$/i.test(name)) {
    return { kind: "archive", extension };
  }
  return { kind: "file", extension };
}

/** 生成气泡上方的角色小标签。 */
function makeRoleLabel(role: "user" | "assistant"): HTMLElement {
  const label = document.createElement("div");
  label.className = "role-label";
  label.textContent = role === "user" ? "you" : "pagent";
  return label;
}

function setSubagentState(
  panel: SubagentPanel,
  state: "running" | "done" | "cancelled",
  text: string,
): void {
  void text;
  panel.root.dataset.state = state;
  if (state === "running") {
    panel.icon.className = "codicon codicon-loading codicon-modifier-spin";
    return;
  }
  if (state === "cancelled") {
    panel.icon.className = "codicon codicon-circle-slash";
    return;
  }
  panel.icon.className = "codicon codicon-pass-filled";
}

// 大脑图标（Lucide brain）：codicons 无脑形字形，这里内联 SVG。
// stroke=currentColor 让它随折叠行文字色走主题，尺寸交给 CSS 的 .thinking-icon。
const BRAIN_ICON_SVG =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
  'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
  '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>' +
  '<path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>' +
  '<path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/>' +
  '<path d="M17.599 6.5a3 3 0 0 0 .399-1.375"/>' +
  '<path d="M6.003 5.125A3 3 0 0 0 6.401 6.5"/>' +
  '<path d="M3.477 10.896a4 4 0 0 1 .585-.396"/>' +
  '<path d="M19.938 10.5a4 4 0 0 1 .585.396"/>' +
  '<path d="M6 18a4 4 0 0 1-1.967-.516"/>' +
  '<path d="M19.967 17.484A4 4 0 0 1 18 18"/></svg>';

/** 生成折叠“思考”面板折叠行的大脑图标节点。 */
function makeBrainIcon(): HTMLElement {
  const span = document.createElement("span");
  span.className = "thinking-icon";
  span.innerHTML = BRAIN_ICON_SVG;
  return span;
}

// slash 命令图标：圆角方框内一条斜杠（对齐输入框旁的斜杠按钮观感）。
// codicons 无此字形，内联 SVG，stroke=currentColor 随卡片文字色走主题。
const SLASH_ICON_SVG =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
  'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
  '<rect x="3" y="3" width="18" height="18" rx="4"/>' +
  '<line x1="14.5" y1="7" x2="9.5" y2="17"/></svg>';

/** 生成 slash 命令卡折叠行的斜杠方框图标节点。 */
function makeSlashIcon(): HTMLElement {
  const span = document.createElement("span");
  span.className = "slash-icon";
  span.innerHTML = SLASH_ICON_SVG;
  return span;
}

/** 用图标表达工具卡状态（替代纯文字）：清空原内容换成一个 codicon，
 *  title 保留中文语义供悬停/无障碍读出。运行/执行态用 loading 自旋。 */
function setToolStatus(status: Element, iconClass: string, title: string): void {
  status.textContent = "";
  status.setAttribute("title", title);
  const icon = document.createElement("i");
  icon.className = `codicon ${iconClass}`;
  status.appendChild(icon);
}

/** 生成审批条上的纯图标按钮；title/aria-label 保留批准/拒绝语义。 */
function makePermitButton(
  text: string,
  icon: string,
  kind: "approve" | "deny",
): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `tool-permit-btn ${kind}`;
  button.title = text;
  button.setAttribute("aria-label", text);
  const i = document.createElement("i");
  i.className = `codicon ${icon}`;
  const label = document.createElement("span");
  label.textContent = text;
  button.append(i, label);
  return button;
}

/** 生成工具卡片里的一段带标题的等宽文本块（参数 / 结果）。 */
function makeToolSection(title: string, text: string): HTMLElement {
  const section = document.createElement("div");
  section.className = "tool-section";
  const head = document.createElement("div");
  head.className = "tool-section-title";
  head.textContent = title;
  const pre = document.createElement("pre");
  pre.className = "tool-section-body";
  pre.textContent = text;
  section.append(head, pre);
  return section;
}
