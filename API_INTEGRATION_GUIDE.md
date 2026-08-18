# 🚀 Guia de Integração da API: AI Web Scraper ➔ SaaS & Supabase

Este guia foi elaborado para que qualquer **desenvolvedor ou Agente de IA** conecte a API do Web Scraper (hospedada no Railway) ao seu **SaaS** e grave os leads no **Supabase**.

---

## 🏗️ 1. Arquitetura da Integração

```text
[Frontend do SaaS] ➔ Dispara busca no Railway (POST /api/v1/scraper/jobs)
                                  │
                                  ▼
[API Railway] ➔ Executa Playwright + Groq IA em segundo plano (Background Task)
                                  │
                   ┌──────────────┴──────────────┐
                   ▼                             ▼
       [Opção A: Polling]               [Opção B: Webhook]
       Frontend consulta status          API envia POST para o SaaS
       (GET /jobs/{id})                  quando a raspagem terminar
                   │                             │
                   └──────────────┬──────────────┘
                                  ▼
         [SaaS Backend] ➔ Insere os leads no Supabase (tabela 'leads')
```

---

## 🗄️ 2. Schema SQL para o Supabase

Execute este script no **SQL Editor** do seu painel do Supabase para criar as tabelas necessárias:

```sql
-- 1. Tabela para controlar as tarefas de raspagem disparadas
CREATE TABLE IF NOT EXISTS scraping_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    tenant_id VARCHAR(100),
    mode VARCHAR(20) NOT NULL DEFAULT 'standard',
    query VARCHAR(255),
    location VARCHAR(255),
    target_leads INT NOT NULL DEFAULT 30,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED', -- QUEUED, RUNNING, COMPLETED, FAILED
    progress_percent NUMERIC(5, 2) DEFAULT 0.0,
    total_leads_collected INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE
);

-- 2. Tabela principal de Leads
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id VARCHAR(50) REFERENCES scraping_jobs(job_id) ON DELETE SET NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    phone VARCHAR(50),
    whatsapp_link TEXT,
    email VARCHAR(255),
    instagram TEXT,
    website TEXT,
    address TEXT,
    rating NUMERIC(3, 1),
    reviews_count INT DEFAULT 0,
    lead_score VARCHAR(10) DEFAULT '3/5',
    ai_qualification TEXT,
    cold_pitch_whatsapp TEXT,
    maps_url TEXT,
    contact_status VARCHAR(50) DEFAULT 'NOVO', -- NOVO, CONTACTADO, EM_NEGOCIACAO, CONVERTIDO, ARQUIVADO
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Índices para consultas rápidas
CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id);
CREATE INDEX IF NOT EXISTS idx_leads_job_id ON leads(job_id);
CREATE INDEX IF NOT EXISTS idx_leads_contact_status ON leads(contact_status);
```

---

## 📡 3. Endpoints da API (Railway)

### URL Base:
```text
https://SEU_PROJETO.up.railway.app
```

---

### Endpoint 1: Iniciar Tarefa de Raspagem
* **Método:** `POST`
* **Rota:** `/api/v1/scraper/jobs`
* **Payload (JSON):**

#### Exemplo A: Busca Personalizada (Nicho e Cidade)
```json
{
  "mode": "standard",
  "query": "Studio de Pilates",
  "location": "Moema, São Paulo SP",
  "target_leads": 30,
  "service_description": "Criação de sites e gestão de tráfego pago para academias",
  "webhook_url": "https://meusaas.com/api/webhooks/leads",
  "metadata": {
    "user_id": "usr_998877",
    "tenant_id": "org_112233"
  }
}
```

#### Exemplo B: Piloto Automático em Massa (100, 500 ou 1000 leads no Brasil)
```json
{
  "mode": "autopilot",
  "target_leads": 500,
  "service_description": "Software de gestão e retenção de alunos para academias",
  "webhook_url": "https://meusaas.com/api/webhooks/leads",
  "metadata": {
    "user_id": "usr_998877"
  }
}
```

* **Resposta de Sucesso (`202 Accepted`):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "QUEUED",
  "message": "Tarefa de raspagem iniciada com sucesso em segundo plano.",
  "status_url": "/api/v1/scraper/jobs/job_a1b2c3d4e5f6",
  "results_url": "/api/v1/scraper/jobs/job_a1b2c3d4e5f6/results",
  "download_url": "/api/v1/scraper/jobs/job_a1b2c3d4e5f6/download"
}
```

---

### Endpoint 2: Consultar Status e Progresso (Polling)
* **Método:** `GET`
* **Rota:** `/api/v1/scraper/jobs/{job_id}`
* **Resposta (`200 OK`):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "RUNNING",
  "progress": {
    "collected": 18,
    "target": 30,
    "percent": 60.0,
    "current_step": "Enriquecendo lead 18/30: Euro Pilates Moema"
  },
  "created_at": "2026-08-18T14:50:00Z",
  "started_at": "2026-08-18T14:50:02Z",
  "finished_at": null,
  "error": null
}
```

---

