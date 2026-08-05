import SwiftUI
import UIKit

enum AppPalette {
  static let canvas = Color(
    uiColor: UIColor { traits in
      traits.userInterfaceStyle == .dark
        ? UIColor(red: 0.055, green: 0.075, blue: 0.105, alpha: 1)
        : UIColor(red: 0.965, green: 0.982, blue: 1, alpha: 1)
    }
  )

  static let surface = Color(
    uiColor: UIColor { traits in
      traits.userInterfaceStyle == .dark
        ? UIColor(red: 0.09, green: 0.12, blue: 0.16, alpha: 1)
        : UIColor.white
    }
  )

  static let raisedSurface = Color(
    uiColor: UIColor { traits in
      traits.userInterfaceStyle == .dark
        ? UIColor(red: 0.12, green: 0.15, blue: 0.20, alpha: 1)
        : UIColor(red: 0.985, green: 0.992, blue: 1, alpha: 1)
    }
  )

  static let primary = Color(red: 0.18, green: 0.48, blue: 0.86)
  static let primarySoft = Color(red: 0.87, green: 0.94, blue: 1)
  static let process = Color(
    uiColor: UIColor { traits in
      traits.userInterfaceStyle == .dark
        ? UIColor(red: 0.16, green: 0.18, blue: 0.22, alpha: 1)
        : UIColor(red: 0.93, green: 0.94, blue: 0.96, alpha: 1)
    }
  )
  static let border = Color(
    uiColor: UIColor { traits in
      traits.userInterfaceStyle == .dark
        ? UIColor.white.withAlphaComponent(0.10)
        : UIColor(red: 0.78, green: 0.84, blue: 0.91, alpha: 0.72)
    }
  )
  static let secondaryText = Color.secondary
  static let danger = Color(red: 0.76, green: 0.24, blue: 0.27)
}

struct SurfaceCard: ViewModifier {
  var radius: CGFloat = 12

  func body(content: Content) -> some View {
    content
      .background(AppPalette.surface)
      .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
      .overlay {
        RoundedRectangle(cornerRadius: radius, style: .continuous)
          .stroke(AppPalette.border, lineWidth: 0.75)
      }
  }
}

extension View {
  func surfaceCard(radius: CGFloat = 12) -> some View {
    modifier(SurfaceCard(radius: radius))
  }
}
