import SwiftUI

struct WorkspaceView: View {
  @EnvironmentObject private var store: AppStore
  @State private var isSettingsPresented = false

  var body: some View {
    ZStack(alignment: .leading) {
      AppPalette.canvas
        .ignoresSafeArea()

      VStack(spacing: 0) {
        topBar
        MessageListView(messages: store.messages, onSuggestion: store.sendText)
        ComposerView(onSend: store.sendText, onVoice: store.sendVoice)
      }

      if store.isTaskDrawerVisible {
        Color.black.opacity(0.18)
          .ignoresSafeArea()
          .contentShape(Rectangle())
          .onTapGesture {
            withAnimation(.easeOut(duration: 0.2)) {
              store.isTaskDrawerVisible = false
            }
          }
          .transition(.opacity)

        TaskDrawerView {
          withAnimation(.easeOut(duration: 0.2)) {
            store.isTaskDrawerVisible = false
          }
          isSettingsPresented = true
        }
        .frame(maxWidth: 350)
        .transition(.move(edge: .leading))
      }
    }
    .animation(.easeOut(duration: 0.22), value: store.isTaskDrawerVisible)
    .sheet(isPresented: $isSettingsPresented) {
      SettingsView(isPresented: $isSettingsPresented)
        .presentationDetents([.height(540), .large])
        .presentationDragIndicator(.visible)
        .presentationCornerRadius(22)
        .presentationBackground(AppPalette.canvas)
    }
  }

  private var topBar: some View {
    HStack {
      Button {
        withAnimation(.easeOut(duration: 0.22)) {
          store.isTaskDrawerVisible = true
        }
      } label: {
        Image(systemName: "sidebar.left")
          .font(.system(size: 17, weight: .medium))
      }
      .accessibilityLabel("打开任务列表")

      Spacer()

      Button {
        store.startNewConversation()
      } label: {
        Image(systemName: "square.and.pencil")
          .font(.system(size: 17, weight: .medium))
      }
      .accessibilityLabel("新建对话")
    }
    .buttonStyle(TopActionButtonStyle())
    .padding(.horizontal, 16)
    .frame(height: 52)
  }
}

private struct TopActionButtonStyle: ButtonStyle {
  func makeBody(configuration: Configuration) -> some View {
    configuration.label
      .frame(width: 38, height: 38)
      .foregroundStyle(AppPalette.primary)
      .background(configuration.isPressed ? AppPalette.primary.opacity(0.12) : AppPalette.surface)
      .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
      .overlay {
        RoundedRectangle(cornerRadius: 11, style: .continuous)
          .stroke(AppPalette.border, lineWidth: 0.75)
      }
  }
}

private struct MessageListView: View {
  let messages: [ChatMessage]
  let onSuggestion: (String) -> Void

  var body: some View {
    ScrollViewReader { proxy in
      ScrollView {
        LazyVStack(spacing: 12) {
          ForEach(messages) { message in
            MessageRow(message: message, onSuggestion: onSuggestion)
              .id(message.id)
          }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, messages.isEmpty ? 0 : 12)
      }
      .scrollIndicators(.hidden)
      .frame(maxWidth: .infinity, maxHeight: .infinity)
      .onChange(of: messages) { _, updatedMessages in
        guard let lastID = updatedMessages.last?.id else {
          return
        }
        withAnimation(.easeOut(duration: 0.2)) {
          proxy.scrollTo(lastID, anchor: .bottom)
        }
      }
    }
  }
}

private struct MessageRow: View {
  let message: ChatMessage
  let onSuggestion: (String) -> Void

