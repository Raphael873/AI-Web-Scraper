"""
Módulo de Enriquecimento de Dados
Acessa o site/links do lead para extrair e-mails, Instagram e links diretos de WhatsApp.
"""

import re
import asyncio
from typing import Dict, Optional, Set
import httpx
from bs4 import BeautifulSoup
from config import HTTP_TIMEOUT_SECONDS, USER_AGENT

# Expressões regulares para captura
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
INSTAGRAM_REGEX = re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.-]+)/?', re.IGNORECASE)
WHATSAPP_LINK_REGEX = re.compile(r'(?:https?://)?(?:api\.whatsapp\.com/send\?phone=|wa\.me/)([0-9+]+)', re.IGNORECASE)

# Ignorar extensões de imagem que possam parecer e-mails
IGNORED_EMAIL_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.css', '.js')


async def enrich_lead_website(website_url: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Visita o site do estabelecimento e extrai e-mails, links de Instagram e WhatsApp.
    """
    enriched_data = {
        "email": None,
        "instagram": None,
        "whatsapp_site": None,
    }

    if not website_url or not website_url.strip():
        return enriched_data

    url = website_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    emails_found: Set[str] = set()
    instagram_found: Optional[str] = None
    whatsapp_found: Optional[str] = None

    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            verify=False
        ) as client:
            response = await client.get(url)
            if response.status_code == 200:
                html_text = response.text
                soup = BeautifulSoup(html_text, "html.parser")

                # 1. Procurar E-mails em mailto: e texto geral
                for mailto in soup.select('a[href^="mailto:"]'):
                    href = mailto.get('href', '')
                    raw_email = href.replace('mailto:', '').split('?')[0].strip()
                    if EMAIL_REGEX.match(raw_email):
                        emails_found.add(raw_email)

                # Busca regex no texto
                for match in EMAIL_REGEX.findall(html_text):
                    clean_email = match.lower().strip()
                    if not any(clean_email.endswith(ext) for ext in IGNORED_EMAIL_EXTENSIONS):
                        emails_found.add(clean_email)

                # 2. Procurar links do Instagram
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    insta_match = INSTAGRAM_REGEX.search(href)
                    if insta_match:
                        handle = insta_match.group(1).strip()
                        # Evita páginas genéricas como 'p', 'explore', etc
                        if handle not in ('p', 'explore', 'reels', 'stories', 'accounts'):
                            instagram_found = f"https://www.instagram.com/{handle}/"
                            break

                # 3. Procurar links de WhatsApp no site
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    wa_match = WHATSAPP_LINK_REGEX.search(href)
                    if wa_match:
                        raw_wa = wa_match.group(1).replace('+', '').strip()
                        if len(raw_wa) >= 10:
                            whatsapp_found = f"https://wa.me/{raw_wa}"
                            break

    except Exception:
        # Falhas de conexão, timeout ou SSL são normais em sites locais e não devem parar o fluxo
        pass

    # Filtrar melhor e-mail (priorizar contato@, comercial@, atendimento@)
    if emails_found:
        priorities = ['contato@', 'comercial@', 'atendimento@', 'info@', 'recepcao@']
        selected_email = None
        for p in priorities:
            for em in emails_found:
                if p in em:
                    selected_email = em
                    break
            if selected_email:
                break
        enriched_data["email"] = selected_email if selected_email else list(emails_found)[0]

    enriched_data["instagram"] = instagram_found
    enriched_data["whatsapp_site"] = whatsapp_found

    return enriched_data
