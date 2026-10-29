"""NumberShield Command-Line Interface.
Built with Typer and Rich to provide complete terminal capability
for telephony normalization, search dorking, exposure audits, and remediation.
"""

import sys
import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from backend.app.core.config import settings
from backend.app.core.database import init_db, purge_all_data, get_db_connection
from backend.app.engines.discovery import parse_and_normalize
from backend.app.engines.discovery.providers import (
    generate_manual_dorks,
    SearXNGProvider,
    DuckDuckGoProvider,
)
from backend.app.engines.remediation import (
    get_all_sources,
    generate_ccpa_opt_out,
    generate_gdpr_erasure,
    generate_tcpa_ftc_complaint,
    generate_trai_1909_complaint,
    generate_merchant_unsubscribe,
    get_all_dnd_guides,
)
from backend.app.engines.prevention import (
    record_spam_incident,
    list_spam_incidents,
    analyze_spam_campaigns,
    verify_exposure_url,
    calculate_metrics,
)

app = typer.Typer(
    name="numbershield",
    help="NumberShield — A Free, Open-Source Phone-Number Privacy & Spam Reduction Platform",
    add_completion=False,
)
console = Console()


@app.callback()
def main_callback():
    """Ensure local SQLite database is initialized."""
    init_db(settings.db_path)


