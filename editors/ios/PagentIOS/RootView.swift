import SwiftUI

struct RootView: View {
  @EnvironmentObject private var store: AppStore

  var body: some View {
    Group {
      if store.isAuthenticated {
        WorkspaceView()
          .transition(.opacity)
      } else {
        GuardLoginView()
          .transition(.opacity)
      }
    }
    .animation(.easeInOut(duration: 0.2), value: store.isAuthenticated)
  }
}
