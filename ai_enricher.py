"""
Módulo de Inteligência Artificial Multi-Provedores (Groq, Gemini, OpenAI, DeepSeek, OpenRouter)
Com suporte a fallback para o motor de templates inteligente sem custos.
"""

import os
import re
import json
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Carregamento de chaves de API
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()


def calculate_lead_score(lead: Dict[str, Any]) -> int:
    """Calcula uma pontuação de 1 a 5 estrelas para a qualidade do lead."""
    score = 1
    if lead.get("phone") or lead.get("whatsapp_site"):
        score += 1
    if lead.get("rating") and float(str(lead["rating"]).replace(",", ".")) >= 4.5:
        score += 1
    if lead.get("reviews_count") and lead["reviews_count"] > 10:
        score += 1
    if lead.get("website") or lead.get("instagram") or lead.get("email"):
        score += 1
    return min(score, 5)


def generate_fallback_pitch(lead: Dict[str, Any]) -> str:
    """
    Gera uma mensagem de abordagem persuasiva e natural para o WhatsApp
    sem necessidade de API, baseada nas características reais do lead.
    """
    nome = lead.get("name") or "Equipe"
    categoria = (lead.get("category") or "espaço fitness").lower().strip()
    rating = lead.get("rating", "")
    reviews = lead.get("reviews_count", 0)
    tem_site = bool(lead.get("website"))
    
    # Elogio de Prova Social
    social_proof = ""
    if rating and reviews and reviews >= 10:
        social_proof = f"Vi a excelente reputação de vocês no Google ({rating} ⭐ com {reviews} avaliações) e me chamou muita atenção o trabalho do {nome}. "
    else:
        social_proof = f"Encontrei o perfil do {nome} e achei muito interessante o trabalho de vocês. "

    if not tem_site:
        pitch = (
            f"Olá! Tudo bem? Me chamo [Seu Nome].\n\n"
            f"{social_proof}"
            f"Notei que vocês ainda não possuem um site oficial integrado para captação de novos alunos pelo Google.\n\n"
            f"Trabalho ajudando negócios no segmento de {categoria} a atraírem mais alunos qualificados todos os meses através da internet. "
            f"Posso te enviar um breve vídeo de 2 minutos mostrando como estruturar isso para o {nome}?"
        )
    else:
        pitch = (
            f"Olá, equipe do {nome}! Tudo bem? Me chamo [Seu Nome].\n\n"
            f"{social_proof}"
            f"Vi que vocês já têm uma presença bacana no digital. Nós desenvolvemos soluções focadas em aumentar a conversão de novos alunos para negócios de {categoria}.\n\n"
            f"Você teria 5 minutinhos nesta semana para eu te apresentar uma ideia rápida de como podemos potencializar os resultados do {nome}?"
        )

    return pitch


def build_llm_prompt(lead: Dict[str, Any], service_description: str = "") -> str:
    """Constrói o prompt otimizado para copywriting de vendas B2B no WhatsApp."""
    return f"""
Você é um especialista em prospecção B2B (Outbound Sales) no Brasil no mercado fitness (academias, pilates, crossfit).
Analise o estabelecimento abaixo e crie uma abordagem personalizada para WhatsApp:

Dados do Estabelecimento:
- Nome: {lead.get('name')}
- Categoria: {lead.get('category')}
- Nota Google: {lead.get('rating')} ({lead.get('reviews_count')} avaliações)
- Endereço: {lead.get('address')}
- Site: {lead.get('website') or 'Não possui'}
- Instagram: {lead.get('instagram') or 'Não encontrado'}
- Serviço oferecido pelo remetente: {service_description or 'Soluções de marketing, criação de sites e tecnologia para atração e conversão de novos alunos'}

Instruções:
1. Resumo do perfil em 1 linha.
2. Crie uma mensagem para WhatsApp curta (máximo 4 parágrafos pequenos), humanizada, educada, sem parecer robótica ou spam, citando detalhes reais do estabelecimento e fazendo uma pergunta aberta.

Responda OBRIGATORIAMENTE em formato JSON válido:
{{
  "resumo": "...",
  "mensagem_whatsapp": "..."
}}
"""


