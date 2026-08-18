# Imagem oficial da Microsoft com Python e dependências do Playwright pré-instaladas
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# Definir diretório de trabalho
WORKDIR /app

# Variáveis de ambiente para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Copiar arquivo de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

# Copiar todo o código-fonte da aplicação
COPY . .

# Criar pasta de saídas se não existir
RUN mkdir -p outputs

# Expor a porta dinâmica do Railway
EXPOSE 8000

# Iniciar o servidor FastAPI com suporte à porta dinâmica do Railway
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
