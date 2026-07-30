## Thread API

这版只定用户私有 thread。

鉴权规则：

- 前端请求带 `Authorization: Bearer <jwt>`
- 后端验签
- 从 JWT claims 里拿当前用户 id
- 请求体里不允许客户端自己传 `owner_user_id`

下面所有接口，都是“当前用户自己的 thread”。

### 1. 创建 thread

`POST /api/threads`

请求：

```json
{
  "title": "新任务",
  "projectPath": "/repo/foo",
  "sandboxBackend": "local",
  "model": "deepseek-v4-flash"
}
```

写入：

- `threads.owner_user_id = 当前用户`
- `threads.title`
- `threads.project_path`
- `threads.sandbox_backend`
- `threads.model`

返回：

```json
{
  "thread": {
    "id": "2b592cf2-9130-46b8-8c96-3d3370d9d5fb",
    "title": "新任务",
    "status": "idle",
    "projectPath": "/repo/foo",
    "sandboxBackend": "local",
    "model": "deepseek-v4-flash",
    "messageCount": 0,
    "lastMessageAt": null,
    "createdAt": "2026-07-30T12:00:00Z",
    "updatedAt": "2026-07-30T12:00:00Z"
  }
}
```

### 2. 列出我的 threads

`GET /api/threads`

查询参数：

- `limit`
- `cursor`
- `includeArchived=false`

后端过滤条件：

- `owner_user_id = 当前用户`
- 默认 `deleted_at is null`

返回：

```json
{
  "items": [
    {
      "id": "2b592cf2-9130-46b8-8c96-3d3370d9d5fb",
      "title": "新任务",
      "status": "running",
      "messageCount": 8,
      "lastMessageAt": "2026-07-30T12:05:00Z",
      "createdAt": "2026-07-30T12:00:00Z",
      "updatedAt": "2026-07-30T12:05:00Z"
    }
  ],
  "nextCursor": null
}
```

### 3. 追加消息

`POST /api/threads/{threadId}/messages`

请求：

```json
{
  "messages": [
    {
      "role": "user",
      "contentText": "帮我看下这个报错"
    }
  ]
}
```

处理规则：

- 先查 `threads.id = threadId and owner_user_id = 当前用户`
- 查不到就返回 `404`
- `seq` 由后端分配
- `thread_messages.owner_user_id` 跟 `threads.owner_user_id` 保持一致
- 写完后回写 `threads.message_count`
- 同时更新 `threads.last_message_at` 和 `threads.updated_at`

返回：

```json
{
  "items": [
    {
      "id": "5f36a977-fadf-4db2-88e1-570fc04d4ef7",
      "threadId": "2b592cf2-9130-46b8-8c96-3d3370d9d5fb",
      "seq": 1,
      "role": "user",
      "contentText": "帮我看下这个报错",
      "createdAt": "2026-07-30T12:01:00Z"
    }
  ]
}
```

### 隔离底线

后端每次都先拿当前用户，再做数据访问。

也就是：

- 不接受客户端上传 `owner_user_id`
- 不允许“按 thread id 直接查”，必须附带当前用户过滤
- `thread_messages` 和 `thread_artifacts` 都冗余存 `owner_user_id`

这样做的目的不是重复，而是把隔离条件写死在数据层，避免后面查询漏条件。
