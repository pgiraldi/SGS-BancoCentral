# BCB Analytics - Dashboard de Séries Temporais

**🌐 Acesse o Dashboard Online: [https://pgiraldi.github.io/SGS-BancoCentral/](https://pgiraldi.github.io/SGS-BancoCentral/index.html)**

Um sistema automatizado para extração, processamento e visualização de séries temporais do Sistema Gerenciador de Séries (SGS) do Banco Central do Brasil.

O projeto transforma dados brutos da API do BCB em um dashboard estático moderno, responsivo e de alta performance.

## 🚀 Funcionalidades

- **Coleta Automatizada**: Busca dados atualizados via API do BCB (SGS).
- **Processamento de Alta Performance**: Utiliza `Polars` e `Parquet` para manipulação eficiente de dados históricos.
- **Visualização Interativa**: Gráficos dinâmicos com `Chart.js` para análise de tendências.
- **Interface Premium**: Design moderno construído com `Tailwind CSS`, incluindo suporte nativo a **Modo Escuro (Dark Mode)**.
- **Análise Detalhada**: Filtros por ano, estatísticas calculadas (acumulado no ano, 12 meses, máximo histórico) e exportação de dados para CSV.
- **Dashboard Personalizável**: Sistema de "Pin" para destacar suas séries favoritas na página inicial.

## 🛠️ Tecnologias Utilizadas

- **Linguagem**: Python 3.12+
- **Processamento de Dados**: [Polars](https://pola.rs/)
- **Templates**: [Jinja2](https://jinja.palletsprojects.com/)
- **Estilização**: [Tailwind CSS](https://tailwindcss.com/)
- **Gráficos**: [Chart.js](https://www.chartjs.org/)
- **API**: [Httpx](https://www.python-httpx.org/) & [Aiometer](https://github.com/samuelcolvin/aiometer) para requisições assíncronas.

## 📦 Estrutura do Projeto

```text
.
├── atualizar_series.py    # Script para buscar dados da API do BCB
├── gerar_site.py          # Gerador do site estático (Jinja2 + Polars)
├── series/                # Armazenamento dos dados em formato Parquet
├── templates/             # Templates HTML (index e detalhes da série)
└── site/                  # Site estático gerado (pronto para deploy)
```

## ⚙️ Como Utilizar

### 1. Instalação das Dependências

Recomendamos o uso do `uv` para gerenciamento de pacotes:

```bash
uv sync
```

Ou via `pip`:

```bash
pip install polars jinja2 httpx aiometer zeep
```

### 2. Atualizar Dados

Para baixar as últimas atualizações das séries econômicas definidas:

```bash
python atualizar_series.py
```

### 3. Gerar o Dashboard

Para reconstruir o site estático com os novos dados:

```bash
python gerar_site.py
```

### 4. Visualizar

Abra o arquivo `site/index.html` em qualquer navegador.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---
*Dados extraídos do Sistema Gerenciador de Séries Temporais do Banco Central do Brasil.*
