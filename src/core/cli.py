"""Command-line interface for SA Voices"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..core.config import get_settings, LANGUAGE_METADATA
from ..tts.engine import TTSEngine, SynthesisRequest
from ..api.server import create_app
from ..ui.gradio_app import launch_ui


app = typer.Typer(
    name="sa-voices",
    help="South African Multilingual Voice Agent",
    rich_markup_mode="rich"
)
console = Console()


@app.command()
def synthesize(
    text: str = typer.Argument(..., help="Text to synthesize"),
    language: str = typer.Option("en", "--language", "-l", help="Language code"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    speed: float = typer.Option(1.0, "--speed", "-s", help="Speech speed (0.5-2.0)"),
    pitch: float = typer.Option(1.0, "--pitch", "-p", help="Voice pitch (0.5-2.0)"),
    play: bool = typer.Option(False, "--play", help="Play audio after generation"),
):
    """Synthesize speech from text"""
    settings = get_settings()
    
    # Validate language
    if language not in settings.supported_languages_list:
        console.print(f"[red]Error:[/red] Language '{language}' not supported")
        console.print(f"Supported: {', '.join(settings.supported_languages_list)}")
        raise typer.Exit(1)
    
    console.print(Panel.fit(
        f"[bold blue]SA Voices[/bold blue] - Synthesizing speech\n"
        f"Language: {LANGUAGE_METADATA[language]['name']}\n"
        f"Text: {text[:50]}{'...' if len(text) > 50 else ''}"
    ))
    
    # Initialize TTS
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Loading TTS engine...", total=None)
        
        tts_engine = TTSEngine()
        
        progress.update(task, description="Synthesizing...")
        
        request = SynthesisRequest(
            text=text,
            language=language,
            speed=speed,
            pitch=pitch
        )
        
        result = tts_engine.synthesize(request)
        
        progress.update(task, description="Saving...")
        
        # Determine output path
        if output is None:
            output = Path(f"output_{language}.wav")
        
        result.save(output)
    
    console.print(f"\n[green]✓[/green] Audio saved to: [bold]{output}[/bold]")
    console.print(f"Duration: {len(result.audio) / result.sample_rate:.2f}s")
    console.print(f"Processing time: {result.processing_time:.2f}s")
    
    # Play audio if requested
    if play:
        console.print("\n[yellow]Playing audio...[/yellow]")
        try:
            import sounddevice as sd
            sd.play(result.audio, result.sample_rate)
            sd.wait()
        except ImportError:
            console.print("[red]Install sounddevice to play audio:[/red] pip install sounddevice")


@app.command()
def languages():
    """List all supported languages"""
    settings = get_settings()
    
    table = Table(title="Supported South African Languages")
    table.add_column("Code", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Native Name", style="yellow")
    table.add_column("Speakers", style="blue")
    table.add_column("Sample", style="magenta")
    
    for code in settings.supported_languages_list:
        meta = LANGUAGE_METADATA[code]
        table.add_row(
            code,
            meta["name"],
            meta["native_name"],
            meta["speakers"],
            meta["sample_text"]
        )
    
    console.print(table)


@app.command()
def server(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Server host"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the API server"""
    import uvicorn
    
    console.print(Panel.fit(
        f"[bold blue]SA Voices API Server[/bold blue]\n"
        f"URL: http://{host}:{port}\n"
        f"Docs: http://{host}:{port}/docs"
    ))
    
    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload
    )


@app.command()
def ui(
    share: bool = typer.Option(False, "--share", help="Create public URL"),
    port: int = typer.Option(7860, "--port", "-p", help="Server port"),
):
    """Launch the web UI"""
    console.print(Panel.fit(
        "[bold blue]SA Voices Web UI[/bold blue]\n"
        f"Launching on port {port}..."
    ))
    
    launch_ui(share=share, server_port=port)


@app.command()
def demo(
    language: str = typer.Option("en", "--language", "-l", help="Language code"),
):
    """Run demo with sample texts"""
    settings = get_settings()
    
    if language not in settings.supported_languages_list:
        console.print(f"[red]Error:[/red] Language '{language}' not supported")
        raise typer.Exit(1)
    
    # Get sample text
    meta = LANGUAGE_METADATA[language]
    sample_text = meta["sample_text"]
    
    console.print(Panel.fit(
        f"[bold blue]SA Voices Demo[/bold blue]\n"
        f"Language: {meta['name']}\n"
        f"Text: {sample_text}"
    ))
    
    # Synthesize
    tts_engine = TTSEngine()
    
    request = SynthesisRequest(
        text=sample_text,
        language=language
    )
    
    with console.status("[bold green]Synthesizing..."):
        result = tts_engine.synthesize(request)
    
    output_path = Path(f"demo_{language}.wav")
    result.save(output_path)
    
    console.print(f"\n[green]✓[/green] Demo saved to: [bold]{output_path}[/bold]")
    console.print(f"[yellow]Tip:[/yellow] Play with: python -m src.core.cli play {output_path}")


@app.command()
def play(
    file: Path = typer.Argument(..., help="Audio file to play", exists=True),
):
    """Play an audio file"""
    try:
        import sounddevice as sd
        import soundfile as sf
        
        audio, sample_rate = sf.read(file)
        
        console.print(f"Playing: {file}")
        sd.play(audio, sample_rate)
        sd.wait()
        console.print("Done!")
        
    except ImportError:
        console.print("[red]Install required packages:[/red] pip install sounddevice soundfile")


@app.command()
def stats():
    """Show system statistics"""
    settings = get_settings()
    
    table = Table(title="SA Voices System Statistics")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    table.add_row("App Name", settings.APP_NAME)
    table.add_row("Version", settings.APP_VERSION)
    table.add_row("TTS Model", settings.QWEN_TTS_MODEL)
    table.add_row("Device", settings.QWEN_TTS_DEVICE)
    table.add_row("Languages", str(len(settings.supported_languages_list)))
    table.add_row("Cache Dir", settings.HUGGINGFACE_CACHE_DIR)
    
    console.print(table)


@app.callback()
def main():
    """SA Voices - South African Multilingual Voice Agent"""
    pass


if __name__ == "__main__":
    app()
