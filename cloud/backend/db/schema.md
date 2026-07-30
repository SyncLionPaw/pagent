## 初始表结构

这版先按 PostgreSQL 设计。

范围只覆盖云端版本最基本的几件事：

- 用户
- 登录
- 工作区
- 项目
- 对话线程
- 消息
- 产物

### 表清单

`users`

- 用户主表
- 一行代表一个云端账号

`user_passwords`

- 本地密码登录
- 密码 hash 单独放，避免混进用户主表

`user_oauth_accounts`

- 第三方登录绑定
- 一个人可以绑定多个外部账号

`user_sessions`

- 浏览器登录会话
- 只存 token hash，不存明文 token

`personal_access_tokens`

- API token
- 面向脚本、CLI、系统集成

`workspaces`

- 团队或个人工作区
- 云端资源先挂在工作区下面

`workspace_members`

- 工作区成员关系
- 负责角色和权限边界

`projects`

- 工作区内项目
- 后面接仓库、运行时配置、部署信息都从这里扩

`threads`

- 对话线程
- 对应一个项目里的一个会话

`messages`

- 线程消息
- 用户、助手、工具消息都落这里

`artifacts`

- 产物元数据
- 文件本体放对象存储，这里只放索引信息

### 当前约定

- `updated_at` 暂时由应用层维护
- 文件正文不进数据库，走对象存储
- token 一律只存 hash
- 线程消息内容保留 `content_text` 和 `content_json` 两份入口，先保证迁移简单

### 先不放进首版的内容

- 审计日志
- 邀请码 / 邮件验证码
- 计费
- 配额
- RBAC 细粒度权限点
- 组织与多层级部门

这些后面都能在这套主干上继续长，不会推翻当前表结构。
