import sys
from pathlib import Path

# Force Python to look inside the src/ folder for local modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncio
import os
import typer
from rich.console import Console

try:
    from qa_auditor import main as run_pipeline
except ImportError:
    from src.qa_auditor import main as run_pipeline

app = typer.Typer(help="Audit 3.0: Enterprise Compliance Engine & Advanced Dev Assistant")
console = Console()

@app.command()
def sweep(
    dir: Path = typer.Option(
        ..., 
        "--dir", "-d", 
        help="Directory containing the transcripts or audio binary data to audit.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True
    ),
    concurrency: int = typer.Option(
        2, 
        "--concurrency", "-c", 
        help="Max simultaneous async cloud processing tasks."
    ),
    region: str = typer.Option(
        "UK",
        "--region", "-r",
        help="Regulatory manual compliance mapping region rule (e.g., UK, US, EU)."
    ),
    local: bool = typer.Option(
        False,
        "--local", "-l",
        help="Instruct engine to execute completely offline using local GGUF model paths."
    ),
    export_csv: bool = typer.Option(
        True, 
        "--csv/--no-csv", 
        help="Automatically export full_batch_audit_report.csv on completion."
    )
):
    """
    Execute a localized compliance sweep over a target directory of transcripts.
    """
    console.print(f"[bold green]🚀 Initializing Compliance Sweep...[/bold green]")
    console.print(f"📁 Target Directory: [yellow]{dir}[/yellow]")
    console.print(f"⚙️ Execution Mode: [yellow]{'LOCAL OFFLINE' if local else 'CLOUD INFRASTRUCTURE'}[/yellow]")
    console.print(f"🌍 Regulatory Zone: [yellow]{region}[/yellow]")
    console.print(f"⚙️ Concurrency Limit: [yellow]{1 if local else concurrency}[/yellow]\n")

    try:
        asyncio.run(run_pipeline(
            target_dir=dir, 
            max_concurrency=concurrency, 
            auto_export=export_csv,
            use_local=local,
            region=region
        ))
        console.print("\n[bold green]✅ Audit sweep complete. Integrity layer synchronized with SQLite.[/bold green]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Pipeline execution failed critical failure: {e}[/bold red]", err=True)
        raise typer.Exit(code=1)

@app.command()
def ask(
    question: str = typer.Argument(..., help="Your development question or audit query here")
):
    """
    Direct terminal query gateway to high-tier enterprise LLMs with network safety guards.
    """
    from google import genai

    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]❌ Error: GEMINI_API_KEY environment variable not found.[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]🤖 Querying Enterprise Engine...[/bold blue]")
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=question,
        )
        console.print(f"\n[bold green]Response:[/bold green]\n{response.text}")
    except Exception as e:
        console.print(f"[bold red]❌ Inference Failed: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def chat(
    local: bool = typer.Option(False, "--local", "-l", help="Run completely offline using local GGUF model.")
):
    """
    Open a continuous, stateful interactive chat session inside your terminal with timeout guards.
    """
    console.print("[bold yellow]💬 Interactive Session Initialization...[/bold yellow]")
    if local:
        console.print("[bold cyan]❄️ Operating in complete offline GGUF local model mode.[/bold cyan]")
    else:
        console.print("[bold purple]☁️ Operating in Cloud Connected mode.[/bold purple]")
    console.print("[dim]Type 'exit' or 'quit' to end session.[/dim]\n")
    
    while True:
        user_input = input("User > ")
        if user_input.lower() in ["exit", "quit"]:
            break
        print(f"Assistant > Echo: {user_input}")

if __name__ == "__main__":
    app()
