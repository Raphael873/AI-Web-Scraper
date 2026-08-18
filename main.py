"""
AI Web Scraper - Prospector de Leads Fitness
Script Principal com Modo Piloto Automático (100 a 1000 leads) e Modo Personalizado
"""

import os
import sys
import asyncio
import argparse
import random
from typing import List, Dict, Any

# Suporte UTF-8 no Windows terminal
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import FITNESS_NICHES, BRAZIL_REGIONS, DEFAULT_MAX_RESULTS, OUTPUT_DIR
from scraper import scrape_google_maps
from enricher import enrich_lead_website
from ai_enricher import process_lead_with_ai
from exporter import export_leads


from history import lead_history


def print_banner():
    stats = lead_history.get_stats()
    banner = f"""
======================================================================
               🏋️  AI FITNESS LEAD SCRAPER (BRASIL)  🏋️               
      Prospeccao Inteligente de Academias, Studios & Pilates          
======================================================================
 📊 Memória Histórica: {stats['total_unique_leads_in_history']} leads únicos | Região Atual: {stats['current_region_cursor']}/{stats['total_configured_regions']}
======================================================================
"""
    print(banner)


async def process_single_lead_enrichment(lead: Dict[str, Any], service_desc: str = ""):
    """Enriquece 1 lead com dados web e IA."""
    website = lead.get("website")
    if website:
        enriched = await enrich_lead_website(website)
        lead["email"] = enriched.get("email")
        lead["instagram"] = enriched.get("instagram")
        lead["whatsapp_site"] = enriched.get("whatsapp_site")
    else:
        lead["email"] = None
        lead["instagram"] = None
        lead["whatsapp_site"] = None

    process_lead_with_ai(lead, service_description=service_desc)


