import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

def _strip_accents(s: str) -> str:
    """Remove acentos de uma string de forma simples, sem dependências externas."""
    import unicodedata
    if not s:
        return s
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

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
                    # 1. Começa com o termo (Prioridade Máxima)
                    # 2. Similaridade (maior score = melhor match)
                    # 3. Tamanho do nome (menor = mais chance de ser o produto principal)
                    sql = f"""
                        SELECT ean, nome, SIMILARITY(nome_unaccent, %s) as score
                        FROM "{table_name}"
                        WHERE 
                            nome_unaccent ILIKE %s -- Garante que contém a palavra (filtro rápido)
                            OR SIMILARITY(nome_unaccent, %s) > 0.3 -- Ou é similar (pega typos)
                        ORDER BY 
                            (CASE WHEN nome_unaccent ILIKE %s THEN 1 ELSE 0 END) DESC, -- Começa com o termo?
                            score DESC, 
                            LENGTH(nome) ASC
                        LIMIT 8
                    """
                    term_ilike = f"%{query}%"
                    term_starts_with = f"{query}%"
                    cur.execute(sql, (query, term_ilike, query, term_starts_with))
                
                results = cur.fetchall()
                
                # LOG DETALHADO DO RETORNO DO BANCO
                logger.info(f"🔍 [POSTGRES] Busca por '{query}' retornou {len(results)} resultados:")
                for i, r in enumerate(results):
                    score_fmt = f"{r.get('score', 0):.2f}" if 'score' in r else "N/A"
                    logger.info(f"   {i+1}. {r.get('nome')} (EAN: {r.get('ean')}) [Score: {score_fmt}]")
                
                # Fallback: tentar novamente com query sem acentos (ex: 'pão' -> 'pao')
                if not results and len(query) >= 3:
                    query_norm = _strip_accents(query)
                    if query_norm and query_norm != query:
                        logger.info(f"🔄 Fallback sem acento: tentando '{query_norm}'")
                        if len(query_norm) < 3:
                            term = f"%{query_norm}%"
                            sql = f"""
                                SELECT ean, nome
                                FROM "{table_name}"
                                WHERE nome_unaccent ILIKE %s OR nome ILIKE %s
                                ORDER BY LENGTH(nome) ASC
                                LIMIT 10
                            """
                            cur.execute(sql, (term, term))
                        else:
                            sql = f"""
                                SELECT ean, nome, SIMILARITY(nome_unaccent, %s) as score
                                FROM "{table_name}"
                                WHERE 
                                    nome_unaccent ILIKE %s
                                    OR SIMILARITY(nome_unaccent, %s) > 0.3
                                ORDER BY 
                                    (CASE WHEN nome_unaccent ILIKE %s THEN 1 ELSE 0 END) DESC,
                                    score DESC,
                                    LENGTH(nome) ASC
                                LIMIT 8
                            """
                            term_ilike = f"%{query_norm}%"
                            term_starts_with = f"{query_norm}%"
                            cur.execute(sql, (query_norm, term_ilike, query_norm, term_starts_with))
                        results = cur.fetchall()
                        logger.info(f"🔍 [POSTGRES] Fallback por '{query_norm}' retornou {len(results)} resultados:")
                        for i, r in enumerate(results):
                            score_fmt = f"{r.get('score', 0):.2f}" if 'score' in r else "N/A"
                            logger.info(f"   {i+1}. {r.get('nome')} (EAN: {r.get('ean')}) [Score: {score_fmt}]")
                
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
