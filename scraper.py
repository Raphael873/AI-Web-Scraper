"""
Motor de Raspagem do Google Maps usando Playwright
Navega, rola a lista de estabelecimentos e extrai os detalhes completos.
"""

import asyncio
import re
import sys
import urllib.parse
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import USER_AGENT, SELECTORS, HEADLESS, BROWSER_TIMEOUT_MS


async def handle_consent_dialog(page: Page):
    """Lida com banners de cookies e termos do Google se aparecerem."""
    try:
        consent_buttons = [
            "button:has-text('Aceitar tudo')",
            "button:has-text('Aceito')",
            "button:has-text('Concordo')",
            "button:has-text('Rejeitar tudo')",
            "button[aria-label*='Aceitar']",
            "form:nth-child(2) button",
        ]
        for btn_selector in consent_buttons:
            btn = page.locator(btn_selector).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await asyncio.sleep(1)
                break
    except Exception:
        pass


def clean_reviews_count(raw_text: str) -> int:
    """Extrai o número inteiro de avaliações a partir de textos como '(124)' ou '124 avaliações'."""
    if not raw_text:
        return 0
    digits = re.findall(r'\d+', raw_text.replace('.', '').replace(',', ''))
    if digits:
        return int(digits[0])
    return 0


def clean_text(raw_text: str) -> str:
    """Remove caracteres especiais de ícones do Maps e quebras de linha."""
    if not raw_text:
        return ""
    # Remove caracteres Unicode na faixa de símbolos/ícones privados e quebras de linha
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', raw_text)
    cleaned = re.sub(r'[\r\n\t]+', ' ', cleaned)
    return cleaned.strip()


async def extract_panel_details(page: Page) -> Dict[str, Any]:
    """Extrai as informações detalhadas do painel lateral aberto no Maps."""
    data = {
        "name": "",
        "rating": "",
        "reviews_count": 0,
        "category": "",
        "address": "",
        "phone": "",
        "website": "",
        "maps_url": page.url,
    }

    # 1. Nome do Estabelecimento
    try:
        title_elem = page.locator("h1.DUwDvf, div.m6QErb h1").first
        if await title_elem.is_visible(timeout=2000):
            data["name"] = clean_text(await title_elem.inner_text())
    except Exception:
        pass

    # 2. Nota e Avaliações
    try:
        rating_elem = page.locator("div.F7nice span[aria-hidden='true'], span.ceNzKf").first
        if await rating_elem.is_visible(timeout=1000):
            data["rating"] = (await rating_elem.inner_text()).strip()
            
        reviews_elem = page.locator("div.F7nice span[aria-label*='avaliações'], div.F7nice span[aria-label*='reviews'], span.HHrUfc").first
        if await reviews_elem.is_visible(timeout=1000):
            raw_rev = await reviews_elem.inner_text()
            data["reviews_count"] = clean_reviews_count(raw_rev)
    except Exception:
        pass

    # 3. Categoria / Nicho
    try:
        cat_elem = page.locator("button[jsaction*='pane.rating.category'], button.DkEaL, span.YhemCb").first
        if await cat_elem.is_visible(timeout=1000):
            data["category"] = clean_text(await cat_elem.inner_text())
    except Exception:
        pass

    # 4. Endereço
    try:
        addr_elem = page.locator("button[data-item-id='address'], button[aria-label*='Endereço:']").first
        if await addr_elem.is_visible(timeout=1000):
            data["address"] = clean_text(await addr_elem.inner_text())
    except Exception:
        pass

    # 5. Telefone
    try:
        phone_elem = page.locator("button[data-item-id*='phone:tel:'], button[aria-label*='Telefone:']").first
        if await phone_elem.is_visible(timeout=1000):
            data["phone"] = clean_text(await phone_elem.inner_text())
    except Exception:
        pass

    # 6. Website Oficial
    try:
        web_elem = page.locator("a[data-item-id='authority'], a[aria-label*='Website:']").first
        if await web_elem.is_visible(timeout=1000):
            data["website"] = await web_elem.get_attribute("href")
    except Exception:
        pass

    return data


