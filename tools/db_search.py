import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

def search_products_postgres(query: str) -> str:
    """
    Busca produtos no banco PostgreSQL (substituto do smart-responder).
    Retorna string formatada com EANs encontrados.
    """
    conn_str = settings.products_db_connection_string
    if not conn_str:
        return "Erro: String de conexão do banco de produtos não configurada."

    query = query.strip()
    if not query:
        return "Nenhum termo de busca informado."

    # Remove aspas para evitar injeção/erros básicos
    query = query.replace("'", "").replace('"', "")
    
    table_name = settings.postgres_products_table_name

    try:
        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # 1. Se for numérico, busca exata por EAN primeiro
                if query.isdigit():
                    sql = f"""
                        SELECT ean, nome 
                        FROM "{table_name}"
                        WHERE ean = %s
                        LIMIT 5
                    """
                    cur.execute(sql, (query,))
                    results = cur.fetchall()
                    if results:
                        return _format_results(results)

                # 2. Busca textual INTELIGENTE (Trigram Similarity)
                # O banco possui extensão pg_trgm instalada.
                # Usamos SIMILARITY() para ordenar os resultados mais relevantes.
                
                # Definir threshold baixo para pegar variações, mas filtrar lixo
                # Se a query for muito curta, usamos ILIKE para garantir performance
                
                if len(query) < 3:
                     # Busca simples para termos muito curtos (ex: "uvas")
                    term = f"%{query}%"
                    sql = f"""
                        SELECT ean, nome
                        FROM "{table_name}"
                        WHERE nome_unaccent ILIKE %s OR nome ILIKE %s
                        ORDER BY LENGTH(nome) ASC
                        LIMIT 10
                    """
                    cur.execute(sql, (term, term))
                else:
                    # Busca inteligente com Trigram
                    # Ordena por:
                    # 1. Similaridade (maior score = melhor match)
                    # 2. Tamanho do nome (menor = mais chance de ser o produto principal e não um acessório)
                    sql = f"""
                        SELECT ean, nome, SIMILARITY(nome_unaccent, %s) as score
                        FROM "{table_name}"
                        WHERE 
                            nome_unaccent ILIKE %s -- Garante que contém a palavra (filtro rápido)
                            OR SIMILARITY(nome_unaccent, %s) > 0.1 -- Ou é similar (pega typos)
                        ORDER BY 
                            score DESC, 
                            LENGTH(nome) ASC
                        LIMIT 10
                    """
                    term_ilike = f"%{query}%"
                    cur.execute(sql, (query, term_ilike, query))
                
                results = cur.fetchall()
                
                if not results:
                    return "Nenhum produto encontrado com esse termo."
                
                return _format_results(results)

    except Exception as e:
        logger.error(f"Erro na busca Postgres: {e}")
        return f"Erro ao buscar no banco de dados: {str(e)}"

def _format_results(results: list[dict]) -> str:
    """Formata lista de dicts para o formato esperado pelo agente"""
    lines = ["EANS_ENCONTRADOS:"]
    for i, row in enumerate(results, 1):
        ean = row.get("ean", "").strip()
        nome = row.get("nome", "").strip()
        if ean and nome:
            lines.append(f"{i}) {ean} - {nome}")
    
    return "\n".join(lines)
