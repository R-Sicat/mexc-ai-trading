"""
Rich terminal live dashboard.
"""
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from sniper.monitoring.metrics import get_summary

console = Console()


def make_dashboard(
    last_signal: dict = None,
    open_position: dict = None,
    balance: float = 0.0,
    sandbox: bool = True,
) -> Panel:
    summary = get_summary()
    mode = "[yellow]SANDBOX[/yellow]" if sandbox else "[green]LIVE[/green]"

    # Header
    header = f"XAUUSDT SNIPER BOT  |  Balance: [bold]${balance:,.2f}[/bold]  |  Mode: {mode}"

    # Signal table
    signal_table = Table(show_header=False, box=None, padding=(0, 1))
    if last_signal:
        signal_table.add_row("Direction:", f"[bold]{last_signal.get('direction', '-')}[/bold]")
        conf = last_signal.get("confidence", 0)
        color = "green" if conf >= 0.72 else "yellow"
        signal_table.add_row("Confidence:", f"[{color}]{conf:.1%}[/{color}]")
        signal_table.add_row("Technical:", f"{last_signal.get('tech_score', 0):.2f}")
        signal_table.add_row("ML:", f"{last_signal.get('ml_score', 0):.2f}")
        signal_table.add_row("Pattern:", f"{last_signal.get('pattern_score', 0):.2f}")
        signal_table.add_row("Sentiment:", f"{last_signal.get('sent_score', 0):.2f}")
        gate = "[green]PASSED[/green]" if last_signal.get("gate_passed") else f"[red]BLOCKED: {last_signal.get('gate_reason', '')}[/red]"
        signal_table.add_row("Gate:", gate)
    else:
        signal_table.add_row("Status:", "Waiting for signal...")

    # Position table
    pos_table = Table(show_header=False, box=None, padding=(0, 1))
    if open_position:
        pos_table.add_row("Direction:", f"[bold]{open_position.get('direction')}[/bold]")
        pos_table.add_row("Entry:", f"${open_position.get('entry', 0):.2f}")
        pos_table.add_row("SL:", f"${open_position.get('sl', 0):.2f}")
        pos_table.add_row("TP:", f"${open_position.get('tp', 0):.2f}")
        unrealized = open_position.get("unrealized_pnl", 0)
        color = "green" if unrealized >= 0 else "red"
        pos_table.add_row("Unrealized:", f"[{color}]${unrealized:+.2f}[/{color}]")
    else:
        pos_table.add_row("", "No open position")

    # Metrics table
    metrics_table = Table(show_header=False, box=None, padding=(0, 1))
    metrics_table.add_row("Trades:", str(summary["total_trades"]))
    wr = summary["win_rate"]
    wr_color = "green" if wr >= 0.55 else "yellow"
    metrics_table.add_row("Win Rate:", f"[{wr_color}]{wr:.1%}[/{wr_color}]")
    metrics_table.add_row("Sharpe:", f"{summary['sharpe_30']:.2f}")
    metrics_table.add_row("Max DD:", f"${summary['max_drawdown']:.2f}")
    metrics_table.add_row("Total P&L:", f"${summary['total_pnl']:+.2f}")

    layout = Layout()
    layout.split_row(
        Layout(Panel(signal_table, title="[bold]LAST SIGNAL[/bold]"), name="signal"),
        Layout(Panel(pos_table, title="[bold]POSITION[/bold]"), name="position"),
        Layout(Panel(metrics_table, title="[bold]METRICS[/bold]"), name="metrics"),
    )

    return Panel(layout, title=header, border_style="blue")


def print_signal(signal_data: dict) -> None:
    console.print(make_dashboard(last_signal=signal_data))