@app.command()
def parse(phone_number: str, region: str = typer.Option("US", help="Default 2-letter ISO country code")):
    """Parses and normalizes a phone number into international, national, and masked formats."""
    norm = parse_and_normalize(phone_number, region)
    
    table = Table(title=f"Telephony Normalization — {norm.masked_display}", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    table.add_row("Valid Number", "[green]Yes[/green]" if norm.is_valid else "[red]No[/red]")
    table.add_row("Possible Number", "[green]Yes[/green]" if norm.is_possible else "[red]No[/red]")
    table.add_row("E.164 Format", norm.e164)
    table.add_row("National Format", norm.national)
    table.add_row("International Format", norm.international)
    table.add_row("Digits Only", norm.digits_only)
    table.add_row("Dashed Format", norm.dashed)
    table.add_row("RFC 3966 URI", norm.rfc3966)
    table.add_row("Country Code", f"+{norm.country_code} ({norm.region_code})")
    table.add_row("Location", norm.location_desc or "N/A")
    table.add_row("Carrier Allocation", norm.carrier_name or "N/A")
    table.add_row("Line Type", norm.line_type)
    table.add_row("Keyed HMAC ID", norm.hmac_id[:16] + "...")

    console.print(table)


@app.command()
def dorks(phone_number: str, region: str = typer.Option("US", help="Default 2-letter ISO country code")):
    """Generates 1-click browser search URLs across Google, Bing, Brave, GitHub, Pastebin, and people directories."""
    norm = parse_and_normalize(phone_number, region)
    if not norm.is_possible:
        console.print("[red]Error: Invalid or impossible phone number.[/red]")
        raise typer.Exit(1)

    manual_dorks = generate_manual_dorks(norm)
    table = Table(title=f"Direct Search Dorks ({norm.masked_display})", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Engine / Target", style="bold")
    table.add_column("Purpose", style="dim")
    table.add_column("Search Link (Click to Open)")

    for d in manual_dorks:
        table.add_row(d.category, d.engine_name, d.purpose, f"[link={d.search_url}]{d.search_url[:50]}...[/link]")

    console.print(table)


@app.command()
def sources():
    """Lists all 25+ data brokers, search engines, and regulators in the Remediation Registry."""
    all_sources = get_all_sources()
    table = Table(title="Remediation Registry Sources", show_header=True, header_style="bold green")
    table.add_column("Source ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Turnaround", style="yellow")
    table.add_column("Official Removal URL")

    for s in all_sources:
        table.add_row(s.source_id, s.name, s.category, s.processing_time_estimate, s.official_removal_url)

    console.print(table)


@app.command()
def template(
    template_type: str = typer.Argument(..., help="CCPA, GDPR, TCPA, TRAI, or MERCHANT"),
    phone_number: str = typer.Argument(..., help="Your telephone number"),
    region: str = typer.Option("US", help="Default ISO country code"),
    recipient: str = typer.Option("Privacy Officer", help="Recipient company or officer name"),
    target_url: str = typer.Option("", help="Specific exposure URL to cite"),
):
    """Generates a formal, customized CCPA, GDPR, TCPA, TRAI, or Merchant privacy notice."""
    norm = parse_and_normalize(phone_number, region)
    t = template_type.upper()

    if "CCPA" in t:
        tpl = generate_ccpa_opt_out(norm, recipient, target_url)
    elif "GDPR" in t:
        tpl = generate_gdpr_erasure(norm, recipient, target_url)
    elif "TRAI" in t:
        tpl = generate_trai_1909_complaint(norm, "9876543210", "24/10/26", "14:30")
    elif "TCPA" in t:
        tpl = generate_tcpa_ftc_complaint(norm, "1-800-555-0199", "2026-10-24", "Robocall")
    else:
        tpl = generate_merchant_unsubscribe(norm, recipient)

    console.print(Panel(tpl.body_markdown, title=f"[bold cyan]{tpl.title}[/bold cyan]", subtitle=tpl.subject_line))


@app.command()
def dnd():
    """Displays national Do Not Call guides and carrier spam forwarding codes (7726)."""
    guides = get_all_dnd_guides()
    for g in guides:
        content = (
            f"[bold]Registry:[/bold] {g.registry_name} ({g.official_website})\n"
            f"[bold]Statutory Scrubbing Window:[/bold] {g.statutory_window}\n"
            f"[bold]Carrier Forwarding Code:[/bold] {g.carrier_spam_forwarding_code}\n"
            f"[bold]Forwarding Instructions:[/bold] {g.carrier_forwarding_instructions}\n"
            f"[bold]Legal Basis:[/bold] {g.legal_basis}"
        )
        console.print(Panel(content, title=f"[bold green]{g.country_name} ({g.country_code})[/bold green]"))


@app.command()
def verify(
    url: str = typer.Argument(..., help="Exposure URL to verify"),
    phone_number: str = typer.Argument(..., help="Phone number to check for"),
    exposure_id: str = typer.Option("manual-check", help="Exposure record ID"),
    region: str = typer.Option("US", help="Default country code"),
):
    """Safely rescans a webpage URL to verify if the phone number has been removed or remains exposed."""
    norm = parse_and_normalize(phone_number, region)
    console.print(f"[dim]Performing safe SSRF-validated HTTP fetch for: {url}[/dim]")
    
    outcome = asyncio.run(verify_exposure_url(exposure_id, url, norm, update_database=False))
    
    color = "green" if outcome.status == "CONFIRMED_REMOVED" else ("yellow" if outcome.status == "UNABLE_TO_VERIFY" else "red")
    console.print(Panel(
        f"[bold]Status:[/bold] [{color}]{outcome.status}[/{color}]\n"
        f"[bold]HTTP Status Code:[/bold] {outcome.http_status_code or 'N/A'}\n"
        f"[bold]Notes:[/bold] {outcome.evidence_notes}\n"
        f"[bold]Timestamp:[/bold] {outcome.verified_at}",
        title="Verification Rescan Result"
    ))


@app.command()
def demo():
    """Loads a realistic synthetic scenario into the local database for demonstration and testing."""
    from backend.app.api.routes import load_synthetic_scenario_endpoint
    res = load_synthetic_scenario_endpoint()
    console.print(Panel(
        f"[green]{res['message']}[/green]\n"
        f"Synthetic Number: [bold]{res['synthetic_phone']}[/bold]\n"
        f"Masked Representation: {res['masked_phone']}\n"
        f"HMAC Token: {res['identity_hmac']}",
        title="Synthetic Scenario Loaded"
    ))


@app.command()
def purge(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation (requires --code PURGE)"),
    code: str = typer.Option("", "--code", help="Confirmation code (must be 'PURGE')"),
):
    """Safely purges all local databases, exposure records, and HMAC keys."""
    from backend.app.core.database import get_purge_impact
    impact = get_purge_impact()
    console.print(f"[bold yellow]Purge Target Database:[/bold yellow] {impact['database_path']}")
    console.print(f"[bold yellow]Total Stored Records:[/bold yellow] {impact['total_records']}")
    if impact.get("is_default_database"):
        console.print("[bold red]WARNING: This will delete your primary local ClearNum database.[/bold red]")

    confirmation = code
    if not yes:
        confirmation = typer.prompt("To permanently delete all records, type PURGE")

    res = purge_all_data(confirmed=True, confirmation_code=confirmation)
    if res["success"]:
        console.print(f"[bold green]{res['message']}[/bold green]")
    else:
        console.print(f"[bold red]Purge aborted: {res['message']}[/bold red]")


@app.command()
def serve(
    host: str = typer.Option(settings.host, help="Bind interface"),
    port: int = typer.Option(settings.port, help="Port to listen on"),
):
    """Starts the NumberShield local API and web server."""
    import uvicorn
    console.print(f"[bold cyan]Starting NumberShield on http://{host}:{port}[/bold cyan]")
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)


@app.command()
def benchmark():
    """Runs the deterministic ground-truth evaluation harness across synthetic test fixtures."""
    from backend.app.engines.discovery.benchmark import run_benchmark, print_benchmark_report
    metrics = run_benchmark()
    print_benchmark_report(metrics, console)


if __name__ == "__main__":
    app()
