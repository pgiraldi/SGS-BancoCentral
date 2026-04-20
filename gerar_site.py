import polars as pl
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import shutil
from datetime import timedelta, date

# Configurações de Pastas
PASTA_SERIES = Path('./series')
PASTA_TEMPLATES = Path('./templates')
PASTA_SAIDA = Path('./site')

def preparar_pastas():
    if PASTA_SAIDA.exists():
        shutil.rmtree(PASTA_SAIDA)
    PASTA_SAIDA.mkdir(exist_ok=True)
    (PASTA_SAIDA / 'serie').mkdir(exist_ok=True)
    
    # Copiar o arquivo de CSS para a raiz do site
    caminho_css = PASTA_TEMPLATES / 'style.css'
    if caminho_css.exists():
        shutil.copy(caminho_css, PASTA_SAIDA / 'style.css')

def formatar(valor):
    if valor is None:
        return "-"
    try:
        return f"{float(valor) * 100:.4f}".replace('.', ',')
    except:
        return "-"

def gerar_site():
    print("Iniciando geração do site estático...")
    
    if not PASTA_SERIES.exists():
        print("Erro: A pasta 'series' com os arquivos Parquet não foi encontrada.")
        return

    env = Environment(loader=FileSystemLoader(PASTA_TEMPLATES))
    template_index = env.get_template('index.html')
    template_serie = env.get_template('serie_detalhe.html')

    preparar_pastas()

    series_info = []
    arquivos_validos = []
    
    # Prioridade para exibir na home
    id_destaques = ['11', '433', '12']

    # PASSO 1: Coletar metadados e calcular métricas de todas as séries
    for arquivo in PASTA_SERIES.glob('*.parquet'):
        id_serie = arquivo.stem
        try:
            df = pl.read_parquet(arquivo)
        except Exception as e:
            continue
            
        if df.is_empty():
            continue
            
        arquivos_validos.append((id_serie, df))
        
        col_valor = [c for c in df.columns if c not in ('data', 'data_final')][0]
        
        partes = col_valor.split(' - ')
        if len(partes) >= 2:
            unidade = partes[-1]
            nome_serie = ' - '.join(partes[:-1])
        else:
            nome_serie = col_valor
            unidade = ""
            
        data_inicial = df['data'].min()
        data_final = df['data'].max()
        
        # Últimos registros para variação
        ultimos_registros = df.sort('data').tail(2).to_dicts()
        if len(ultimos_registros) >= 2:
            valor_ultimo = ultimos_registros[1][col_valor]
            valor_penultimo = ultimos_registros[0][col_valor]
            if float(valor_penultimo) != 0:
                variacao = (float(valor_ultimo) - float(valor_penultimo)) / abs(float(valor_penultimo)) * 100
            else:
                variacao = 0.0
        else:
            valor_ultimo = ultimos_registros[0][col_valor]
            variacao = 0.0
            
        if variacao > 0:
            seta = "▲"
            cor_variacao = "var(--text-success)"
            variacao_fmt = f"+{variacao:.2f}".replace('.', ',')
        elif variacao < 0:
            seta = "▼"
            cor_variacao = "var(--text-danger)"
            variacao_fmt = f"{variacao:.2f}".replace('.', ',')
        else:
            seta = "▬"
            cor_variacao = "var(--text-secondary)"
            variacao_fmt = "0,00"
            
        data_ultimo = ultimos_registros[-1]['data']
        
        # Filtros para estatísticas
        ano_atual = data_final.year
        df_ano = df.filter(pl.col('data').dt.year() == ano_atual)
        data_12m = data_final - timedelta(days=365)
        df_12m = df.filter(pl.col('data') > data_12m)
        
        def calc_acumulado(df_subset):
            if df_subset.is_empty(): return 0.0
            if "% a.a." in unidade:
                return None
            return float((df_subset[col_valor] + 1).product() - 1)

        stats_raw = {
            'ultimo': float(valor_ultimo),
            'maior_ano': float(df_ano[col_valor].max()) if not df_ano.is_empty() else 0,
            'menor_ano': float(df_ano[col_valor].min()) if not df_ano.is_empty() else 0,
            'maior_hist': float(df[col_valor].max()),
            'menor_hist': float(df[col_valor].min()),
            'acumulado_ano': calc_acumulado(df_ano),
            'acumulado_12m': calc_acumulado(df_12m),
        }
        stats_fmt = {k: formatar(v) for k, v in stats_raw.items()}
        
        info = {
            'id': id_serie,
            'nome': nome_serie,
            'unidade': unidade,
            'data_inicial': data_inicial.strftime('%Y-%m-%d'),
            'data_inicial_legivel': data_inicial.strftime('%d/%m/%Y'),
            'data_final': data_final.strftime('%Y-%m-%d'),
            'data_final_legivel': data_final.strftime('%d/%m/%Y'),
            'ano_atual': ano_atual,
            'stats_raw': stats_raw,
            'stats_fmt': stats_fmt,
            'seta': seta,
            'cor_variacao': cor_variacao,
            'variacao_fmt': variacao_fmt,
            'data_iso': data_ultimo.strftime('%Y-%m-%d'),
            'data_legivel': data_ultimo.strftime('%d/%m/%Y'),
        }
        series_info.append(info)

    # Ordenar os destaques
    destaques_ordenados = []
    for pid in id_destaques:
        for s in series_info:
            if s['id'] == pid:
                destaques_ordenados.append(s)

    # PASSO 2: Renderizar as páginas de detalhes
    for id_serie, df in arquivos_validos:
        info_serie = next(s for s in series_info if s['id'] == id_serie)
        col_valor = [c for c in df.columns if c not in ('data', 'data_final')][0]
        
        # Agrupar por ano para paginação
        dados_por_ano = {}
        anos = []
        for row in df.sort('data', descending=True).to_dicts():
            val = row[col_valor]
            dt = row['data']
            ano = dt.year
            if ano not in dados_por_ano:
                dados_por_ano[ano] = []
                anos.append(ano)
            dados_por_ano[ano].append({
                'data_iso': dt.strftime('%Y-%m-%d'),
                'data_legivel': dt.strftime('%d/%m/%Y'),
                'valor_puro': float(val),
                'valor_formatado': formatar(val)
            })
            
        html_serie_renderizado = template_serie.render(serie=info_serie, dados_por_ano=dados_por_ano, anos=anos, series=series_info)
        (PASTA_SAIDA / 'serie' / f'{id_serie}.html').write_text(html_serie_renderizado, encoding='utf-8')
        print(f"✓ Página gerada: site/serie/{id_serie}.html")

    # Renderiza a Home
    ano_referencia = date.today().year
    if destaques_ordenados:
        ano_referencia = destaques_ordenados[0]['ano_atual']

    html_index_renderizado = template_index.render(series=series_info, destaques=destaques_ordenados, ano_atual=ano_referencia)
    (PASTA_SAIDA / 'index.html').write_text(html_index_renderizado, encoding='utf-8')
    print(f"✓ Página gerada: site/index.html")
    print("SUCESSO!")

if __name__ == '__main__':
    gerar_site()
