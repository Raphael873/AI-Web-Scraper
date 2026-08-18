# 🏋️ AI Web Scraper de Leads Fitness (Brasil)

Ferramenta gratuita e automatizada para prospecção em massa de leads B2B no nicho de **Academias, Studios de Pilates, Boxes de CrossFit, Studios de Treinamento Funcional e Personal Trainers**.

O sistema raspa o Google Maps, enriquece as informações acessando os sites dos estabelecimentos (extraindo e-mails, WhatsApp direto e Instagram), qualifica os leads com IA e gera mensagens de abordagem personalizadas, exportando tudo diretamente para **Excel (.xlsx)** e **JSON**.

---

## 🚀 Como Executar

### 1. Execução Rápida no Windows (Recomendado):
Basta dar dois cliques no arquivo:
```
run.bat
```

Você verá o menu interativo:
```text
======================================================================
               🏋️  AI FITNESS LEAD SCRAPER (BRASIL)  🏋️               
      Prospeccao Inteligente de Academias, Studios & Pilates          
======================================================================

Escolha o modo de operação:
  [1] 🚀 Piloto Automático Rápido (100 Leads Brasil)  - [1 Clique]
  [2] 🔥 Piloto Automático Turbo  (500 Leads Brasil)  - [1 Clique]
  [3] ⚡ Piloto Automático Mega   (1000 Leads Brasil) - [1 Clique]
  [4] 🎯 Prospecção Personalizada (Escolher nicho e cidade específica)
```

### 2. Ou via Linha de Comando:

**Modo Piloto Automático (Ex: 500 leads de uma vez):**
```bash
python main.py -a 500
```

**Modo Personalizado (Nicho e localidade específicos):**
```bash
python main.py --query "Studio de Pilates" --location "Moema, São Paulo SP" --max 30
```

---

## 🧠 Configuração de IA (Groq, Gemini, OpenAI)

Por padrão, a ferramenta funciona **100% gratuita** sem necessidade de nenhuma chave, usando o motor inteligente de regras e templates.

### Como usar a Groq (IA Gratuita e Ultra Rápida):
1. Crie sua conta gratuita em: [https://console.groq.com/keys](https://console.groq.com/keys)
2. Crie uma chave de API (Leva menos de 1 minuto).
3. Crie um arquivo `.env` na raiz do projeto (ou renomeie o `.env.example`) e adicione:
   ```env
   GROQ_API_KEY=gsk_sua_chave_aqui
   ```

A ferramenta também suporta:
* `GEMINI_API_KEY` (Google AI Studio - Gratuito)
* `OPENAI_API_KEY` (GPT-4o mini)
* `DEEPSEEK_API_KEY` (DeepSeek)
* `OPENROUTER_API_KEY` (OpenRouter)

---

## 📊 Estrutura dos Dados Gerados na Planilha Excel (.xlsx)

| Coluna | Descrição |
| :--- | :--- |
| **Nome do Estabelecimento** | Nome comercial oficial do espaço fitness |
| **Nicho / Categoria** | Categoria identificada (ex: Studio de Pilates, Box de CrossFit, Academia) |
| **Telefone** | Número formatado no padrão `(XX) 9XXXX-XXXX` |
| **Link WhatsApp** | Link clicável `https://wa.me/55...` pronto para abrir a conversa |
| **E-mail de Contato** | E-mail corporativo extraído do website/contato |
| **Instagram** | Link do perfil no Instagram encontrado |
| **Site Oficial** | URL do website |
| **Endereço** | Endereço completo com bairro e cidade |
| **Nota Google** | Média de estrelas (ex: 4.9) |
| **Total de Avaliações** | Volume de prova social |
| **Lead Score** | Pontuação de qualidade do lead (1/5 a 5/5) |
| **Qualificação IA** | Resumo do perfil gerado pela IA |
| **Pitch WhatsApp** | Mensagem de abordagem personalizada para copiar e enviar |
| **Link Google Maps** | Link direto para o card no Maps |

Todos os relatórios são salvos na pasta `outputs/`.
