# SUSPEND 配置功能

## 功能说明

在 `configs/user*.yml` 中设置 `SUSPEND: true` 可暂停抢座并发送钉钉通知。

## 配置文件字段

```yaml
# 抢座暂停开关，true=暂停抢座并发送通知，false=正常抢座
SUSPEND: true
```

## 实现原理

1. 脚本从原始配置文件加载配置，保留 SUSPEND 字段
2. 生成临时配置文件到 `/tmp/`
3. 检查每个配置的 SUSPEND 字段
4. 如果为 `true`，发送钉钉通知「抢座任务已暂停」并退出
5. 如果为 `false`，正常执行抢座

## 用法

### 通过环境变量暂停（临时）
```bash
SUSPEND=true bash book-seat.sh
```

### 通过配置文件永久暂停
编辑 `user1.yml` 或 `user2.yml`，添加：
```yaml
SUSPEND: true
```

## 注意事项

- 配置修改后需重启抢座脚本或等下次 cron 运行才生效
- 并发脚本 `book-seat.sh` 会检查所有用户的 SUSPEND 配置
- 如果任一用户 SUSPEND=true，整个脚本立即退出
- <姓名C>有独立脚本 `book-seat-userC.sh`，不受并发脚本 SUSPEND 影响

## 恢复抢座方法

```bash
# 编辑对应的 yml 文件，将 SUSPEND 改为 false
sed -i 's/SUSPEND: true/SUSPEND: false/' /home/admin/MyQFNULibraryBook/configs/user1.yml
sed -i 's/SUSPEND: true/SUSPEND: false/' /home/admin/MyQFNULibraryBook/configs/user2.yml
```

## 相关脚本

- `~/.hermes/scripts/book-seat.sh` — <姓名A>、<姓名B>并发抢座（19:17）
- `~/.hermes/scripts/book-seat-userC.sh` — <姓名C>独立抢座（19:20:30）

## 版本记录

- 2026-10-08: 新增 SUSPEND 配置功能
- 2026-10-10: 修复临时配置文件不包含SUSPEND字段的bug，改为从原始配置加载
