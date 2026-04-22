# Smart-AI 系统设计 - 待确认问题

## 问题：如何获取用户对话历史

### 背景
Skill 需要获取用户对话历史（包括文本和图片），但目前不确定 OpenClaw 的统一处理方案。

### 方案对比

| 方案 | 说明 | 状态 |
|------|------|------|
| 依赖 OpenClaw 自动传递 | 每次触发 Skill 时，OpenClaw 自动把历史传给 Skill | ❓ 待确认 |
| Skill 自己调用平台工具 | Skill 根据 channel 类型调用 feishu_im_user_get_messages 等工具 | ⚠️ 复杂 |
| 自己存储 | 用户发消息时 Skill 自己保存到文件/数据库 | ✅ 可行但繁琐 |

### 待确认点

1. **OpenClaw 是否会自动把对话历史传给 Skill？**
   - 如果传，Skill 收到的 message 参数中是否包含完整历史？
   - 历史中的图片是格式（URL 还是 token）？

2. **多平台统一方案**
   - 飞书格式：`![image](img_xxx)`
   - Telegram/Discord/其他平台格式？
   - 是否有统一的处理方案？

3. **Skill 获取历史的方式**
   - 是 OpenClaw 自动传入（作为函数参数）？
   - 还是需要 Skill 自己调用工具获取？

### 相关文档

- `/usr/lib/node_modules/openclaw/docs/concepts/messages.md` - 消息机制
- `/usr/lib/node_modules/openclaw/docs/tools/skills.md` - Skill 机制

### 下一步

需要进一步研究 OpenClaw 的消息传递机制，确认 Skill 实际接收到的数据格式。