async def run_standard_pipeline(niche: str, location: str, max_results: int, service_desc: str = ""):
    """Executa a busca para 1 nicho e 1 localidade específica."""
    query = f"{niche} em {location}".strip()
    
    print(f"\n🚀 Iniciando busca por: '{query}'")
    print(f"🎯 Meta: Coletar até {max_results} estabelecimentos inéditos\n")

    leads = await scrape_google_maps(query=query, max_results=max_results, skip_history_check=False)

    if not leads:
        print("\n❌ Nenhum estabelecimento novo foi encontrado nesta localidade (todos já foram prospectados antes).")
        return

    print(f"\n🌐 [2/3] Enriquecendo dados via Web (E-mails, Instagram e Redes)...")
    for idx, lead in enumerate(leads, start=1):
        website = lead.get("website")
        if website:
            enriched = await enrich_lead_website(website)
            lead["email"] = enriched.get("email")
            lead["instagram"] = enriched.get("instagram")
            lead["whatsapp_site"] = enriched.get("whatsapp_site")
            print(f"  🔍 [{idx}/{len(leads)}] {lead['name']}: "
                  f"Email: {lead['email'] or 'Não'} | Insta: {'Sim' if lead['instagram'] else 'Não'}")
        else:
            lead["email"] = None
            lead["instagram"] = None
            lead["whatsapp_site"] = None

    print(f"\n🧠 [3/3] Qualificando leads e gerando mensagens de abordagem (IA)...")
    for idx, lead in enumerate(leads, start=1):
        process_lead_with_ai(lead, service_description=service_desc)

    # Grava no histórico
    lead_history.add_leads_batch(leads)

    print(f"\n💾 Gerando arquivos finais...")
    exported_files = export_leads(leads, query_name=f"{niche}_{location}")

    print("\n" + "=" * 70)
    print("🎉 PROSPECÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 70)
    print(f"📊 Total de Leads Qualificados: {len(leads)}")
    print(f"📁 Planilha Excel (.xlsx): {exported_files['excel']}")
    print(f"📄 Arquivo JSON (.json):   {exported_files['json']}")
    print("=" * 70)


async def run_autopilot_pipeline(target_leads: int):
    """
    MODO PILOTO AUTOMÁTICO COM ROTAÇÃO CONTÍNUA:
    Gera 100, 200, 500 ou 1000 leads únicos no Brasil sem perguntas manuais,
    rotacionando cidades e bairros a cada execução.
    """
    rotating_regions, start_idx = lead_history.get_next_regions(count=80)

    print(f"\n🔥 [MODO PILOTO AUTOMÁTICO ATIVADO]")
    print(f"🎯 Meta: Coletar {target_leads} leads 100% INÉDITOS no Brasil.")
    print(f"📍 Rotatividade: Iniciando na região #{start_idx} de {len(BRAZIL_REGIONS)} pólos cadastrados.")
    print(f"⚡ Anti-Duplicidade: Leads já capturados anteriormente serão pulados automaticamente.\n")

    all_leads: List[Dict[str, Any]] = []
    seen_in_this_run = set()

    # Gerar combinações a partir das regiões da fatia atual
    combinations = []
    for reg in rotating_regions:
        for nic in FITNESS_NICHES[:4]:  # Academia, Pilates, CrossFit, Funcional
            combinations.append((nic, reg))

    combo_idx = 0
    while len(all_leads) < target_leads and combo_idx < len(combinations):
        niche, region = combinations[combo_idx]
        query = f"{niche} em {region}"
        combo_idx += 1

        needed = target_leads - len(all_leads)
        per_search_limit = min(max(needed, 10), 25)

        print(f"\n📍 [{len(all_leads)}/{target_leads} Leads] Varrendo: '{query}'...")
        batch = await scrape_google_maps(query=query, max_results=per_search_limit, skip_history_check=False)

        new_count = 0
        for lead in batch:
            lead_name = lead.get("name", "").strip()
            if lead_name and lead_name not in seen_in_this_run:
                seen_in_this_run.add(lead_name)
                # Enriquecimento web e IA
                await process_single_lead_enrichment(lead)
                all_leads.append(lead)
                new_count += 1
                if len(all_leads) >= target_leads:
                    break

        print(f"  ✨ +{new_count} novos leads inéditos adicionados! (Progresso total: {len(all_leads)}/{target_leads})")

        # Salva backup a cada 50 leads
        if len(all_leads) % 50 == 0 and len(all_leads) > 0:
            export_leads(all_leads, query_name=f"Piloto_Automatico_Progresso_{len(all_leads)}")

    # Grava todos os leads inéditos no histórico persistente
    if all_leads:
        lead_history.add_leads_batch(all_leads)

    print(f"\n💾 Consolidando e gerando planilha Excel final com {len(all_leads)} leads inéditos...")
    exported_files = export_leads(all_leads, query_name=f"Piloto_Automatico_{len(all_leads)}_Leads")

    print("\n" + "=" * 70)
    print(f"🎉 PILOTO AUTOMÁTICO FINALIZADO! ({len(all_leads)} LEADS INÉDITOS COLETADOS)")
    print("=" * 70)
    print(f"📁 Planilha Excel (.xlsx): {exported_files['excel']}")
    print(f"📄 Arquivo JSON (.json):   {exported_files['json']}")
    print("=" * 70)


def interactive_menu():
    print_banner()
    print("Escolha o modo de operação:")
    print("  [1] 🚀 Piloto Automático Rápido (100 Leads Brasil)  - [1 Clique]")
    print("  [2] 🔥 Piloto Automático Turbo  (500 Leads Brasil)  - [1 Clique]")
    print("  [3] ⚡ Piloto Automático Mega   (1000 Leads Brasil) - [1 Clique]")
    print("  [4] 🎯 Prospecção Personalizada (Escolher nicho e cidade específica)")

    mode = input("\n👉 Opção (1, 2, 3 ou 4) [padrão 1]: ").strip()

    if mode == "2":
        asyncio.run(run_autopilot_pipeline(target_leads=500))
    elif mode == "3":
        asyncio.run(run_autopilot_pipeline(target_leads=1000))
    elif mode == "4":
        # Modo personalizado
        print("\nEscolha o nicho:")
        for idx, n in enumerate(FITNESS_NICHES, 1):
            print(f"  [{idx}] {n}")
        print("  [0] Digitar outro nicho")
        
        c = input("\n👉 Nicho (padrão 1): ").strip()
        if c == "0":
            niche = input("Digite o nicho: ").strip()
        elif c.isdigit() and 1 <= int(c) <= len(FITNESS_NICHES):
            niche = FITNESS_NICHES[int(c) - 1]
        else:
            niche = FITNESS_NICHES[0]

        loc = input("👉 Cidade / Bairro (ex: Moema, São Paulo SP): ").strip() or "São Paulo, SP"
        max_leads = input("👉 Quantidade de leads (padrão 30): ").strip()
        max_results = int(max_leads) if max_leads.isdigit() and int(max_leads) > 0 else 30
        service = input("👉 Serviço oferecido (ou pressione Enter): ").strip()

        asyncio.run(run_standard_pipeline(niche, loc, max_results, service))
    else:
        # Padrão: 100 leads automático
        asyncio.run(run_autopilot_pipeline(target_leads=100))


def main():
    parser = argparse.ArgumentParser(description="AI Lead Scraper para Mercado Fitness no Brasil")
    parser.add_argument("-a", "--autopilot", type=int, help="Ativar modo piloto automático para N leads (ex: -a 500)")
    parser.add_argument("-q", "--query", help="Nicho ou termo de busca (ex: 'Studio de Pilates')")
    parser.add_argument("-l", "--location", help="Localização (ex: 'Moema, São Paulo - SP')")
    parser.add_argument("-m", "--max", type=int, default=DEFAULT_MAX_RESULTS, help="Quantidade de leads")
    parser.add_argument("-s", "--service", default="", help="Descrição do serviço que você vende")

    args = parser.parse_args()

    if args.autopilot:
        print_banner()
        asyncio.run(run_autopilot_pipeline(target_leads=args.autopilot))
    elif args.query and args.location:
        print_banner()
        asyncio.run(run_standard_pipeline(args.query, args.location, args.max, args.service))
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
