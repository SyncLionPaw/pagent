# pagent iOS

原生 SwiftUI 移动端，覆盖任务侧栏、文本与语音入口、消息流、设置抽屉和 Guard 登录闭环。

## 环境

- Xcode 16+
- iOS 17+
- Swift 5

## 运行

1. 用 Xcode 打开 `PagentIOS.xcodeproj`。
2. 选择 `PagentIOS` Scheme 和任意 iPhone 模拟器。
3. 运行应用。

当前版本使用本地任务数据与模拟回复。`AppStore` 是界面的单一状态源，接入服务时可将发送消息、任务加载和 Guard 登录替换为对应客户端实现。移动端消费 Agent 事件时使用 Wire NDJSON，事件结构见仓库根目录 `docs/wire.md`。