async def scrape_google_maps(query: str, max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Executa a raspagem completa no Google Maps para uma dada consulta.
    """
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.google.com/maps/search/{encoded_query}/?hl=pt-BR"
    
    leads: List[Dict[str, Any]] = []
    seen_names = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="pt-BR",
        )
        
        page = await context.new_page()
        page.set_default_timeout(BROWSER_TIMEOUT_MS)

        print(f"\n🔍 [1/3] Acessando Google Maps: '{query}'...")
        await page.goto(search_url, wait_until="domcontentloaded")
        await handle_consent_dialog(page)
        await asyncio.sleep(2)

        # Verificar se abriu direto no detalhe de 1 estabelecimento
        if await page.locator(SELECTORS["title"]).is_visible(timeout=3000):
            # Caso seja resultado único
            feed_visible = await page.locator(SELECTORS["feed"]).is_visible(timeout=1000)
            if not feed_visible:
                lead = await extract_panel_details(page)
                if lead["name"]:
                    leads.append(lead)
                    await browser.close()
                    return leads

        # Caso seja uma lista de resultados
        feed_locator = page.locator(SELECTORS["feed"])
        try:
            await feed_locator.wait_for(state="visible", timeout=10000)
        except Exception:
            print("⚠️ Não foi possível encontrar a lista de estabelecimentos. Tentando seletores alternativos...")

        print(f"⏳ Rolando feed para carregar até {max_results} estabelecimentos...")
        
        # Rolar o feed para carregar os cards necessários
        scroll_attempts = 0
        max_scroll_attempts = max(max_results // 2, 10)
        
        while scroll_attempts < max_scroll_attempts:
            # Seleciona apenas os cards reais de estabelecimentos (div.Nv2PK)
            cards = page.locator("div[role='feed'] div.Nv2PK")
            count = await cards.count()
            
            if count >= max_results:
                break

            # Rola o feed para baixo
            try:
                await page.evaluate("""
                    const feed = document.querySelector("div[role='feed']");
                    if (feed) {
                        feed.scrollTop = feed.scrollHeight;
                    }
                """)
            except Exception:
                pass

            await asyncio.sleep(1.2)
            
            # Checar se chegou ao fim da lista
            end_of_list = await page.locator("text='Você chegou ao final da lista.'").is_visible(timeout=400)
            if end_of_list:
                break
                
            scroll_attempts += 1

        # Agora iterar sobre cada card real
        cards = page.locator("div[role='feed'] div.Nv2PK")
        total_found = await cards.count()
        target_count = min(total_found, max_results)
        
        print(f"📌 {total_found} estabelecimentos encontrados. Extraindo detalhes de {target_count} leads...")

        for i in range(target_count):
            try:
                card = cards.nth(i)
                await card.scroll_into_view_if_needed()
                
                # Extrai nome preliminar diretamente do card para segurança
                card_name = ""
                name_elem = card.locator("div.qBF1Pd, a.hfpxzc").first
                if await name_elem.is_visible(timeout=500):
                    card_name = clean_text(await name_elem.inner_text() or await name_elem.get_attribute("aria-label") or "")

                # Clica no link do estabelecimento para abrir o painel lateral completo
                link_elem = card.locator("a.hfpxzc").first
                if await link_elem.is_visible(timeout=1000):
                    await link_elem.click()
                else:
                    await card.click()

                await asyncio.sleep(1.3)

                # Extrai dados do painel lateral
                lead_data = await extract_panel_details(page)
                
                # Se o nome no painel for inválido ou for o cabeçalho 'Resultados', usa o nome do card
                if not lead_data["name"] or lead_data["name"].lower().startswith("resultado"):
                    lead_data["name"] = card_name

                # Se a categoria estiver vazia, tenta pegar da consulta ou do card
                if not lead_data["category"]:
                    lead_data["category"] = query.split(" em ")[0]

                # Evita duplicidades e nomes vazios
                if lead_data["name"] and not lead_data["name"].lower().startswith("resultado") and lead_data["name"] not in seen_names:
                    seen_names.add(lead_data["name"])
                    leads.append(lead_data)
                    print(f"  ✓ [{len(leads)}/{target_count}] {lead_data['name']} | Tel: {lead_data['phone'] or 'S/ Tel'} | ⭐ {lead_data['rating'] or 'S/ Nota'}")
                    
            except Exception as e:
                # Se falhar em um card específico, continua para o próximo
                continue

        await browser.close()

    return leads
