import SwiftUI

enum AppTheme: String, CaseIterable, Identifiable {
  case system
  case light
  case dark

  var id: String { rawValue }

  var title: String {
    switch self {
    case .system: "跟随系统"
    case .light: "浅色"
    case .dark: "深色"
    }
  }

  var colorScheme: ColorScheme? {
    switch self {
    case .system: nil
    case .light: .light
    case .dark: .dark
    }
  }
}

enum MessageKind: Equatable {
  case taskLabel
  case user
  case voice
  case process
  case assistant
  case suggestion
}

struct ChatMessage: Identifiable, Equatable {
  let id: UUID
  let kind: MessageKind
  let text: String
  let time: Date

  init(id: UUID = UUID(), kind: MessageKind, text: String, time: Date = .now) {
    self.id = id
    self.kind = kind
    self.text = text
    self.time = time
  }
}

struct WorkTask: Identifiable, Equatable {
  let id: UUID
  let title: String
  let subtitle: String
  let relativeTime: String
  let status: String
  let participants: String
  let messages: [ChatMessage]
}

@MainActor
final class AppStore: ObservableObject {
  @Published var isAuthenticated = true
  @Published var isTaskDrawerVisible = false
  @Published var selectedTaskID: WorkTask.ID?
  @Published var messages: [ChatMessage] = []
  @Published var theme: AppTheme {
    didSet {
      UserDefaults.standard.set(theme.rawValue, forKey: Self.themeKey)
    }
  }

  let tasks: [WorkTask] = WorkTask.samples

  private static let themeKey = "pagent.ios.theme"
  private var conversationID = UUID()

  init() {
    let storedTheme = UserDefaults.standard.string(forKey: Self.themeKey)
    theme = AppTheme(rawValue: storedTheme ?? "") ?? .system
  }

  func startNewConversation() {
    conversationID = UUID()
    selectedTaskID = nil
    messages = []
    isTaskDrawerVisible = false
  }

  func loadTask(_ task: WorkTask) {
    conversationID = UUID()
    selectedTaskID = task.id
    messages = task.messages
    isTaskDrawerVisible = false
  }

  func sendText(_ text: String) {
    let content = text.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !content.isEmpty else {
      return
    }
    selectedTaskID = nil
    messages.append(ChatMessage(kind: .user, text: content))
    appendMockResponse(for: content)
  }

  func sendVoice() {
    selectedTaskID = nil
    messages.append(ChatMessage(kind: .voice, text: "语音消息"))
    appendMockResponse(for: "语音消息")
  }

  func logout() {
    conversationID = UUID()
    selectedTaskID = nil
    messages = []
    isTaskDrawerVisible = false
    isAuthenticated = false
  }

  func loginWithGuard() {
    startNewConversation()
    isAuthenticated = true
  }

  private func appendMockResponse(for prompt: String) {
    let activeConversationID = conversationID
    messages.append(ChatMessage(kind: .process, text: "过程已折叠"))

    Task {
      try? await Task.sleep(for: .milliseconds(450))
      guard activeConversationID == conversationID, isAuthenticated else {
        return
      }
      messages.append(
        ChatMessage(
          kind: .assistant,
          text: "已收到“\(prompt)”。当前为交互原型，接入服务后将在这里展示实际协同结果。"
        )
      )
    }
  }
}

extension WorkTask {
  static let samples: [WorkTask] = [
    WorkTask(
      id: UUID(),
      title: "季度方案评审",
      subtitle: "整理评审结论与待确认项",
      relativeTime: "12 分钟前",
      status: "待跟进",
      participants: "产品、设计、研发",
      messages: [
        ChatMessage(kind: .taskLabel, text: "季度方案评审"),
        ChatMessage(kind: .process, text: "过程已折叠"),
        ChatMessage(
          kind: .assistant,
          text: "评审已形成三项共识：先收敛移动端核心路径；语音交互保持轻量；设置与登录在本期形成闭环。"
        ),
        ChatMessage(kind: .suggestion, text: "整理需要研发确认的事项"),
      ]
    ),
    WorkTask(
      id: UUID(),
      title: "版本上线复盘",
      subtitle: "跟进性能指标和遗留问题",
      relativeTime: "昨天",
      status: "进行中",
      participants: "客户端、服务端",
      messages: [
        ChatMessage(kind: .taskLabel, text: "版本上线复盘"),
        ChatMessage(kind: .process, text: "过程已折叠"),
        ChatMessage(
          kind: .assistant,
          text: "核心链路运行稳定。需要继续观察首屏耗时，并为两个遗留问题补充负责人和完成时间。"
        ),
        ChatMessage(kind: .suggestion, text: "生成复盘行动清单"),
      ]
    ),
    WorkTask(
      id: UUID(),
      title: "客户会议纪要",
      subtitle: "确认试点范围与交付节奏",
      relativeTime: "周一",
      status: "已完成",
      participants: "销售、交付、客户",
      messages: [
        ChatMessage(kind: .taskLabel, text: "客户会议纪要"),
        ChatMessage(kind: .process, text: "过程已折叠"),
        ChatMessage(
          kind: .assistant,
          text: "客户确认先在一个团队试点。首阶段覆盖任务查询、会议追问和结果分享，试点周期为两周。"
        ),
        ChatMessage(kind: .suggestion, text: "起草试点确认邮件"),
      ]
    ),
    WorkTask(
      id: UUID(),
      title: "移动端体验走查",
      subtitle: "检查输入、侧栏与安全区",
      relativeTime: "上周",
      status: "待评审",
      participants: "设计、iOS",
      messages: [
        ChatMessage(kind: .taskLabel, text: "移动端体验走查"),
        ChatMessage(kind: .process, text: "过程已折叠"),
        ChatMessage(
          kind: .assistant,
          text: "走查重点包括顶部安全区、输入框键盘避让、消息区独立滚动，以及底部抽屉的内容层级。"
        ),
        ChatMessage(kind: .suggestion, text: "列出验收检查项"),
      ]
    ),
  ]
}
