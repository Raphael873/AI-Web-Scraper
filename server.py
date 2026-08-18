"""
Servidor API REST (FastAPI) - AI Web Scraper
Microserviço pronto para deploy no Railway e integração com SaaS / Supabase.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from jobs import job_manager, JobStatus, JobModel
from history import lead_history
from config import BASE_DIR, OUTPUT_DIR, BRAZIL_REGIONS

app = FastAPI(
    title="AI Fitness Lead Scraper API",
    description=(
        "API Cloud de Prospecção Automatizada de Leads Fitness no Brasil com histórico persistente anti-duplicidade, "
        "enriquecimento via IA e geração de planilhas Excel / JSON. Pronta para integração com SaaS e Supabase."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Habilitar CORS para consumo seguro pelo seu SaaS Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Schemas de Entrada / Saída
class CreateJobRequest(BaseModel):
    mode: str = Field(
        default="standard",
        description="'standard' (nicho e cidade específicos) ou 'autopilot' (varredura automática Brasil com rotação)",
        examples=["standard"],
    )
    query: Optional[str] = Field(
        default=None,
        description="Nicho fitness desejado (ex: 'Studio de Pilates', 'Box de CrossFit', 'Academia')",
        examples=["Studio de Pilates"],
    )
    location: Optional[str] = Field(
        default=None,
        description="Cidade / Bairro (ex: 'Moema, São Paulo SP', 'Belo Horizonte MG')",
        examples=["Moema, São Paulo SP"],
    )
    target_leads: int = Field(
        default=30,
        ge=1,
        le=1000,
        description="Quantidade alvo de leads (de 1 a 1000)",
        examples=[30],
    )
    service_description: Optional[str] = Field(
        default="",
        description="Serviço que seu SaaS/usuário oferece para personalizar o pitch de abordagem da IA",
        examples=["Soluções de marketing e criação de sites para academias"],
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL do seu SaaS para receber o payload completo quando a raspagem terminar",
        examples=["https://meusaas.com/api/webhooks/leads"],
    )
    exclude_phones: Optional[List[str]] = Field(
        default_factory=list,
        description="Lista de telefones existentes no Supabase/SaaS a serem ignorados nesta busca",
        examples=[["11999998888", "31988887777"]],
    )
    exclude_names: Optional[List[str]] = Field(
        default_factory=list,
        description="Lista de nomes de academias existentes a serem ignorados",
        examples=[["Academia Smart Fit", "Bluefit"]],
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Metadados customizados do seu SaaS (ex: user_id, tenant_id, campaign_id)",
        examples=[{"user_id": "usr_123", "tenant_id": "org_456"}],
    )


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    status_url: str
    results_url: str
    download_url: str


@app.get("/", tags=["Geral"])
async def root():
    """Endpoint raiz com informações e links rápidos."""
    return {
        "service": "AI Fitness Lead Scraper API",
        "status": "online",
        "docs": "/docs",
        "endpoints": {
            "create_job": "POST /api/v1/scraper/jobs",
            "get_status": "GET /api/v1/scraper/jobs/{job_id}",
            "get_results": "GET /api/v1/scraper/jobs/{job_id}/results",
            "download_excel": "GET /api/v1/scraper/jobs/{job_id}/download",
            "health": "GET /health"
        }
    }


@app.get("/health", tags=["Geral"])
async def health_check():
    """Healthcheck para o Railway monitorar a saúde do container."""
    return {"status": "healthy", "timestamp": job_manager.list_jobs(limit=1)}


@app.post(
    "/api/v1/scraper/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Scraper Jobs"],
    summary="Iniciar nova tarefa de raspagem de leads em background",
)
async def create_scraper_job(
    req: CreateJobRequest,
    background_tasks: BackgroundTasks
):
    """
    Cria uma nova tarefa de raspagem e executa o Playwright + IA em segundo plano no Railway.
    Retorna imediatamente o `job_id` para o SaaS acompanhar o progresso.
    """
    job = job_manager.create_job(
        mode=req.mode,
        query=req.query,
        location=req.location,
        target_leads=req.target_leads,
        service_description=req.service_description or "",
        webhook_url=req.webhook_url,
        exclude_phones=req.exclude_phones,
        exclude_names=req.exclude_names,
        metadata=req.metadata,
    )

    # Dispara a execução em background
    background_tasks.add_task(job_manager.run_job, job.job_id)

    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        message="Tarefa de raspagem iniciada com sucesso em segundo plano.",
        status_url=f"/api/v1/scraper/jobs/{job.job_id}",
        results_url=f"/api/v1/scraper/jobs/{job.job_id}/results",
        download_url=f"/api/v1/scraper/jobs/{job.job_id}/download",
    )


@app.get(
    "/api/v1/scraper/history",
    tags=["Histórico & Memória"],
    summary="Consultar estatísticas da memória histórica de leads e cursor geográfico",
)
async def get_history_stats():
    """Retorna o total de leads únicos gravados, telefones únicos e o cursor atual de rotação das regiões."""
    return lead_history.get_stats()


@app.get(
    "/api/v1/scraper/jobs/{job_id}",
    response_model=JobModel,
    tags=["Scraper Jobs"],
    summary="Consultar o status e progresso em tempo real de uma tarefa",
)
async def get_job_status(job_id: str):
    """Retorna o status atual, progresso em % e etapa atual do job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return job


@app.get(
    "/api/v1/scraper/jobs/{job_id}/results",
    tags=["Scraper Jobs"],
    summary="Obter todos os leads estruturados em JSON para salvar no Supabase / Banco",
)
async def get_job_results(job_id: str):
    """Retorna a lista de leads gerados pronta para inserção no banco de dados do seu SaaS."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    if job.status == JobStatus.RUNNING or job.status == JobStatus.QUEUED:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "progress": job.progress,
            "message": "A tarefa ainda está em andamento. Consulte novamente em alguns segundos.",
            "leads": job.leads,
            "total_leads_so_far": len(job.leads),
        }

    return {
        "job_id": job.job_id,
        "status": job.status,
        "mode": job.mode,
        "metadata": job.metadata,
        "total_leads": job.total_leads_collected,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "leads": job.leads,
    }


@app.get(
    "/api/v1/scraper/jobs/{job_id}/download",
    tags=["Scraper Jobs"],
    summary="Fazer download da planilha Excel formatada (.xlsx)",
)
async def download_job_excel(job_id: str):
    """Permite ao usuário baixar o arquivo Excel .xlsx com formatação profissional."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    if not job.excel_file_path or not Path(job.excel_file_path).exists():
        raise HTTPException(
            status_code=400,
            detail="O arquivo Excel ainda não foi gerado ou o job falhou."
        )

    filename = Path(job.excel_file_path).name
    return FileResponse(
        path=job.excel_file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get(
    "/api/v1/scraper/jobs",
    tags=["Scraper Jobs"],
    summary="Listar os últimos jobs executados",
)
async def list_all_jobs(limit: int = Query(default=20, ge=1, le=100)):
    """Retorna o histórico dos últimos jobs criados."""
    return job_manager.list_jobs(limit=limit)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
