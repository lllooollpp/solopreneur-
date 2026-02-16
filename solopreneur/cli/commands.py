"""nanobot �?CLI 命令�?""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from solopreneur import __version__, __logo__
from solopreneur.config.logging import setup_logging

# 初始化日�?
setup_logging()

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - 个人 AI 助手",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanobot - 个人 AI 助手�?""
    pass


# ============================================================================
# 设置与引�?(Onboard / Setup)
# ============================================================================


@app.command()
def onboard():
    """初始�?nanobot 配置和工作区�?""
    from solopreneur.config.loader import get_config_path, save_config
    from solopreneur.config.schema import Config
    from solopreneur.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]配置文件已存在：{config_path}[/yellow]")
        if not typer.confirm("是否覆盖�?):
            raise typer.Exit()
    
    # 创建默认配置
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] 已在 {config_path} 创建配置")
    
    # 创建工作�?
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] 已在 {workspace} 创建工作�?)
    
    # 创建默认引导文件
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} nanobot 已准备就绪！")
    console.print("\n后续步骤�?)
    console.print("  1. 将你�?API 密钥添加�?[cyan]~/.nanobot/config.json[/cyan]")
    console.print("     在此处获取：https://openrouter.ai/keys")
    console.print("  2. 开始聊天：[cyan]nanobot agent -m \"你好！\"[/cyan]")
    console.print("\n[dim]想要使用 Telegram/WhatsApp？请参阅：https://github.com/HKUDS/nanobot#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """创建默认工作区模板文件�?""
    templates = {
        "AGENTS.md": """# Agent 指令

你是一个乐于助人的 AI 助手。请保持简洁、准确且友好�?

## 准则

- 在执行操作前始终解释你正在做什�?
- 如果请求模糊，请要求澄清
- 使用工具来帮助完成任�?
- 在记忆文件中记录重要信息
""",
        "SOUL.md": """# 灵魂 (Soul)

我是 nanobot，一个轻量级�?AI 助手�?

## 性格

- 乐于助人且友�?
- 言简意赅
- 好奇且好�?

## 价值观

- 准确度高于速度
- 用户隐私和安�?
- 行动透明
""",
        "USER.md": """# 用户

在此处填写用户信息�?

## 偏好

- 沟通风格：（随�?正式�?
- 时区：（你的时区�?
- 语言：（你的首选语言�?
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]已创�?{filename}[/dim]")
    
    # 创建 memory 目录�?MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# 长期记忆

此文件存储应在会话之间持久保存的重要信息�?

## 用户信息

（关于用户的重要事实�?

## 偏好

（随时间掌握的用户偏好）

## 重要笔记

（需要记住的事情�?
""")
        console.print("  [dim]已创�?memory/MEMORY.md[/dim]")


# ============================================================================
# 网关 / 服务�?(Gateway / Server)
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="网关端口"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """启动 nanobot 网关�?""
    from solopreneur.config.loader import load_config, get_data_dir
    from solopreneur.bus.queue import MessageBus
    from solopreneur.providers.litellm_provider import LiteLLMProvider
    from solopreneur.agent.core.loop import AgentLoop
    from solopreneur.channels.manager import ChannelManager
    from solopreneur.cron.service import CronService
    from solopreneur.cron.types import CronJob
    from solopreneur.heartbeat.service import HeartbeatService
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    console.print(f"{__logo__} 正在启动 nanobot 网关，端�?{port}...")
    
    config = load_config()
    
    # 创建组件
    bus = MessageBus()
    
    # 创建提供商（支持 OpenRouter, Anthropic, OpenAI, Bedrock�?
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agents.defaults.model
    is_bedrock = model.startswith("bedrock/")

    if not api_key and not is_bedrock:
        console.print("[red]错误：未配置 API 密钥。[/red]")
        console.print("�?~/.nanobot/config.json 中的 providers.openrouter.apiKey 下设置一个�?)
        raise typer.Exit(1)
    
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    # 创建 agent
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        max_session_tokens=config.agents.defaults.max_tokens_per_session,
        max_total_time=config.agents.defaults.agent_timeout,
    )
    
    # 创建定时服务
    async def on_cron_job(job: CronJob) -> str | None:
        """通过 agent 执行定时任务�?""
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}"
        )
        # 可选地交付给通道
        if job.payload.deliver and job.payload.to:
            from solopreneur.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "whatsapp",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path, on_job=on_cron_job)
    
    # 创建心跳服务
    async def on_heartbeat(prompt: str) -> str:
        """通过 agent 执行心跳�?""
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 分钟
        enabled=True
    )
    
    # 创建通道管理�?
    channels = ChannelManager(config, bus)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] 已启用通道：{', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]警告：未启用任何通道[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] 定时任务：{cron_status['jobs']} 个已调度任务")
    
    console.print(f"[green]✓[/green] 心跳：每 30 分钟一�?)
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\n正在关机...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent 命令
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="发送给 agent 的消�?),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="会话 ID"),
):
    """直接�?agent 交互�?""
    from solopreneur.config.loader import load_config
    from solopreneur.bus.queue import MessageBus
    from solopreneur.providers.litellm_provider import LiteLLMProvider
    from solopreneur.agent.core.loop import AgentLoop
    
    config = load_config()
    
    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agents.defaults.model
    is_bedrock = model.startswith("bedrock/")

    if not api_key and not is_bedrock:
        console.print("[red]错误：未配置 API 密钥。[/red]")
        raise typer.Exit(1)

    bus = MessageBus()
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.agents.defaults.model
    )
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        max_session_tokens=config.agents.defaults.max_tokens_per_session,
        max_total_time=config.agents.defaults.agent_timeout,
    )
    
    if message:
        # 单次消息模式
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")
        
        asyncio.run(run_once())
    else:
        # 交互模式
        console.print(f"{__logo__} 交互模式 (�?Ctrl+C 退�?\n")
        
        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]你：[/bold blue] ")
                    if not user_input.strip():
                        continue
                    
                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    console.print("\n再见�?)
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# 通道命令
# ============================================================================


channels_app = typer.Typer(help="管理通道")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """显示通道状态�?""
    from solopreneur.config.loader import load_config

    config = load_config()

    table = Table(title="通道状�?)
    table.add_column("通道", style="cyan")
    table.add_column("已启�?, style="green")
    table.add_column("配置", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "�? if wa.enabled else "�?,
        wa.bridge_url
    )

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]未配置[/dim]"
    table.add_row(
        "Telegram",
        "�? if tg.enabled else "�?,
        tg_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """获取 bridge 目录，根据需要进行设置�?""
    import shutil
    import subprocess
    
    # 用户�?bridge 位置
    user_bridge = Path.home() / ".nanobot" / "bridge"
    
    # 检查是否已构建
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # 检�?npm
    if not shutil.which("npm"):
        console.print("[red]未找�?npm。请安装 Node.js >= 18。[/red]")
        raise typer.Exit(1)
    
    # 查找�?bridge：首先检查包数据，然后检查源目录
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (已安�?
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # 仓库根目�?bridge (开发中)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]未找�?bridge 源码。[/red]")
        console.print("请尝试重新安装：pip install --force-reinstall nanobot")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} 正在设置 bridge...")
    
    # 复制到用户目�?
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # 安装和构�?
    try:
        console.print("  正在安装依赖...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  正在构建...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] Bridge 已就绪\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]构建失败：{e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """通过二维码链接设备�?""
    import subprocess
    
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} 正在启动 bridge...")
    console.print("请扫描二维码进行连接。\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge 启动失败：{e}[/red]")
    except FileNotFoundError:
        console.print("[red]未找�?npm。请安装 Node.js。[/red]")


# ============================================================================
# Cron 命令
# ============================================================================

cron_app = typer.Typer(help="管理定时任务")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="包含已禁用的任务"),
):
    """列出调度任务�?""
    from solopreneur.config.loader import get_data_dir
    from solopreneur.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("没有调度的任务�?)
        return
    
    table = Table(title="调度任务")
    table.add_column("ID", style="cyan")
    table.add_column("名称")
    table.add_column("调度")
    table.add_column("状�?)
    table.add_column("下次运行")
    
    import time
    for job in jobs:
        # 格式化调�?
        if job.schedule.kind == "every":
            sched = f"�?{(job.schedule.every_ms or 0) // 1000} �?
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "一次�?
        
        # 格式化下次运行时�?
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time
        
        status = "[green]已启用[/green]" if job.enabled else "[dim]已禁用[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="任务名称"),
    message: str = typer.Option(..., "--message", "-m", help="发送给 agent 的消�?),
    every: int = typer.Option(None, "--every", "-e", help="每隔 N 秒运行一�?),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron 表达�?(例如 '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="在指定时间运行一�?(ISO 格式)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="将响应交付给通道"),
    to: str = typer.Option(None, "--to", help="接收�?),
    channel: str = typer.Option(None, "--channel", help="交付通道 (例如 'telegram', 'whatsapp')"),
):
    """添加调度任务�?""
    from solopreneur.config.loader import get_data_dir
    from solopreneur.cron.service import CronService
    from solopreneur.cron.types import CronSchedule
    
    # 确定调度类型
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]错误：必须指�?--every, --cron �?--at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )
    
    console.print(f"[green]✓[/green] 已添加任�?'{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="要移除的任务 ID"),
):
    """移除调度任务�?""
    from solopreneur.config.loader import get_data_dir
    from solopreneur.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] 已移除任�?{job_id}")
    else:
        console.print(f"[red]未找到任�?{job_id}[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="任务 ID"),
    disable: bool = typer.Option(False, "--disable", help="禁用而不是启�?),
):
    """启用或禁用任务�?""
    from solopreneur.config.loader import get_data_dir
    from solopreneur.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "已禁�? if disable else "已启�?
        console.print(f"[green]✓[/green] 任务 '{job.name}' {status}")
    else:
        console.print(f"[red]未找到任�?{job_id}[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="要运行的任务 ID"),
    force: bool = typer.Option(False, "--force", "-f", help="即使已禁用也运行"),
):
    """手动运行任务�?""
    from solopreneur.config.loader import get_data_dir
    from solopreneur.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    async def run():
        return await service.run_job(job_id, force=force)
    
    if asyncio.run(run()):
        console.print(f"[green]✓[/green] 任务已执�?)
    else:
        console.print(f"[red]运行任务 {job_id} 失败[/red]")


# ============================================================================
# 登录命令
# ============================================================================


@app.command()
def login(
    provider: str = typer.Option("github-copilot", "--provider", "-p", help="认证提供商（github-copilot�?),
    slot: int = typer.Option(1, "--slot", "-s", help="账号槽位编号 (1-5)，用于多账号负载均衡"),
    label: str = typer.Option("", "--label", "-l", help="账号标签 (�?'工作�?, '个人�?)"),
):
    """登录到模型提供商（支持多账号）�?""
    import asyncio
    
    if provider != "github-copilot":
        console.print(f"[red]错误：不支持的提供商 '{provider}'[/red]")
        console.print("支持的提供商：github-copilot")
        raise typer.Exit(1)
    
    if not (1 <= slot <= 10):
        console.print("[red]错误：槽位编号范�?1-10[/red]")
        raise typer.Exit(1)
    
    slot_label = label or f"账号{slot}"
    console.print(f"{__logo__} GitHub Copilot 登录 �?[cyan]Slot {slot}[/cyan] ({slot_label})\n")
    
    async def do_login():
        from solopreneur.providers.github_copilot import GitHubCopilotProvider
        
        copilot = GitHubCopilotProvider()
        
        try:
            # 启动设备流程
            console.print("[cyan]正在启动 OAuth 设备流程...[/cyan]")
            flow_response = await copilot.start_device_flow()
            
            console.print("\n[bold green]请在浏览器中完成授权：[/bold green]")
            console.print(f"  1. 访问: [bold cyan]{flow_response.verification_uri}[/bold cyan]")
            console.print(f"  2. 输入代码: [bold yellow]{flow_response.user_code}[/bold yellow]")
            console.print("\n[dim]等待授权...[/dim]\n")
            
            # 轮询 token
            github_token = await copilot.poll_for_token(flow_response.device_code, flow_response.interval)
            
            # 获取 Copilot token
            copilot_token, expires_at = await copilot.get_copilot_token(github_token)
            
            # 写入 Token �?
            copilot.pool.add_slot(
                slot_id=slot,
                github_access_token=github_token,
                copilot_token=copilot_token,
                expires_at=expires_at,
                label=slot_label,
            )
            
            console.print(f"[green]✓[/green] Slot {slot} ({slot_label}) 登录成功�?)
            console.print(f"[dim]过期时间: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
            
            # 显示池状�?
            pool_status = copilot.pool.get_status()
            console.print(f"\n[bold]Token 池状态：{len(pool_status)} 个账号[/bold]")
            for s in pool_status:
                state_color = {"active": "green", "cooling": "yellow", "expired": "yellow", "dead": "red"}.get(s["state"], "white")
                console.print(f"  Slot {s['slot_id']} ({s['label']}): [{state_color}]{s['state']}[/{state_color}]")
            
            await copilot.close()
                
        except Exception as e:
            console.print(f"[red]登录失败：{e}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(do_login())


# ============================================================================
# Token 池管理命�?
# ============================================================================

pool_app = typer.Typer(help="管理多账�?Token �?)
app.add_typer(pool_app, name="pool")


@pool_app.command("status")
def pool_status():
    """显示 Token 池状态�?""
    from solopreneur.providers.github_copilot import GitHubCopilotProvider
    
    copilot = GitHubCopilotProvider()
    status = copilot.pool.get_status()
    
    if not status:
        console.print("[yellow]Token 池为空。请运行 `nanobot login --slot 1` 添加账号。[/yellow]")
        return
    
    table = Table(title="Token 池状�?)
    table.add_column("Slot", style="cyan", justify="center")
    table.add_column("标签", style="white")
    table.add_column("状�?, justify="center")
    table.add_column("冷却剩余", justify="center")
    table.add_column("总请�?, justify="right")
    table.add_column("429次数", justify="right")
    table.add_column("Token 过期", style="dim")
    
    for s in status:
        state_color = {"active": "green", "cooling": "yellow", "expired": "yellow", "dead": "red"}.get(s["state"], "white")
        table.add_row(
            str(s["slot_id"]),
            s["label"],
            f"[{state_color}]{s['state']}[/{state_color}]",
            s["cooling_remaining"] or "-",
            str(s["total_requests"]),
            str(s["total_429s"]),
            s["token_expires"][:19],
        )
    
    console.print(table)
    console.print(f"\n可用 / 总计: [bold]{copilot.pool.active_count}[/bold] / {copilot.pool.size}")


@pool_app.command("remove")
def pool_remove(
    slot_id: int = typer.Argument(..., help="要移除的槽位编号"),
):
    """移除 Token 池中的某个槽位�?""
    from solopreneur.providers.github_copilot import GitHubCopilotProvider
    
    copilot = GitHubCopilotProvider()
    if copilot.pool.remove_slot(slot_id):
        console.print(f"[green]✓[/green] Slot {slot_id} 已移�?)
    else:
        console.print(f"[red]未找�?Slot {slot_id}[/red]")


@pool_app.command("refresh")
def pool_refresh():
    """刷新 Token 池中所有过期的 Copilot Token�?""
    import asyncio
    from solopreneur.providers.github_copilot import GitHubCopilotProvider
    
    async def do_refresh():
        copilot = GitHubCopilotProvider()
        await copilot._refresh_expired_slots()
        
        status = copilot.pool.get_status()
        for s in status:
            state_color = {"active": "green", "cooling": "yellow", "expired": "yellow", "dead": "red"}.get(s["state"], "white")
            console.print(f"  Slot {s['slot_id']} ({s['label']}): [{state_color}]{s['state']}[/{state_color}]")
        
        await copilot.close()
    
    console.print(f"{__logo__} 正在刷新 Token...")
    asyncio.run(do_refresh())
    console.print("[green]✓[/green] 刷新完成")


# ============================================================================
# 状态命�?
# ============================================================================


@app.command()
def status():
    """显示 nanobot 状态�?""
    from solopreneur.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} nanobot 状态\n")

    console.print(f"配置：{config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"工作区：{workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        console.print(f"模型：{config.agents.defaults.model}")
        
        # 检�?API 密钥
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_gemini = bool(config.providers.gemini.api_key)
        has_vllm = bool(config.providers.vllm.api_base)
        
        console.print(f"OpenRouter API: {'[green]✓[/green]' if has_openrouter else '[dim]未设置[/dim]'}")
        console.print(f"Anthropic API: {'[green]✓[/green]' if has_anthropic else '[dim]未设置[/dim]'}")
        console.print(f"OpenAI API: {'[green]✓[/green]' if has_openai else '[dim]未设置[/dim]'}")
        console.print(f"Gemini API: {'[green]✓[/green]' if has_gemini else '[dim]未设置[/dim]'}")
        vllm_status = f"[green]�?{config.providers.vllm.api_base}[/green]" if has_vllm else "[dim]未设置[/dim]"
        console.print(f"vLLM/本地: {vllm_status}")


if __name__ == "__main__":
    app()
