# 🚀 Guia de Integração da API: AI Web Scraper ➔ SaaS & Supabase

Este guia foi elaborado para que qualquer **desenvolvedor ou Agente de IA** conecte a API do Web Scraper (hospedada no Railway) ao seu **SaaS**, crie a interface visual e grave os leads no **Supabase**.

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

## 📐 3. Tipos TypeScript (`types/scraper.ts`)

Copie e cole estes tipos no seu projeto SaaS:

```typescript
export type JobStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface ScraperJobRequest {
  mode: 'standard' | 'autopilot';
  query?: string;
  location?: string;
  target_leads: number;
  service_description?: string;
  webhook_url?: string;
  exclude_phones?: string[];
  exclude_names?: string[];
  metadata?: Record<string, any>;
}

export interface ScraperJobProgress {
  collected: number;
  target: number;
  percent: number;
  current_step: string;
}

export interface Lead {
  name: string;
  category: string;
  phone: string;
  phone_formatted: string;
  whatsapp_link: string;
  email: string | null;
  instagram: string | null;
  website: string | null;
  address: string;
  rating: string | number;
  reviews_count: number;
  lead_score: string; // Ex: "5/5"
  ai_qualification: string;
  cold_pitch_whatsapp: string;
  maps_url: string;
}

export interface ScraperJobResponse {
  job_id: string;
  status: JobStatus;
  message: string;
  status_url: string;
  results_url: string;
  download_url: string;
}

export interface ScraperJobDetails {
  job_id: string;
  status: JobStatus;
  mode: string;
  progress: ScraperJobProgress;
  total_leads_collected: number;
  leads: Lead[];
  created_at: string;
  started_at?: string;
  finished_at?: string;
  error?: string | null;
}
```

---

## 📡 4. Endpoints da API (Railway)

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
  "exclude_phones": ["11999998888", "31988887777"],
  "metadata": {
    "user_id": "usr_998877",
    "tenant_id": "org_112233"
  }
}
```

#### Exemplo B: Piloto Automático em Massa com Rotação Contínua (100, 500 ou 1000 leads no Brasil)
```json
{
  "mode": "autopilot",
  "target_leads": 500,
  "service_description": "Software de gestão e retenção de alunos para academias",
  "webhook_url": "https://meusaas.com/api/webhooks/leads",
  "exclude_phones": ["11999998888"],
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

### Endpoint 2: Consultar Status e Progresso (Polling em Tempo Real)
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
      "phone_formatted": "(11) 99802-6170",
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

### Endpoint 5: Consultar Estatísticas de Memória e Histórico
* **Método:** `GET`
* **Rota:** `/api/v1/scraper/history`
* **Resposta (`200 OK`):**
```json
{
  "total_unique_leads_in_history": 1045,
  "total_unique_phones": 750,
  "current_region_cursor": 40,
  "total_configured_regions": 251,
  "last_updated": "2026-08-18T18:24:00Z"
}
```

---

## 💻 5. Exemplos de Implementação no SaaS (Next.js / TypeScript)

### A. Disparar Job via Server Action ou API Route (`actions/scraper.ts`)
```typescript
import { createClient } from '@/utils/supabase/server';
import { ScraperJobRequest, ScraperJobResponse } from '@/types/scraper';

const SCRAPER_API_URL = process.env.NEXT_PUBLIC_SCRAPER_API_URL; // Ex: https://seu-scraper.up.railway.app

export async function startScraping(params: {
  query?: string;
  location?: string;
  targetLeads: number;
  mode?: 'standard' | 'autopilot';
  serviceDesc?: string;
}): Promise<ScraperJobResponse> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();

  // 1. Buscar telefones já existentes no banco para não repetir
  const { data: existingLeads } = await supabase
    .from('leads')
    .select('phone')
    .eq('user_id', user?.id)
    .not('phone', 'is', null);

  const excludePhones = existingLeads ? existingLeads.map((l: { phone: string }) => l.phone) : [];

  // 2. Chamar a API no Railway
  const bodyPayload: ScraperJobRequest = {
    mode: params.mode || 'standard',
    query: params.query,
    location: params.location,
    target_leads: params.targetLeads,
    service_description: params.serviceDesc,
    webhook_url: `${process.env.NEXT_PUBLIC_SITE_URL}/api/webhooks/leads`,
    exclude_phones: excludePhones,
    metadata: { user_id: user?.id }
  };

  const response = await fetch(`${SCRAPER_API_URL}/api/v1/scraper/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bodyPayload)
  });

  const jobData = await response.json();

  // 3. Registrar o Job no Supabase
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

### C. Hook React para Acompanhar Progresso no Frontend (`hooks/useScraperJob.ts`)
```typescript
import { useState, useEffect } from 'react';
import { ScraperJobDetails } from '@/types/scraper';

const SCRAPER_API_URL = process.env.NEXT_PUBLIC_SCRAPER_API_URL;

export function useScraperJob(jobId: string | null) {
  const [job, setJob] = useState<ScraperJobDetails | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    setIsPolling(true);
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${SCRAPER_API_URL}/api/v1/scraper/jobs/${jobId}`);
        const data: ScraperJobDetails = await res.json();
        setJob(data);

        if (data.status === 'COMPLETED' || data.status === 'FAILED' || data.status === 'CANCELLED') {
          clearInterval(interval);
          setIsPolling(false);
        }
      } catch (err) {
        console.error('Erro ao consultar job:', err);
      }
    }, 2000); // Consulta a cada 2 segundos

    return () => clearInterval(interval);
  }, [jobId]);

  return { job, isPolling };
}
```

---

## 🤖 6. Prompt Pronto para Você Passar para o Agente do seu SaaS

Se você estiver usando outro Agente de IA para programar o SaaS, basta copiar e colar a mensagem abaixo:

```text
Olá! Preciso que você integre o nosso SaaS ao Microserviço de Prospecção de Leads que já está hospedado no Railway.
Por favor, leia atentamente o documento 'API_INTEGRATION_GUIDE.md' e implemente:

1. As tabelas no Supabase (conforme o Schema SQL do item 2).
2. A tela de Prospecção no Frontend (com opção de escolher Nicho/Cidade ou modo Piloto Automático de 100/500/1000 leads).
3. A barra de progresso em tempo real que consome o status do job.
4. O Webhook Handler em Next.js para salvar os leads na tabela 'leads' do Supabase quando a busca terminar.
5. A tabela visual de Leads com filtros por Score, botão para abrir WhatsApp direto e botão para baixar o Excel.

A URL base da nossa API no Railway é: [SUA_URL_DO_RAILWAY_AQUI]
```