### Endpoint 3: Obter Leads Estruturados (JSON para Salvar no Supabase)
* **Método:** `GET`
* **Rota:** `/api/v1/scraper/jobs/{job_id}/results`
* **Resposta (`200 OK`):**
```json
{
  "job_id": "job_a1b2c3d4e5f6",
  "status": "COMPLETED",
  "total_leads": 30,
  "leads": [
    {
      "name": "Euro Pilates Moema",
      "category": "Estúdio de pilates",
      "phone": "(11) 99802-6170",
      "whatsapp_link": "https://wa.me/5511998026170",
      "email": "contato@europilates.com.br",
      "instagram": "https://www.instagram.com/europilates/",
      "website": "https://www.europilates.com.br/",
      "address": "Av. Moaci, 426 - Moema, São Paulo - SP, 04083-000, Brasil",
      "rating": 5.0,
      "reviews_count": 189,
      "lead_score": "5/5",
      "ai_qualification": "Score 5/5. Telefone: Sim, Presença digital: Sim.",
      "cold_pitch_whatsapp": "Olá, equipe do Euro Pilates Moema! Tudo bem? Me chamo [Seu Nome]...",
      "maps_url": "https://www.google.com/maps/place/..."
    }
  ]
}
```

---

### Endpoint 4: Download Direto da Planilha Excel (.xlsx)
* **Método:** `GET`
* **Rota:** `/api/v1/scraper/jobs/{job_id}/download`
* **Retorno:** Arquivo binário `.xlsx` pronto para download pelo navegador.

---

## 💻 4. Exemplos de Implementação no SaaS (Next.js / TypeScript)

### A. Disparar Job via Server Action ou API Route (`actions/scraper.ts`)
```typescript
import { createClient } from '@/utils/supabase/server';

const SCRAPER_API_URL = process.env.NEXT_PUBLIC_SCRAPER_API_URL; // Ex: https://seu-scraper.up.railway.app

export async function startScraping(params: {
  query?: string;
  location?: string;
  targetLeads: number;
  mode?: 'standard' | 'autopilot';
  serviceDesc?: string;
}) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();

  // 1. Chamar a API no Railway
  const response = await fetch(`${SCRAPER_API_URL}/api/v1/scraper/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: params.mode || 'standard',
      query: params.query,
      location: params.location,
      target_leads: params.targetLeads,
      service_description: params.serviceDesc,
      webhook_url: `${process.env.NEXT_PUBLIC_SITE_URL}/api/webhooks/leads`,
      metadata: { user_id: user?.id }
    })
  });

  const jobData = await response.json();

  // 2. Registrar o Job no Supabase
  await supabase.from('scraping_jobs').insert({
    job_id: jobData.job_id,
    user_id: user?.id,
    mode: params.mode || 'standard',
    query: params.query,
    location: params.location,
    target_leads: params.targetLeads,
    status: 'QUEUED'
  });

  return jobData;
}
```

---

### B. Webhook Handler no Next.js (`app/api/webhooks/leads/route.ts`)
```typescript
import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

// Cliente Supabase com Service Role para salvar direto no banco
const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const { job_id, status, metadata, leads } = payload;
    const userId = metadata?.user_id;

    // 1. Atualizar o status do job
    await supabaseAdmin
      .from('scraping_jobs')
      .update({
        status: status,
        total_leads_collected: leads?.length || 0,
        finished_at: new Date().toISOString()
      })
      .eq('job_id', job_id);

    // 2. Inserir todos os leads no Supabase em batch
    if (leads && leads.length > 0) {
      const formattedLeads = leads.map((lead: any) => ({
        job_id: job_id,
        user_id: userId,
        name: lead.name,
        category: lead.category,
        phone: lead.phone_formatted || lead.phone,
        whatsapp_link: lead.whatsapp_link,
        email: lead.email,
        instagram: lead.instagram,
        website: lead.website,
        address: lead.address,
        rating: lead.rating ? parseFloat(String(lead.rating).replace(',', '.')) : null,
        reviews_count: lead.reviews_count || 0,
        lead_score: lead.lead_score,
        ai_qualification: lead.ai_qualification,
        cold_pitch_whatsapp: lead.cold_pitch_whatsapp,
        maps_url: lead.maps_url,
        contact_status: 'NOVO'
      }));

      await supabaseAdmin.from('leads').insert(formattedLeads);
    }

    return NextResponse.json({ success: true, count: leads?.length || 0 });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
```

---

## 🛠️ 5. Como Fazer o Deploy no Railway

1. Acesse sua conta no **[Railway.app](https://railway.app/)**.
2. Clique em **+ New Project** ➔ **Deploy from GitHub repo**.
3. Selecione o repositório **`Raphael873/AI-Web-Scraper`**.
4. No painel do serviço criado, clique em **Variables** e adicione as suas chaves:
   - `GROQ_API_KEY` (Sua chave gratuita da Groq)
   - `GEMINI_API_KEY` (Opcional - Google AI Studio)
   - `PORT=8000`
5. Vá na aba **Settings** ➔ **Networking** ➔ Clique em **Generate Domain** para gerar sua URL pública (ex: `https://ai-web-scraper-production.up.railway.app`).
6. Pronto! A sua API estará online 24/7 respondendo requisições do seu SaaS.
