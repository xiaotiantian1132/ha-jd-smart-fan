# HA JD Smart 集成（风扇增强版）

一个用于 Home Assistant 的京东智能云（JD Smart / api.smart.jd.com）集成。在原项目基础上**新增了对京东生态电风扇的支持**（如艾美特 FA18-AD16），并优化了从 iOS 设备提取登录凭证的流程。

> 本项目是 [orangeboyChen/ha-jd-smart](https://github.com/orangeboyChen/ha-jd-smart) 的分支增强版本，遵循原项目 MIT 协议。核心贡献：风扇（设备类目 `102007`）平台支持 + iOS 免 root 提取 A2 凭证的实操方法。

---

## 目录

- [功能特性](#功能特性)
- [支持设备](#支持设备)
- [安装](#安装)
- [获取凭证（关键步骤）](#获取凭证关键步骤)
- [配置项字段说明](#配置项字段说明)
- [风扇实体说明](#风扇实体说明)
- [凭证的自动刷新与维护](#凭证的自动刷新与维护)
- [安全说明](#安全说明)
- [已知限制](#已知限制)
- [致谢与许可](#致谢与许可)

---

## 功能特性

- 通过京东智能云 API 读取设备列表、状态快照，下发控制指令（云端轮询）
- **原项目支持**：空调（climate）、开关、选择、传感器实体
- **本分支新增**：
  - 电风扇（`fan`）实体：开关、风速（0–11 档映射为百分比）、7 种运行模式、左右摆头
  - 从 iOS 设备（含巨魔/TrollStore 环境）的 App 日志中直接提取明文 A2 凭证，**无需 root、无需 Frida、无需模拟器**
  - 配置时跳过首次 token 刷新，避免跨 App 刷新导致凭证错配

## 支持设备

| 设备类型 | 类目 ID | 实体平台 | 状态 |
|---|---|---|---|
| 空调 | `101001` | climate | 原项目支持 |
| 电风扇（含艾美特 FA18-AD16 等） | `102007` | **fan（本分支新增）** | 已实测 |

> 其他类目暂不支持。如果遇到未识别的设备，集成会在 HA 通知里给出类目 ID 和 stream 信息，欢迎提 issue 或 PR。

---

## 安装

### 方式一：手动安装（推荐）

1. 确认 HA 版本 ≥ 2024.x（本分支在 **HA 2026.11** 上实测）。
2. 通过 SSH / Samba / File Editor 将本仓库的 `custom_components/jd_smart/` 整个目录复制到 HA 配置目录下的 `custom_components/`：

   ```
   <HA 配置目录>/
   └── custom_components/
       └── jd_smart/          # ← 就是这个目录
           ├── __init__.py
           ├── api.py
           ├── climate.py
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── entity.py
           ├── fan.py
           ├── manifest.json
           ├── strings.json
           ├── ...
           └── translations/
   ```

3. **重启 Home Assistant**（新增/更换集成代码必须重启，reload 不会重新加载 Python 模块）。
4. 在 HA：设置 → 设备与服务 → 添加集成 → 搜索 `JD Smart`。

### 方式二：HACS（自定义仓库）

1. HACS → 集成 → 右上角菜单 → 自定义仓库 → 添加本仓库地址（`https://github.com/xiaotiantian1132/ha-jd-smart-fan`），类型选 `Integration`。
2. 在 HACS 中搜索并安装 `JD Smart (Fan Edition)`。
3. 重启 HA，然后添加集成。

---

## 获取凭证（关键步骤）

集成的配置表单需要填写一组京东登录凭证。**A2（tgt）是核心**，网关只认它，网页端凭证（thor / pt_key 等）全部无效。下面给出两种获取方式，**推荐方式 A**。

### 方式 A：从 iOS 设备日志提取（免 root，推荐）

适用：手机上装有京东小家 App，并且能通过巨魔（TrollStore）等工具读取 App 的数据容器。

原理：京东小家 iOS 版会把登录凭证和设备信息以**明文**打印到运行日志中（`Library/Caches/JDXJ_LOG/*.log`），日志属于 App 沙盒内文件，用带文件管理权限的工具即可导出。

步骤：

1. 在 iOS 手机上正常打开京东小家 App，确认已登录，并至少进入一次设备列表页（让日志写入凭证）。
2. 用巨魔版文件管理器（如 Filza）进入京东小家的数据容器：
   `/var/mobile/Containers/Data/Application/<UUID>/`
   （可在巨魔的文件管理/应用列表中找到京东小家并直接跳转到容器）
3. 找到目录 `Library/Caches/JDXJ_LOG/`，把里面的 `com.jd.iots 日期--时间.log` 导出/压缩后传到电脑。
4. 在日志中搜索关键字 `tgt :`，会看到一段类似下面的记录：

   ```
   flutterCall:deviceInfo | callback:{
     tgt : AAJ........(很长一串),
     deviceId : xxxxxxxxxxxxxxxx,
     platform : iPhone,
     systemVersion : 16.1.1,
     pin : jd_xxxxxxxx,
     appVersion : 2.5.0,
     baseUrl : https://api.smart.jd.com
   }
   ```

5. 记下 `tgt`、`deviceId`、`pin`、`platform`、`systemVersion`、`appVersion`、`channel`（通常在同批日志的 URL 参数里，如 `channel=AppStore`）。
6. 按下一节构造 `cookie`，填入 HA 配置表单。

> 也可以用其他方式导出 App 容器（如 `shotbackups`、备份提取等），只要能拿到 `JDXJ_LOG` 日志即可。

### 方式 B：Root 设备 + Frida hook（备选）

适用于 Android 真机已 root 的情况：

1. Root 设备安装京东小家 App 并登录。
2. 用 Frida hook `WJLoginHelper.getA2()`，或直接读取 App 私有目录中的 `JDLoginInfo.plist` / 登录存储（其中 `a2` 字段通常是加密的，hook 拿到的是明文）。
3. 拿到明文 A2 后按同样方式填写。

> 注意：x86 模拟器（雷电、MuMu 等）因 houdini 转译层兼容性问题，可能无法启动该 App；建议用 ARM 真机。

---

## 配置项字段说明

添加集成时（设置 → 添加集成 → JD Smart）会要求填写以下字段：

| 字段 | 含义 | 示例 / 获取方式 |
|---|---|---|
| **Cookie** | 请求 Cookie，必须含 `wskey=<tgt>`，通常还带 `pin` / `pt_pin` / `pwdt_id` | `pin=<PIN>; pt_pin=<PIN>; pwdt_id=<PIN>; wskey=<TGT>` |
| **TGT**（A2） | 核心登录令牌，网关据此鉴权，来自日志的 `tgt` | `AAJ...`（长字符串） |
| **Pin** | 京东账号标识，来自日志的 `pin` | `jd_xxxxxx` |
| **Device ID** | 一个设备标识（用于构造签名和请求参数），来自日志 `deviceId` | 32 位十六进制串 |
| **Platform** | 平台，签名算法的组成部分 | iOS 填 `iPhone`；Android 填 `Android`（**必须与实际一致，否则 401**） |
| **App Version** | App 版本号，签名组成部分 | 日志里的 `appVersion`，如 `2.5.0` |
| **Device Model** | 机型，签名组成部分 | 日志里的 `hard_platform` 值（如 `iPhoneXX,X` / `PKR110`），按你设备实际值填 |
| **Platform Version** | 系统版本，签名组成部分 | 如 `16.1.1` |
| **Channel** | 渠道 | 如 `AppStore`；Android 常见 `76161171` |
| **User Agent** | HTTP UA | 可留默认，或填日志中的真实 UA |

**Cookie 的构造**（把上一步拿到的值代入）：

```
pin=<PIN>; pt_pin=<PIN>; pwdt_id=<PIN>; wskey=<TGT>
```

其中 `<TGT>` 就是 `tgt` 字段的值。签名算法会绑定 `platform + app_version + device_model + platform_version + 年积日`，所以这四个字段必须与提取凭证时的 App 环境一致，**任意一个不对都会返回 `401 token invalid`**。

提交后，集成会拉取设备列表让你勾选要接入的设备；本分支已支持风扇，可直接选择电风扇设备。

---

## 风扇实体说明

接入后，每台电风扇会生成一个 `fan` 实体，命名格式为设备名（可在 HA 中改）。

| 功能 | 对应 stream | 取值 / 说明 |
|---|---|---|
| 开关 | `Power` | `0` 关 / `1` 开 |
| 风速 | `Wind` | `0`–`11` 档，映射为 HA 的 0–100% 风速 |
| 运行模式 | `Mode` | 7 种：`normal` 普通 / `smart` 智能 / `auto` 自动 / `sleep` 睡眠 / `soft` 柔和 / `cool` 冷房 / `silent` 静音 |
| 左右摆头 | `Horizontal` | `0` 关 / `1` 开（作为 HA 的 oscillate） |

> 设备快照里通常还有 `Vertical`（上下摆头）、`HorizontalDivision`（摆幅 0–8）、`Timing`（定时）等 stream，本分支暂未全部暴露为实体，欢迎 PR 扩展。

状态更新：默认每 60 秒轮询一次快照；下发控制指令后会立即快速刷新状态。

---

## 凭证的自动刷新与维护

- 集成内置 **A2 自动刷新**（调用京东 `wlogin` 的 `refreshA2`），token 过期时由 coordinator 自动续期并写回配置。
- 但从京东小家 iOS App 提取的 A2 属于“跨 App”凭证，自动刷新路径**未在所有环境验证**。A2 有效期通常约 180 天。
- 如果发现实体全部变为不可用 / 出现认证失败通知：
  1. 按[方式 A](#方式-a从-ios-设备日志提取免-root推荐)重新从手机日志提取新的 `tgt`；
  2. 在 HA：设置 → 设备与服务 → JD Smart → 重新配置，填入新的 Cookie 和 TGT；
  3. 或使用集成提供的“刷新凭证”流程。

---

## 安全说明

- **凭证只存在你自己的 Home Assistant 配置中**，集成代码不会上传、不联网发送凭证到任何第三方。
- 集成仅与官方域名 `api.smart.jd.com` / `wlogin.m.jd.com` 通信。
- 本项目代码经过脱敏检查，**不含任何真实 tgt / pin / cookie / 设备号硬编码**。
- 建议：不要把包含真实凭证的配置文件、日志、截图提交到 GitHub 或发到公开渠道；分享问题时请打码 `tgt`、`pin`、`cookie`、`device_id`。
- 发布到 GitHub 前请按文末清单替换占位符，并再次全局搜索敏感串。

---

## 已知限制

- 需联网（云端 API），不支持纯本地控制；断网时无法控制。
- 只支持京东智能云生态中已适配的类目（空调 `101001`、电风扇 `102007`）。
- 风扇的部分 stream（上下摆头、摆幅、定时）暂未做成实体。
- 原项目的 climate 平台有 HA 2027.11 的 deprecated 属性警告（不影响当前使用，属上游待修复项）。
- x86 安卓模拟器普遍无法运行京东小家 App，凭证提取建议用 ARM 真机（iOS 或 Android）。

---

## 如果你想 Fork 本仓库

- 修改 `manifest.json` 里的 `codeowners` / `documentation` / `issue_tracker` 为你自己的仓库信息。
- 提交前全局搜索 `AAJ`、`pin=`、`wskey`、`jd_` 等，确认没有把真实凭证提交进去。
- 请保留原项目 MIT 声明与作者署名（见 LICENSE / 致谢）。
- 也欢迎把风扇支持直接贡献给[原项目](https://github.com/orangeboyChen/ha-jd-smart)，让更多用户受益。

---

## 致谢与许可

- 基于 [orangeboyChen/ha-jd-smart](https://github.com/orangeboyChen/ha-jd-smart)（MIT License）改造，感谢原作者完成协议与签名算法的逆向。
- 本项目同样以 MIT License 发布，详见 [LICENSE](LICENSE)。
- 参考文章：[京东小家接入 Home Assistant 记录](https://post.smzdm.com/p/arz6n7nz/)（smzdm，48 小时逆向实战）。
