"""
AI Web Scraper - Configurações e Seletores
"""

import os
from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# User-Agent moderno para evitar bloqueios
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Seletores do Google Maps (atualizados para a versão pt-BR)
SELECTORS = {
    # Lista de resultados
    "feed": "div[role='feed']",
    "result_item": "div[role='feed'] > div > div > a[href*='/maps/place/']",
    "result_container": "div[role='feed'] > div",
    
    # Detalhes do item
    "title": "h1.DUwDvf",
    "rating": "div.F7nice span[aria-hidden='true']",
    "reviews_count": "div.F7nice span[aria-label*='avaliações'], div.F7nice span[aria-label*='reviews']",
    "category": "button[jsaction*='pane.rating.category']",
    "address_btn": "button[data-item-id='address']",
    "website_btn": "a[data-item-id='authority']",
    "phone_btn": "button[data-item-id*='phone:tel:']",
    "hours_btn": "button[data-item-id*='oh:']",
}

# Configurações de Scraping
DEFAULT_MAX_RESULTS = 30
HEADLESS = True
BROWSER_TIMEOUT_MS = 25000
HTTP_TIMEOUT_SECONDS = 7.0

# Nichos padrão sugeridos para o mercado Fitness no Brasil
FITNESS_NICHES = [
    "Academia",
    "Studio de Pilates",
    "Box de CrossFit",
    "Studio de Treinamento Funcional",
    "Academia de Lutas / Muay Thai / Jiu-Jitsu",
    "Studio de Yoga",
    "Personal Trainer Studio",
    "Centro de Ginástica e Dança"
]

# Regiões e Capitais do Brasil para o Modo Piloto Automático
BRAZIL_REGIONS = [
    # São Paulo (Capital e Bairros nobres de alta densidade)
    "Moema, São Paulo SP",
    "Pinheiros, São Paulo SP",
    "Jardins, São Paulo SP",
    "Vila Mariana, São Paulo SP",
    "Tatuapé, São Paulo SP",
    "Santana, São Paulo SP",
    "Morumbi, São Paulo SP",
    "Barra Funda, São Paulo SP",
    "Campinas SP",
    "Ribeirão Preto SP",
    "Santos SP",
    "São José dos Campos SP",
    "Sorocaba SP",
    
    # Rio de Janeiro
    "Barra da Tijuca, Rio de Janeiro RJ",
    "Copacabana, Rio de Janeiro RJ",
    "Ipanema, Rio de Janeiro RJ",
    "Tijuca, Rio de Janeiro RJ",
    "Botafogo, Rio de Janeiro RJ",
    "Niterói RJ",
    
    # Minas Gerais
    "Savassi, Belo Horizonte MG",
    "Lourdes, Belo Horizonte MG",
    "Belvedere, Belo Horizonte MG",
    "Pampulha, Belo Horizonte MG",
    "Uberlândia MG",
    
    # Sul
    "Batel, Curitiba PR",
    "Bigorrilho, Curitiba PR",
    "Moinhos de Vento, Porto Alegre RS",
    "Bela Vista, Porto Alegre RS",
    "Centro, Florianópolis SC",
    "Balneário Camboriú SC",
    "Joinville SC",
    "Londrina PR",
    
    # Centro-Oeste
    "Asa Sul, Brasília DF",
    "Asa Norte, Brasília DF",
    "Águas Claras, Brasília DF",
    "Setor Bueno, Goiânia GO",
    "Setor Marista, Goiânia GO",
    "Cuiabá MT",
    "Campo Grande MS",
    
    # Nordeste
    "Pituba, Salvador BA",
    "Barra, Salvador BA",
    "Aldeota, Fortaleza CE",
    "Meireles, Fortaleza CE",
    "Boa Viagem, Recife PE",
    "Ponta Verde, Maceió AL",
    "Natal RN",
    "João Pessoa PB"
]
