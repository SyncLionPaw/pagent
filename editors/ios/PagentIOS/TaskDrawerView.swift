import SwiftUI

struct TaskDrawerView: View {
  @EnvironmentObject private var store: AppStore
  @State private var query = ""

  let onOpenSettings: () -> Void

  private var filteredTasks: [WorkTask] {
    let normalizedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !normalizedQuery.isEmpty else {
      return store.tasks
    }
    return store.tasks.filter { task in
      task.title.localizedCaseInsensitiveContains(normalizedQuery)
        || task.subtitle.localizedCaseInsensitiveContains(normalizedQuery)
        || task.participants.localizedCaseInsensitiveContains(normalizedQuery)
    }
  }

  var body: some View {
    VStack(spacing: 0) {
      header
      searchField

      ScrollView {
        LazyVStack(spacing: 8) {
          ForEach(filteredTasks) { task in
            TaskRow(
              task: task,
              isSelected: store.selectedTaskID == task.id
            ) {
              store.loadTask(task)
            }
          }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 12)
      }
      .scrollIndicators(.hidden)

      accountFooter
    }
    .background(AppPalette.surface)
    .overlay(alignment: .trailing) {
      Rectangle()
        .fill(AppPalette.border)
        .frame(width: 0.75)
    }
    .shadow(color: Color.black.opacity(0.12), radius: 18, x: 6)
  }

  private var header: some View {
    HStack {
      VStack(alignment: .leading, spacing: 2) {
        Text("任务")
          .font(.system(size: 19, weight: .bold))
        Text("继续最近的协同上下文")
          .font(.system(size: 11))
          .foregroundStyle(AppPalette.secondaryText)
      }

      Spacer()

      Button {
        withAnimation(.easeOut(duration: 0.2)) {
          store.isTaskDrawerVisible = false
        }
      } label: {
        Image(systemName: "xmark")
          .font(.system(size: 13, weight: .semibold))
          .frame(width: 32, height: 32)
          .background(AppPalette.raisedSurface)
          .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
      }
      .foregroundStyle(.secondary)
      .accessibilityLabel("关闭任务列表")
    }
    .padding(.horizontal, 16)
    .padding(.top, 14)
    .padding(.bottom, 12)
  }

  private var searchField: some View {
    HStack(spacing: 8) {
      Image(systemName: "magnifyingglass")
        .font(.system(size: 13))
        .foregroundStyle(AppPalette.secondaryText)
      TextField("搜索任务、会议或成员", text: $query)
        .font(.system(size: 14))
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
      if !query.isEmpty {
        Button {
          query = ""
        } label: {
          Image(systemName: "xmark.circle.fill")
            .foregroundStyle(AppPalette.secondaryText)
        }
        .accessibilityLabel("清除搜索")
      }
    }
    .padding(.horizontal, 11)
    .frame(height: 38)
    .background(AppPalette.raisedSurface)
    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    .overlay {
      RoundedRectangle(cornerRadius: 10, style: .continuous)
        .stroke(AppPalette.border, lineWidth: 0.75)
    }
    .padding(.horizontal, 12)
  }

  private var accountFooter: some View {
    HStack(spacing: 10) {
      Text("林")
        .font(.system(size: 13, weight: .bold))
        .foregroundStyle(.white)
        .frame(width: 32, height: 32)
        .background(AppPalette.primary)
        .clipShape(Circle())

      VStack(alignment: .leading, spacing: 2) {
        Text("林默")
          .font(.system(size: 13, weight: .semibold))
        Text("企业工作空间")
          .font(.system(size: 10))
          .foregroundStyle(AppPalette.secondaryText)
      }

      Spacer()

      Button(action: onOpenSettings) {
        Image(systemName: "gearshape")
          .font(.system(size: 15, weight: .medium))
          .frame(width: 34, height: 34)
          .background(AppPalette.raisedSurface)
          .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
      }
      .foregroundStyle(AppPalette.primary)
      .accessibilityLabel("打开设置")
    }
    .padding(12)
    .overlay(alignment: .top) {
      Rectangle()
        .fill(AppPalette.border)
        .frame(height: 0.75)
    }
  }
}

private struct TaskRow: View {
  let task: WorkTask
  let isSelected: Bool
  let action: () -> Void

  var body: some View {
    Button(action: action) {
      VStack(alignment: .leading, spacing: 8) {
        HStack(alignment: .firstTextBaseline) {
          Text(task.title)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(.primary)
            .lineLimit(1)
          Spacer(minLength: 8)
          Text(task.relativeTime)
            .font(.system(size: 9))
            .foregroundStyle(AppPalette.secondaryText)
        }

        Text(task.subtitle)
          .font(.system(size: 11))
          .foregroundStyle(AppPalette.secondaryText)
          .lineLimit(2)
          .frame(maxWidth: .infinity, alignment: .leading)

        HStack(spacing: 6) {
          Text(task.status)
            .font(.system(size: 9, weight: .semibold))
            .foregroundStyle(isSelected ? .white : AppPalette.primary)
            .padding(.horizontal, 7)
            .padding(.vertical, 4)
            .background(isSelected ? AppPalette.primary : AppPalette.primary.opacity(0.09))
            .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))

          Text(task.participants)
            .font(.system(size: 9))
            .foregroundStyle(AppPalette.secondaryText)
            .lineLimit(1)
        }
      }
      .padding(11)
      .background(isSelected ? AppPalette.primary.opacity(0.09) : AppPalette.raisedSurface)
      .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
      .overlay {
        RoundedRectangle(cornerRadius: 11, style: .continuous)
          .stroke(
            isSelected ? AppPalette.primary.opacity(0.42) : AppPalette.border,
            lineWidth: 0.75
          )
      }
    }
    .buttonStyle(.plain)
  }
}
