import polars as pl
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import shutil
from datetime import timedelta, date

# Configurações de Pastas
PASTA_SERIES = Path('./series')
PASTA_TEMPLATES = Path('./templates') # Usa a nova pasta de templates
PASTA_SAIDA = Path('./site')           # Saída separada para o novo modelo

def preparar_pastas():
    if PASTA_SAIDA.exists():
        shutil.rmtree(PASTA_SAIDA)
    PASTA_SAIDA.mkdir(exist_ok=True)
    (PASTA_SAIDA / 'serie').mkdir(exist_ok=True)
    
    # Nota: templates_2 não usa style.css separado (Tailwind via CDN)

def formatar(valor):
    if valor is None:
        return "-"
    try:
        # Multiplicamos por 100 para exibir como percentual nominal (ex: 4,52)
        val = float(valor) * 100
        # Formata com 4 casas e remove zeros desnecessários à direita
        s = f"{val:.4f}".replace('.', ',')
        if ',' in s:
            s = s.rstrip('0').rstrip(',')
        return s
    except:
        return "-"

def gerar_site():
    print("Iniciando geração do site estático (Modelo 2)...")
    
    if not PASTA_SERIES.exists():
        print("Aviso: A pasta 'series' não existe. Criando pasta vazia para evitar erro.")
        PASTA_SERIES.mkdir(exist_ok=True)

    env = Environment(loader=FileSystemLoader(PASTA_TEMPLATES))
    template_index = env.get_template('index.html')
    template_serie = env.get_template('serie_detalhe.html')

    preparar_pastas()

    series_info = []
    arquivos_validos = []
    
    # ID das séries que aparecerão nos cards de destaque da Home
    id_destaques = ['11', '433', '12', '432']

    # PASSO 1: Coletar metadados e calcular métricas de todas as séries
    for arquivo in PASTA_SERIES.glob('*.parquet'):
        id_serie = arquivo.stem
        try:
            df = pl.read_parquet(arquivo)
        except Exception as e:
            print(f"Erro ao ler {arquivo}: {e}")
            continue
            
        if df.is_empty():
            continue
            
        arquivos_validos.append((id_serie, df))
        
        # Identifica a coluna de valor (que não é 'data' nem 'data_final')
        col_valor = [c for c in df.columns if c not in ('data', 'data_final')][0]
        
        # Extrai nome e unidade do cabeçalho da coluna (formato: "Nome - Unidade")
        partes = col_valor.split(' - ')
        if len(partes) >= 2:
            unidade = partes[-1]
            nome_serie = ' - '.join(partes[:-1])
        else:
            nome_serie = col_valor
            unidade = ""
            
        data_inicial = df['data'].min()
        data_final = df['data'].max()
        
        # Calcula variação entre os dois últimos registros
        df_sorted = df.sort('data')
        ultimos_registros = df_sorted.tail(2).to_dicts()
        if len(ultimos_registros) >= 2:
            valor_ultimo = ultimos_registros[1][col_valor]
            valor_penultimo = ultimos_registros[0][col_valor]
            # Variação percentual sobre o valor anterior
            if float(valor_penultimo) != 0:
                variacao = (float(valor_ultimo) - float(valor_penultimo)) / abs(float(valor_penultimo)) * 100
            else:
                variacao = 0.0
        else:
            valor_ultimo = ultimos_registros[0][col_valor] if ultimos_registros else 0
            variacao = 0.0
            
        # Define ícones e cores para o novo modelo (Tailwind classes)
        if variacao > 0:
            seta = "▲"
            cor_variacao = "text-error"     # No novo modelo, vermelho indica alta (inflação/juros)
            variacao_fmt = f"+{variacao:.2f}".replace('.', ',')
        elif variacao < 0:
            seta = "▼"
            cor_variacao = "text-secondary" # Verde indica queda
            variacao_fmt = f"{variacao:.2f}".replace('.', ',')
        else:
            seta = "▬"
            cor_variacao = "text-slate-500"
            variacao_fmt = "0,00"
            
        data_ultimo = ultimos_registros[-1]['data'] if ultimos_registros else date.today()
        
        # Cálculo de estatísticas adicionais
        ano_atual = data_final.year
        df_ano = df.filter(pl.col('data').dt.year() == ano_atual)
        data_12m = data_final - timedelta(days=365)
        df_12m = df.filter(pl.col('data') > data_12m)
        
        def calc_acumulado(df_subset):
            if df_subset.is_empty(): return 0.0
            if "% a.a." in unidade: # Séries já anualizadas não são acumuladas por produto
                return None
            try:
                # Acúmulo de taxas (1+r1)*(1+r2)... - 1
                return float((df_subset[col_valor] + 1).product() - 1)
            except:
                return 0.0

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
        
        # Adiciona histórico completo para o gráfico da home (suporte ao botão MÁX)
        historico_home = []
        for row in df_sorted.to_dicts():
            historico_home.append({
                'data': row['data'].strftime('%d/%m/%y'),
                'valor': float(row[col_valor]) * 100
            })

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
            'historico_home': historico_home, # Novo campo para o gráfico
        }
        series_info.append(info)

    # Ordena as séries de destaque para a Home
    destaques_ordenados = []
    for pid in id_destaques:
        for s in series_info:
            if s['id'] == pid:
                destaques_ordenados.append(s)

    # PASSO 2: Renderizar as páginas de detalhes
    for id_serie, df in arquivos_validos:
        info_serie = next(s for s in series_info if s['id'] == id_serie)
        col_valor = [c for c in df.columns if c not in ('data', 'data_final')][0]
        
        # Agrupar por ano para o seletor da tabela
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
            
        html_serie_renderizado = template_serie.render(
            serie=info_serie, 
            dados_por_ano=dados_por_ano, 
            anos=anos, 
            series=series_info
        )
        (PASTA_SAIDA / 'serie' / f'{id_serie}.html').write_text(html_serie_renderizado, encoding='utf-8')
        print(f"✓ Página gerada: site_2/serie/{id_serie}.html")

    # Preparar resumo de todas as séries para os favoritos dinâmicos
    resumo_series = {}
    for s_info in series_info:
        resumo_series[s_info['id']] = {
            'id': s_info['id'],
            'nome': s_info['nome'],
            'unidade': s_info['unidade'],
            'stats_fmt': s_info['stats_fmt'],
            'data_legivel': s_info['data_legivel'],
            'seta': s_info['seta'],
            'variacao_fmt': s_info['variacao_fmt'],
            'historico_home': s_info['historico_home']
        }

    # Renderiza a Home
    data_hoje = date.today().strftime('%d/%m/%Y')
    html_index_renderizado = template_index.render(
        series=series_info, 
        destaques=destaques_ordenados, 
        resumo_series=resumo_series,
        data_atual=data_hoje
    )
    (PASTA_SAIDA / 'index.html').write_text(html_index_renderizado, encoding='utf-8')
    print(f"✓ Página gerada: site_2/index.html")
    print("GERAÇÃO CONCLUÍDA COM SUCESSO! Verifique a pasta 'site_2'.")

if __name__ == '__main__':
    gerar_site()
