import SwiftUI

struct SettingsView: View {
  @EnvironmentObject private var store: AppStore
  @Binding var isPresented: Bool

  @State private var infoTitle = ""
  @State private var isInfoPresented = false

  var body: some View {
    ScrollView {
      VStack(spacing: 16) {
        titleArea
        accountCard
        settingsList
        logoutArea
      }
      .padding(.horizontal, 16)
      .padding(.top, 10)
      .padding(.bottom, 28)
    }
    .scrollIndicators(.hidden)
    .background(AppPalette.canvas)
    .alert(infoTitle, isPresented: $isInfoPresented) {
      Button("知道了", role: .cancel) {}
    } message: {
      Text(
        infoTitle == "隐私协议"
          ? "隐私协议将在正式服务地址配置后打开。"
          : "当前为移动端交互原型版本。")
    }
  }

  private var titleArea: some View {
    HStack(alignment: .center) {
      VStack(alignment: .leading, spacing: 3) {
        Text("设置")
          .font(.system(size: 22, weight: .bold))
        Text("账号、外观与安全")
          .font(.system(size: 11))
          .foregroundStyle(AppPalette.secondaryText)
      }

      Spacer()

      Button {
        isPresented = false
      } label: {
        Image(systemName: "xmark")
          .font(.system(size: 13, weight: .semibold))
          .frame(width: 32, height: 32)
          .background(AppPalette.raisedSurface)
          .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
      }
      .foregroundStyle(.secondary)
      .accessibilityLabel("关闭设置")
    }
  }

  private var accountCard: some View {
    HStack(spacing: 12) {
      Text("林")
        .font(.system(size: 17, weight: .bold))
        .foregroundStyle(.white)
        .frame(width: 44, height: 44)
        .background(
          LinearGradient(
            colors: [AppPalette.primary, Color(red: 0.35, green: 0.65, blue: 0.95)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
          )
        )
        .clipShape(Circle())

      VStack(alignment: .leading, spacing: 4) {
        Text("林默")
          .font(.system(size: 15, weight: .semibold))
        Label("企业工作空间", systemImage: "building.2")
          .font(.system(size: 10))
          .foregroundStyle(AppPalette.secondaryText)
      }

      Spacer()

      Image(systemName: "checkmark.shield.fill")
        .font(.system(size: 17))
        .foregroundStyle(AppPalette.primary)
        .accessibilityLabel("账号已通过 Guard 验证")
    }
    .padding(14)
    .background(AppPalette.primary.opacity(0.07))
    .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
    .overlay {
      RoundedRectangle(cornerRadius: 13, style: .continuous)
        .stroke(AppPalette.primary.opacity(0.17), lineWidth: 0.8)
    }
  }

  private var settingsList: some View {
    VStack(spacing: 0) {
      HStack(spacing: 12) {
        settingIcon("circle.lefthalf.filled")
        VStack(alignment: .leading, spacing: 8) {
          Text("主题")
            .font(.system(size: 14, weight: .medium))
          Picker("主题", selection: $store.theme) {
            ForEach(AppTheme.allCases) { theme in
              Text(theme.title).tag(theme)
            }
          }
          .pickerStyle(.segmented)
          .labelsHidden()
        }
      }
      .padding(13)

      Divider()
        .padding(.leading, 52)

      SettingRow(
        icon: "hand.raised",
        title: "隐私协议",
        subtitle: "了解数据和权限使用方式"
      ) {
        presentInfo("隐私协议")
      }

      Divider()
        .padding(.leading, 52)

      SettingRow(
        icon: "clock.arrow.circlepath",
        title: "更新日志",
        subtitle: "查看版本变化"
      ) {
        presentInfo("更新日志")
      }
    }
    .surfaceCard(radius: 13)
  }

  private var logoutArea: some View {
    Button {
      isPresented = false
      store.logout()
    } label: {
      HStack {
        Image(systemName: "rectangle.portrait.and.arrow.right")
        Text("退出登录")
        Spacer()
      }
      .font(.system(size: 14, weight: .medium))
      .foregroundStyle(AppPalette.danger)
      .padding(.horizontal, 14)
      .frame(height: 48)
    }
    .background(AppPalette.danger.opacity(0.055))
    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    .overlay {
      RoundedRectangle(cornerRadius: 12, style: .continuous)
        .stroke(AppPalette.danger.opacity(0.16), lineWidth: 0.75)
    }
  }

  private func settingIcon(_ name: String) -> some View {
    Image(systemName: name)
      .font(.system(size: 14, weight: .medium))
      .foregroundStyle(AppPalette.primary)
      .frame(width: 28, height: 28)
      .background(AppPalette.primary.opacity(0.09))
      .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
  }

  private func presentInfo(_ title: String) {
    infoTitle = title
    isInfoPresented = true
  }
}

private struct SettingRow: View {
  let icon: String
  let title: String
  let subtitle: String
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      HStack(spacing: 12) {
        Image(systemName: icon)
          .font(.system(size: 14, weight: .medium))
          .foregroundStyle(AppPalette.primary)
          .frame(width: 28, height: 28)
          .background(AppPalette.primary.opacity(0.09))
          .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

        VStack(alignment: .leading, spacing: 3) {
          Text(title)
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(.primary)
          Text(subtitle)
            .font(.system(size: 10))
            .foregroundStyle(AppPalette.secondaryText)
        }

        Spacer()

        Image(systemName: "chevron.right")
          .font(.system(size: 11, weight: .semibold))
          .foregroundStyle(AppPalette.secondaryText)
      }
      .padding(.horizontal, 13)
      .frame(height: 58)
    }
    .buttonStyle(.plain)
  }
}

struct GuardLoginView: View {
  @EnvironmentObject private var store: AppStore
  @State private var isSigningIn = false

  var body: some View {
    ZStack {
      AppPalette.canvas
        .ignoresSafeArea()

      VStack(spacing: 0) {
        Spacer()

        ZStack {
          RoundedRectangle(cornerRadius: 18, style: .continuous)
            .fill(AppPalette.primary.opacity(0.09))
            .frame(width: 72, height: 72)
          Image(systemName: "checkmark.shield")
            .font(.system(size: 31, weight: .medium))
            .foregroundStyle(AppPalette.primary)
        }
        .padding(.bottom, 22)

        Text("Guard 安全验证")
          .font(.system(size: 25, weight: .bold))
          .padding(.bottom, 8)

        Text("使用企业账号验证身份，继续访问协同任务。")
          .font(.system(size: 14))
          .foregroundStyle(AppPalette.secondaryText)
          .multilineTextAlignment(.center)
          .padding(.horizontal, 34)
          .padding(.bottom, 28)

        Button {
          guard !isSigningIn else {
            return
          }
          isSigningIn = true
          Task {
            try? await Task.sleep(for: .milliseconds(500))
            store.loginWithGuard()
            isSigningIn = false
          }
        } label: {
          HStack(spacing: 8) {
            if isSigningIn {
              ProgressView()
                .tint(.white)
            } else {
              Image(systemName: "lock.shield")
            }
            Text(isSigningIn ? "正在验证" : "使用 Guard 登录")
          }
          .font(.system(size: 15, weight: .semibold))
          .foregroundStyle(.white)
          .frame(maxWidth: .infinity)
          .frame(height: 48)
          .background(AppPalette.primary)
          .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        }
        .disabled(isSigningIn)
        .padding(.horizontal, 28)

        Spacer()

        Label("企业账号保护", systemImage: "lock")
          .font(.system(size: 10))
          .foregroundStyle(AppPalette.secondaryText)
          .padding(.bottom, 12)
      }
    }
  }
}
