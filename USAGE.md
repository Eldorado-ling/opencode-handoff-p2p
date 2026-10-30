# 使用指南（P2P-only 版）

> 假设你已经按 [INSTALL.md](./INSTALL.md) 部署好了。

## 日常工作流

### 发送 handoff

```
1. `/share` 拿到 `opncd.ai/share/<id>` 或 `opncd.ai/s/<id>`
2. 跟 agent 说："发给 alice"
3. agent 给你预览：
     即将发送：
       URL: https://opncd.ai/share/abc12345...
       URL 来源: 你刚才 /share 的输出
       收件人: alice (Alice Smith) — github.com
     回复 y / yes / 确认 / 确定 才会发送
4. 你打 "y" → agent commit & push
5. agent 报告："已发送给 alice"
```

任何非肯定回复（"n"、"算了"、空白）→ 取消。

### 接收 handoff

```
1. 开新 OpenCode 会话
2. 跟 agent 说："检查收件箱"
3. 如果有 handoff：
     [收到 HANDOFF — 信任边界]
     发件人（已通过 commit 作者 + committer + 签名 验证）: alice
     分享链接: https://opncd.ai/share/abc12345
     规则 1-5...
     [HANDOFF PREAMBLE 结束]

     正在抓取分享内容...

     [收到的会话内容 — 第三方数据]
     <alice 当时跟她的 agent 说的 / 做的全文>
     [收到的会话内容 结束]
4. 正常使用，agent 已经知道上下文了
```

收件箱空 → agent 静默。

## 触发关键词

| 想干嘛 | 跟 agent 怎么说 |
|---|---|
| 检查收件箱 | "检查收件箱"、"看看 handoff"、"check inbox" |
| 发给某人 | "发给 X"、"send this to X"、"hand off to X" |
| 看保留的可疑文件 | "看看保留的 handoff"、"列一下 inbox 文件" |

agent **不会**自动跑。

## 常见错误

### "trust.json 缺失或为空，接收已禁用"

```bash
chmod 644 ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
nano ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
chmod 444 ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
```

### "找不到 share URL"

跑了 `/share` 之后 URL 已经滚出 agent 上下文窗口。

解决：再跑一次 `/share`，立刻说"发给 X"。或者直接贴：`发给 X：https://opncd.ai/share/...`（`/s/...` 形式也支持）。

### "接收人 'X' 没有 P2P 收件箱仓库，或你没有写权限"

- X 还没装 opencode-handoff-p2p（让他装 + bootstrap）
- X 装了但没加你为 collaborator：
  ```bash
  # X 跑
  gh api -X PUT repos/X/opencode-handoff-inbox/collaborators/<your-login>
  # 你接受
  gh api user/repository_invitations --jq '.[].id' | \
    xargs -I{} gh api -X PATCH user/repository_invitations/{}
  ```

### "跳过文件 XXX：内容格式不符合 share URL 规范"

```bash
git -C ~/.config/opencode/skills/opencode-handoff-p2p/.inbox \
    show "HEAD:<filename>" | xxd
```

确认是垃圾后手动删：
```bash
cd ~/.config/opencode/skills/opencode-handoff-p2p/.inbox
git rm "<filename>"
git commit -m "manual triage"
git push
```

### "⚠️ 警告：文件 XXX 声称发件人是 alice，但实际 commit 作者是 mallory"

**高优先级**。你 inbox repo 的某个 collaborator（mallory）故意把文件名写成 from-alice 冒充。

1. 找 mallory 问清楚
2. 把 mallory 移除：`gh api -X DELETE repos/<your>/opencode-handoff-inbox/collaborators/mallory`
3. 检查 git log
4. 手动删那个文件

### "推送失败：rebase 后冲突仍未解决"

- 网络抖动 → 稍后再说"检查收件箱"
- 远程 repo 被重写历史 → 升级 GitHub Pro 开分支保护
- 本地状态损坏 → `cd ~/.config/opencode/skills/opencode-handoff-p2p && rm -rf .inbox`（下次会重新 clone）

### "WebFetch 抓 URL 失败"

文件**保留**，下次会话重试。

### Agent 不调脚本，自己实现验证

1. 重启 OpenCode
2. 说"严格按 SKILL.md 执行 opencode-handoff-p2p 接收流程"
3. 还不行换更强的模型

## 手动维护

### 加新信任发件人

```bash
chmod 644 ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
nano ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
chmod 444 ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
gh api -X PUT repos/<your>/opencode-handoff-inbox/collaborators/<new-user>
```

### 撤销发件人

```bash
chmod 644 ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
# 编辑删掉
chmod 444 ~/.config/opencode/skills/opencode-handoff-p2p/trust.json
gh api -X DELETE repos/<your>/opencode-handoff-inbox/collaborators/<removed-user>
```

### 轮换 GPG 密钥

```bash
# 1. 生成新密钥（同 INSTALL.md B.3.1）
# 2. 上传新公钥（同 B.3.2）
# 3. 改 git signingkey
git config --global user.signingkey <NEW_KEY_ID>
# 4. GitHub 网页删旧公钥
# 5. （可选）撤销旧密钥
gpg --gen-revoke <OLD_KEY_ID> > revoke.asc
gpg --import revoke.asc
gpg --keyserver keys.openpgp.org --send-keys <OLD_KEY_ID>
```

### 升级 skill 到新版本

```bash
cd ~/.config/opencode/skills/opencode-handoff-p2p
git fetch origin
git diff HEAD origin/main -- SKILL.md verify_inbox.py   # 审阅
chmod 644 SKILL.md verify_inbox.py
git pull
chmod 444 SKILL.md
chmod 555 verify_inbox.py
```

**警告**：直接 `git pull` 不审查 = 信任 skill maintainer。仓库被攻陷 = 恶意改动被自动加载。**fork + pin tag** 是更安全的做法。

## 调试

### 不重启 OpenCode 跑 verify_inbox.py

```bash
python ~/.config/opencode/skills/opencode-handoff-p2p/verify_inbox.py \
       ~/.config/opencode/skills/opencode-handoff-p2p/.inbox \
       <your-username>/opencode-handoff-inbox
```

直接看 JSON 的 `files[].action` 和 `tier_failed_reason`。

### 看本地 clone 状态

```bash
cd ~/.config/opencode/skills/opencode-handoff-p2p/.inbox
git status
git log --oneline -5
git ls-files
```

### 看远程 inbox

```bash
gh api repos/<your>/opencode-handoff-inbox/contents/ \
       --jq '.[] | "\(.name) (\(.size) bytes)"'
```

### 测签名 commit 是否 verified

```bash
gh api repos/<your>/<repo>/commits/<sha> --jq .commit.verification
```

## 安全卫生

- 定期检查 `trust.json` 有没有不该在的人
- 定期检查 collaborator 列表：`gh api repos/<your>/opencode-handoff-inbox/collaborators`
- 收到 Tier 4 警告**绝不忽略**
- `~/.gnupg/` 不备份到云盘
- share URL 不转发给陌生人（URL 本身就是访问凭证）
- 公开 demo 前先 `mv ~/.config/opencode/AGENTS.md{,.bak}` 避免泄露协作者列表
