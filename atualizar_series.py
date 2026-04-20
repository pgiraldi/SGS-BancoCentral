import asyncio
import decimal
import functools
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict, NamedTuple
from itertools import chain

import aiometer
import httpx
import polars
import zeep
from zeep.transports import AsyncTransport
from zeep import exceptions as ZeepExceptions


class Serie(TypedDict):
    id: str
    data_inicial: date
    nome: str


class ValoresSerie(Serie):
    data_final: date


class Datas(NamedTuple):
    inicial: date
    final: date




async def async_buscar_series(client: zeep.AsyncClient, valores: ValoresSerie):

    array_type = client.get_type('ns0:ArrayOfflong')
    serie = valores['id']
    data_inicial = valores['data_inicial'].strftime('%d/%m/%Y')
    data_final = valores['data_final'].strftime('%d/%m/%Y')

    if data_final == data_inicial:
        return None

    print(f'> Buscando a série: {serie} {data_inicial} - {data_final}')

    try:
        response = await client.service.getValoresSeriesVO(
            array_type([serie]),
            data_inicial,
            data_final,
        )

    except ZeepExceptions.Fault as exc:
        # a resposta em dias não úteis retorna vazio
        # caso não tenham dias úteis dentro do intervalo
        response = None

    except Exception as exc:
        print(f'= Exceção {serie} {data_inicial} - {data_final}: {exc}')
        response = None

    print(f'< Retornou a série: {serie} {data_inicial} - {data_final}')

    return response


def dividir_datas(serie: Serie, datas: list[Datas]):

    valores_series: list[ValoresSerie] = []

    max_dt = 365 * 5   # aproximadamente 5 anos

    for inicial, final in datas:

        dt = final - inicial

        div, mod = divmod(dt.days, max_dt)

        serie['data_inicial'] = inicial

        for i in range(div):

            final = serie['data_inicial'] + timedelta(max_dt - 1)

            valores_series.append(ValoresSerie(**serie, data_final=final))

            # atualizamos a data_inicial para a proxima iteracao
            serie['data_inicial'] = final + timedelta(1)

        final = serie['data_inicial'] + timedelta(mod)

        valores_series.append(ValoresSerie(**serie, data_final=final))

    return valores_series


def gerar_valores_series(serie: Serie, pasta_series: Path):

    data_inicial = serie['data_inicial']
    data_final = date.today()

    arquivo_consultar_valores = pasta_series / f'{serie["id"]}.parquet'

    datas: list[Datas] = []

    if arquivo_consultar_valores.exists():
        # Lendo apenas os metadados do Parquet (muito mais rápido)
        limites = (
            polars.scan_parquet(arquivo_consultar_valores)
            .select(
                polars.col('data').min().alias('min'),
                polars.col('data').max().alias('max')
            )
            .collect()
        )

        primeira_data_salva: date = limites.item(0, 'min')
        última_data_salva: date = limites.item(0, 'max')

        menor_data = min(data_inicial, primeira_data_salva)
        maior_data = max(data_final, última_data_salva)

        if menor_data < primeira_data_salva:
            data_inicial = menor_data
            data_final = primeira_data_salva - timedelta(1)
            datas.append(Datas(inicial=data_inicial, final=data_final))

        if maior_data > última_data_salva:
            data_inicial = última_data_salva + timedelta(1)
            data_final = maior_data
            datas.append(Datas(inicial=data_inicial, final=data_final))

    else:
        datas.append(Datas(inicial=data_inicial, final=data_final))

    return dividir_datas(serie, datas)


def criar_cliente_bc() -> zeep.AsyncClient:
    """Configura e retorna o cliente assíncrono para consumir o SOAP do Banco Central."""
    return zeep.AsyncClient(
        wsdl='https://www3.bcb.gov.br/sgspub/JSP/sgsgeral/FachadaWSSGS.wsdl',
        transport=AsyncTransport(
            client=httpx.AsyncClient(follow_redirects=True, timeout=6000),
            wsdl_client=httpx.Client(follow_redirects=True, timeout=6000),
            timeout=6000,
        ),
    )


def processar_e_salvar_resposta(resp, pasta_series: Path):
    """Transforma a resposta SOAP em Polars DataFrame e salva o arquivo."""
    wsdl_object_as_dict = zeep.helpers.serialize_object(resp, dict)
    
    if not wsdl_object_as_dict:
        return
        
    id_serie = wsdl_object_as_dict[0]['oid']
    nome_serie = wsdl_object_as_dict[0]['nomeCompleto']['_value_1']
    unidade = wsdl_object_as_dict[0]['unidadePadrao']['_value_1']

    df_novas_entradas = (
        polars.DataFrame(wsdl_object_as_dict)
        .explode('valores')
        .unnest('valores', separator='_')
        .unnest('valores_valor', separator='_')
        .select(
            polars.date(
                polars.col('valores_ano'),
                polars.col('valores_mes'),
                polars.col('valores_dia'),
            ).alias('data'),
            polars.date(
                polars.col('valores_anoFim'),
                polars.col('valores_mesFim'),
                polars.col('valores_diaFim'),
            ).alias('data_final'),
            (
                polars.col('valores_valor__value_1').cast(
                    polars.Decimal(scale=10)
                )
                / decimal.Decimal('100')
            ).alias(f'{nome_serie} - {unidade}'),
        )
    )

    if not wsdl_object_as_dict[0]['especial']:
        df_novas_entradas = df_novas_entradas.drop('data_final')

    arquivo_consultar_valores = pasta_series / f'{id_serie}.parquet'

    if arquivo_consultar_valores.exists():
        df = polars.read_parquet(arquivo_consultar_valores)

        data_max_arquivo: date = df['data'].max()
        data_min_novas_entradas: date = df_novas_entradas['data'].max()

        if data_max_arquivo != data_min_novas_entradas:
            # esse if é por conta do IPCA
            df = polars.concat([df, df_novas_entradas])
    else:
        df = df_novas_entradas

    # para séries que os valores são referentes a um mês
    # acabam aparecendo valores duplicados. Ex: IPCA (433)
    # a solução mais simples é remover as duplicadas
    df.unique().sort('data').write_parquet(arquivo_consultar_valores)

    print(f'Série {id_serie} foi atualizada com sucesso')


async def main():
    pasta_series = Path('./series')
    pasta_series.mkdir(parents=True, exist_ok=True)

    series = [
        Serie(id='11', data_inicial=date(1986, 6, 4), nome='SELIC'),
        Serie(id='12', data_inicial=date(1986, 3, 6), nome='CDI'),
        Serie(id='226', data_inicial=date(1991, 2, 1), nome='TR'),
        Serie(id='253', data_inicial=date(1995, 7, 1), nome='TBF'),
        Serie(id='432', data_inicial=date(1999, 3, 5), nome='META SELIC'),
        Serie(id='433', data_inicial=date(1980, 1, 2), nome='IPCA'),
    ]

    valores_series = list(
        chain.from_iterable(gerar_valores_series(serie, pasta_series) for serie in series)
    )

    client = criar_cliente_bc()
    buscar_series = functools.partial(async_buscar_series, client)

    try:
        async with aiometer.amap(buscar_series, valores_series) as results:
            responses = [result async for result in results if result]
    except Exception as exc:
        print('Exceção ao realizar chamadas assíncronas:', exc)
        return

    for resp in responses:
        try:
            processar_e_salvar_resposta(resp, pasta_series)
        except Exception as exc:
            # Garante que um erro no processamento de uma série não derrube as outras
            print(f'Erro ao processar e salvar resposta de uma série: {exc}')


if __name__ == '__main__':
    asyncio.run(main())