def call_openai_compatible_api(endpoint: str, api_key: str, model: str, prompt: str, extra_headers: Optional[Dict] = None) -> Optional[Dict[str, str]]:
    """Chama endpoints compatíveis com a especificação OpenAI (Groq, OpenAI, DeepSeek, OpenRouter)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Você é um assistente especialista em prospecção de vendas B2B e responde sempre em JSON estrito."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "response_format": {"type": "json_object"} if "groq" in endpoint or "openai" in endpoint else None
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"].strip()
                
                # Limpar blocos markdown json
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()

                parsed = json.loads(raw_text)
                return {
                    "resumo": parsed.get("resumo", ""),
                    "mensagem_whatsapp": parsed.get("mensagem_whatsapp", "")
                }
    except Exception:
        pass
    return None


def call_gemini_api(api_key: str, prompt: str) -> Optional[Dict[str, str]]:
    """Chama a API do Google Gemini."""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        return {
            "resumo": data.get("resumo", ""),
            "mensagem_whatsapp": data.get("mensagem_whatsapp", "")
        }
    except Exception:
        pass
    return None


def process_lead_with_ai(lead: Dict[str, Any], service_description: str = "") -> Dict[str, Any]:
    """
    Processa o lead usando o melhor provedor de IA disponível:
    1. Groq (Llama 3.3 70B - Gratuito e Ultra Rápido)
    2. Google Gemini (1.5 Flash - Gratuito)
    3. OpenAI (GPT-4o mini)
    4. DeepSeek / OpenRouter
    5. Fallback para Motor de Regras Inteligentes
    """
    score = calculate_lead_score(lead)
    lead["lead_score"] = f"{score}/5"
    prompt = build_llm_prompt(lead, service_description)
    ai_result = None

    # 1. Tentar Groq (Prioridade máxima por ser gratuita e extremamente rápida)
    if GROQ_API_KEY:
        ai_result = call_openai_compatible_api(
            endpoint="https://api.groq.com/openai/v1/chat/completions",
            api_key=GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            prompt=prompt
        )

    # 2. Tentar Gemini
    if not ai_result and GEMINI_API_KEY:
        ai_result = call_gemini_api(api_key=GEMINI_API_KEY, prompt=prompt)

    # 3. Tentar OpenAI
    if not ai_result and OPENAI_API_KEY:
        ai_result = call_openai_compatible_api(
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key=OPENAI_API_KEY,
            model="gpt-4o-mini",
            prompt=prompt
        )

    # 4. Tentar DeepSeek
    if not ai_result and DEEPSEEK_API_KEY:
        ai_result = call_openai_compatible_api(
            endpoint="https://api.deepseek.com/chat/completions",
            api_key=DEEPSEEK_API_KEY,
            model="deepseek-chat",
            prompt=prompt
        )

    # 5. Tentar OpenRouter
    if not ai_result and OPENROUTER_API_KEY:
        ai_result = call_openai_compatible_api(
            endpoint="https://openrouter.ai/api/v1/chat/completions",
            api_key=OPENROUTER_API_KEY,
            model="meta-llama/llama-3.3-70b-instruct:free",
            prompt=prompt,
            extra_headers={"HTTP-Referer": "https://ai-web-scraper.local"}
        )

    # Aplicação dos resultados ou fallback inteligente
    if ai_result and ai_result.get("mensagem_whatsapp"):
        lead["ai_qualification"] = ai_result.get("resumo") or f"Score {score}/5"
        lead["cold_pitch_whatsapp"] = ai_result.get("mensagem_whatsapp")
    else:
        lead["cold_pitch_whatsapp"] = generate_fallback_pitch(lead)
        lead["ai_qualification"] = (
            f"Score {score}/5. "
            f"Telefone: {'Sim' if lead.get('phone') else 'Não'}, "
            f"Presença digital: {'Sim' if lead.get('website') or lead.get('instagram') else 'Básica'}."
        )

    return lead
