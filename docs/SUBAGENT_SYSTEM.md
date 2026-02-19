# 子 Agent 系统 (Subagent System)

solopreneur 的子 Agent 系统允许主 Agent 将复杂、长耗时的任务委派给后台运行的轻量级实例。这种设计实现了 Agent 之间的异步协作（Agent-to-Agent Communication）。

## 1. 核心概念

-   **主 Agent (Main Agent)**: 用户直接交互的对象，负责任务调度和最终总结。
-   **子 Agent (Subagent)**: 由主 Agent 派生的临时实例，专注于完成特定任务。
-   **隔离环境**: 每个子 Agent 拥有独立的 LLM 上下文和系统提示词，但共享相同的工作空间和工具（部分受限）。

## 2. 通信流程 (A2A)

1.  **委派 (Spawn)**:
    主 Agent 调用 `SpawnSubagentTool`。`SubagentManager` 启动一个新的后台 `asyncio` 任务。
2.  **执行 (Execution)**:
    子 Agent 在后台执行自己的“思考-行动”循环。它可以使用：
    -   `ReadFileTool` / `WriteFileTool`: 读写文件。
    -   `ExecTool`: 执行 Shell 命令。
    -   `WebSearchTool` / `WebFetchTool`: 网页搜索与抓取。
3.  **结果通报 (Announce)**:
    任务完成后，子 Agent 将结果封装为 `system` 渠道的 `InboundMessage` 发布到系统的消息总线 (`Message Bus`)。
4.  **唤醒与总结 (Summary)**:
    主 Agent 检测到总线上的系统通知，被唤醒并提取执行结果，最后以简练的语言向用户汇报。

## 3. 设计原则

-   **安全性**: 子 Agent 不允许生成子子 Agent，且通常被禁止向用户直接发送原始消息。
-   **非阻塞**: 子 Agent 在后台运行，不会阻塞主 Agent 处理用户的其他即时询问。
-   **无状态**: 子 Agent 在完成任务后即销毁，不保留长期会话状态。

## 4. 典型场景

-   **调研任务**: “帮我搜一下目前市面上最新的三款折叠屏手机，对比它们的参数并保存到文本文件。”
-   **代码执行**: “在后台运行这个简单的爬虫程序，运行结果出来后告诉我。”
-   **多任务处理**: 当用户一次性要求多个复杂变更时。
