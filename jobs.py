"""
Módulo de Gerenciamento de Tarefas (Job Manager)
Controla execuções assíncronas em background, progresso em tempo real, persistência e Webhooks.
"""

import os
import re
import uuid
import asyncio
import random
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional
import httpx
from pydantic import BaseModel, Field

from config import FITNESS_NICHES, BRAZIL_REGIONS, OUTPUT_DIR
from scraper import scrape_google_maps
from enricher import enrich_lead_website
from ai_enricher import process_lead_with_ai
from exporter import export_leads, format_brazilian_phone


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobProgress(BaseModel):
    collected: int = 0
    target: int = 0
    percent: float = 0.0
    current_step: str = "Aguardando início..."


class JobModel(BaseModel):
    job_id: str
    mode: str = "standard"  # "standard" ou "autopilot"
    query: Optional[str] = None
    location: Optional[str] = None
    target_leads: int = 30
    service_description: str = ""
    webhook_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    progress: JobProgress = Field(default_factory=JobProgress)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_leads_collected: int = 0
    leads: List[Dict[str, Any]] = Field(default_factory=list)
    excel_file_path: Optional[str] = None
    json_file_path: Optional[str] = None
    error: Optional[str] = None


class JobManager:
    """Gerenciador central de tarefas assíncronas de raspagem."""

    def __init__(self):
        self.jobs: Dict[str, JobModel] = {}

    def create_job(
        self,
        mode: str = "standard",
        query: Optional[str] = None,
        location: Optional[str] = None,
        target_leads: int = 30,
        service_description: str = "",
        webhook_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JobModel:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = JobModel(
            job_id=job_id,
            mode=mode,
            query=query,
            location=location,
            target_leads=target_leads,
            service_description=service_description,
            webhook_url=webhook_url,
            metadata=metadata or {},
            progress=JobProgress(target=target_leads),
        )
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[JobModel]:
        return self.jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[JobModel]:
        all_jobs = list(self.jobs.values())
        all_jobs.reverse()
        return all_jobs[:limit]

    async def _notify_webhook(self, job: JobModel):
        """Envia os resultados para o webhook do SaaS se configurado."""
        if not job.webhook_url:
            return

        payload = {
            "event": "scraper.job.completed" if job.status == JobStatus.COMPLETED else "scraper.job.failed",
            "job_id": job.job_id,
            "status": job.status,
            "metadata": job.metadata,
            "total_leads": job.total_leads_collected,
            "leads": job.leads,
            "error": job.error,
            "finished_at": job.finished_at,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(job.webhook_url, json=payload)
        except Exception as e:
            print(f"⚠️ Erro ao enviar webhook para {job.webhook_url}: {e}")

    async def run_job(self, job_id: str):
        """Executa a raspagem em background para um dado job_id."""
        job = self.get_job(job_id)
        if not job:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow().isoformat() + "Z"
        job.progress.current_step = "Iniciando motor de busca no Google Maps..."

        all_leads: List[Dict[str, Any]] = []
        seen_names = set()

        try:
            if job.mode == "autopilot":
                # MODO PILOTO AUTOMÁTICO
                combinations = []
                for reg in BRAZIL_REGIONS:
                    for nic in FITNESS_NICHES[:4]:
                        combinations.append((nic, reg))
                random.shuffle(combinations)

                combo_idx = 0
                while len(all_leads) < job.target_leads and combo_idx < len(combinations):
                    niche, region = combinations[combo_idx]
                    current_query = f"{niche} em {region}"
                    combo_idx += 1

                    job.progress.current_step = f"Varrendo região: {region} ({niche})"
                    needed = job.target_leads - len(all_leads)
                    per_search_limit = min(max(needed, 10), 25)

                    batch = await scrape_google_maps(query=current_query, max_results=per_search_limit)

                    for lead in batch:
                        lead_name = lead.get("name", "").strip()
                        if lead_name and lead_name not in seen_names:
                            seen_names.add(lead_name)
                            
                            # Enriquecimento web
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

                            # Enriquecimento IA
                            process_lead_with_ai(lead, service_description=job.service_description)

                            # Formatar telefone para saída limpa
                            phone_info = format_brazilian_phone(lead.get("phone") or lead.get("whatsapp_site") or "")
                            lead["phone_formatted"] = phone_info["phone_formatted"]
                            lead["whatsapp_link"] = lead.get("whatsapp_site") or phone_info["whatsapp_link"]

                            all_leads.append(lead)

                            # Atualiza progresso
                            job.progress.collected = len(all_leads)
                            job.progress.percent = round((len(all_leads) / job.target_leads) * 100, 1)

                            if len(all_leads) >= job.target_leads:
                                break

            else:
                # MODO STANDARD (Busca específica)
                query_str = f"{job.query or 'Academia'} em {job.location or 'São Paulo, SP'}"
                job.progress.current_step = f"Buscando estabelecimentos para: '{query_str}'"

                raw_leads = await scrape_google_maps(query=query_str, max_results=job.target_leads)

                for idx, lead in enumerate(raw_leads, start=1):
                    job.progress.current_step = f"Enriquecendo lead {idx}/{len(raw_leads)}: {lead.get('name')}"

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

                    process_lead_with_ai(lead, service_description=job.service_description)

                    phone_info = format_brazilian_phone(lead.get("phone") or lead.get("whatsapp_site") or "")
                    lead["phone_formatted"] = phone_info["phone_formatted"]
                    lead["whatsapp_link"] = lead.get("whatsapp_site") or phone_info["whatsapp_link"]

                    all_leads.append(lead)
                    job.progress.collected = len(all_leads)
                    job.progress.percent = round((len(all_leads) / job.target_leads) * 100, 1)

            # Exportação de arquivos
            job.progress.current_step = "Gerando planilha Excel e JSON final..."
            job_slug = f"job_{job.job_id}"
            exported = export_leads(all_leads, query_name=job_slug)

            job.leads = all_leads
            job.total_leads_collected = len(all_leads)
            job.excel_file_path = str(exported["excel"])
            job.json_file_path = str(exported["json"])
            job.status = JobStatus.COMPLETED
            job.progress.percent = 100.0
            job.progress.current_step = "Concluído com sucesso!"
            job.finished_at = datetime.utcnow().isoformat() + "Z"

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.progress.current_step = f"Falha na execução: {e}"
            job.finished_at = datetime.utcnow().isoformat() + "Z"

        finally:
            await self._notify_webhook(job)


# Instância global do gerenciador de jobs
job_manager = JobManager()
