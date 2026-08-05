import SwiftUI

@main
struct PagentIOSApp: App {
  @StateObject private var store = AppStore()

  var body: some Scene {
    WindowGroup {
      RootView()
        .environmentObject(store)
        .preferredColorScheme(store.theme.colorScheme)
    }
  }
}