  var body: some View {
    switch message.kind {
    case .taskLabel:
      HStack {
        Label(message.text, systemImage: "checklist")
          .font(.system(size: 12, weight: .semibold))
          .foregroundStyle(AppPalette.primary)
          .padding(.horizontal, 10)
          .padding(.vertical, 6)
          .background(AppPalette.primary.opacity(0.10))
          .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
        Spacer()
      }
    case .user:
      bubble(isOutgoing: true) {
        Text(message.text)
          .foregroundStyle(.white)
          .padding(.horizontal, 13)
          .padding(.vertical, 10)
          .background(AppPalette.primary)
          .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
      }
    case .voice:
      bubble(isOutgoing: true) {
        HStack(spacing: 7) {
          Image(systemName: "waveform")
          Text(message.text)
        }
        .font(.system(size: 14, weight: .medium))
        .foregroundStyle(.white)
        .padding(.horizontal, 13)
        .padding(.vertical, 10)
        .background(AppPalette.primary)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
      }
    case .process:
      HStack {
        Label("过程已折叠", systemImage: "chevron.right")
          .font(.system(size: 12, weight: .medium))
          .foregroundStyle(AppPalette.secondaryText)
          .padding(.horizontal, 10)
          .padding(.vertical, 7)
          .background(AppPalette.process)
          .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        Spacer()
      }
    case .assistant:
      bubble(isOutgoing: false) {
        Text(message.text)
          .font(.system(size: 15))
          .foregroundStyle(.primary)
          .padding(.horizontal, 13)
          .padding(.vertical, 11)
          .surfaceCard(radius: 14)
      }
    case .suggestion:
      HStack {
        Button {
          onSuggestion(message.text)
        } label: {
          HStack(spacing: 7) {
            Text(message.text)
            Image(systemName: "arrow.up.right")
          }
          .font(.system(size: 12, weight: .medium))
          .foregroundStyle(AppPalette.primary)
          .padding(.horizontal, 11)
          .padding(.vertical, 8)
          .background(AppPalette.primary.opacity(0.08))
          .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
        }
        Spacer()
      }
    }
  }

  private func bubble<Content: View>(
    isOutgoing: Bool,
    @ViewBuilder content: () -> Content
  ) -> some View {
    HStack {
      if isOutgoing {
        Spacer(minLength: 52)
      }
      content()
        .frame(maxWidth: 310, alignment: isOutgoing ? .trailing : .leading)
      if !isOutgoing {
        Spacer(minLength: 52)
      }
    }
  }
}

private struct ComposerView: View {
  let onSend: (String) -> Void
  let onVoice: () -> Void

  @State private var text = ""
  @GestureState private var isPressingMicrophone = false
  @FocusState private var isTextFieldFocused: Bool

  var body: some View {
    HStack(alignment: .bottom, spacing: 8) {
      microphoneButton

      TextField("输入消息", text: $text, axis: .vertical)
        .focused($isTextFieldFocused)
        .lineLimit(1...4)
        .font(.system(size: 15))
        .submitLabel(.send)
        .onSubmit(send)
        .padding(.vertical, 9)

      Button(action: send) {
        Image(systemName: "arrow.up")
          .font(.system(size: 14, weight: .bold))
          .foregroundStyle(.white)
          .frame(width: 32, height: 32)
          .background(
            text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
              ? Color.secondary.opacity(0.35)
              : AppPalette.primary
          )
          .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
      }
      .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
      .accessibilityLabel("发送")
    }
    .padding(7)
    .background(AppPalette.surface)
    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    .overlay {
      RoundedRectangle(cornerRadius: 16, style: .continuous)
        .stroke(AppPalette.border, lineWidth: 0.8)
    }
    .shadow(color: Color.black.opacity(0.08), radius: 12, y: 4)
    .padding(.horizontal, 14)
    .padding(.top, 8)
    .padding(.bottom, 8)
  }

  private var microphoneButton: some View {
    Image(systemName: "mic")
      .font(.system(size: 17, weight: .medium))
      .foregroundStyle(isPressingMicrophone ? .white : AppPalette.primary)
      .frame(width: 34, height: 34)
      .background(isPressingMicrophone ? AppPalette.primary : Color.clear)
      .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
      .scaleEffect(isPressingMicrophone ? 1.08 : 1)
      .animation(.easeOut(duration: 0.12), value: isPressingMicrophone)
      .contentShape(Rectangle())
      .gesture(
        LongPressGesture(minimumDuration: 0.45)
          .updating($isPressingMicrophone) { current, state, _ in
            state = current
          }
          .onEnded { _ in
            onVoice()
          }
      )
      .accessibilityElement()
      .accessibilityLabel("长按发送语音")
      .accessibilityAddTraits(.isButton)
      .accessibilityAction {
        onVoice()
      }
  }

  private func send() {
    let content = text
    guard !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      return
    }
    text = ""
    onSend(content)
  }
}
