## 初始表结构

先只定鉴权。

当前只保留 4 张表：

- `users`
- `user_passwords`
- `user_oauth_accounts`
- `user_sessions`

### 这 4 张表分别管什么

`users`

- 用户主表
- 先用 `email` 作为唯一账号标识

`user_passwords`

- 密码登录信息
- 密码 hash 单独存

`user_oauth_accounts`

- 第三方登录绑定
- 一个用户可以绑多个外部账号

`user_sessions`

- 浏览器登录会话
- 只存 token hash

### 当前约定

- 数据库先按 PostgreSQL 设计
- `updated_at` 暂时由应用层维护
- token 只存 hash
- 业务表后面再补

### 现在先不定的内容

- 工作区
- 项目
- 对话线程
- 消息
- 产物
- 审计日志
- 邀请码 / 邮件验证码
- API token

这一版先把登录和会话边界收干净，后面的业务表再单独定。
