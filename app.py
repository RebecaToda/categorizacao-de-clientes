from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime, date

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        port=40115,  # Porta do seu DBeaver
        user="root",
        password="",
        database="ajxfood"
    )

@app.route('/')
def index():
    busca = request.args.get('q', '').strip()
    status_filtro = request.args.get('status', '').strip()
    max_dias = request.args.get('max_dias', '').strip()
    ordem_data = request.args.get('ordem', 'desc').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Consulta unificada com tratamento de ordenação garantido para todos os clientes
    query = """
        SELECT 
            c.codigo AS codigo_cliente,
            c.nome_razao AS nome_cliente,
            c.tel_1 AS telefone,
            c.cidade,
            MAX(todas_vendas.data_venda) AS ultimo_pedido_real,
            c.data AS data_registro
        FROM clientes c
        LEFT JOIN (
            SELECT codigo_endereco AS id_cli, data AS data_venda FROM vendas_delivery WHERE codigo_endereco IS NOT NULL
            UNION ALL
            SELECT codigo_cliente AS id_cli, data_entrada AS data_venda FROM vendas_retirada WHERE codigo_cliente IS NOT NULL
        ) todas_vendas ON c.codigo = todas_vendas.id_cli
    """

    params = []
    condicoes = []

    if busca:
        if busca.isdigit():
            condicoes.append("(c.codigo = %s OR c.tel_1 LIKE %s)")
            params.extend([int(busca), f"%{busca}%"])
        else:
            condicoes.append("(c.nome_razao LIKE %s OR c.tel_1 LIKE %s)")
            params.extend([f"%{busca}%", f"%{busca}%"])

    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)

    query += " GROUP BY c.codigo, c.nome_razao, c.tel_1, c.cidade, c.data"

    # Ordenação blindada: utiliza o pedido real e, se não houver, recorre à data de registo do cliente
    if ordem_data == 'asc':
        query += " ORDER BY COALESCE(MAX(todas_vendas.data_venda), c.data) ASC, c.codigo ASC;"
    else:
        query += " ORDER BY COALESCE(MAX(todas_vendas.data_venda), c.data) DESC, c.codigo ASC;"

    cursor.execute(query, params)
    resultados = cursor.fetchall()
    
    cursor.close()
    conn.close()

    hoje = datetime.now().date()
    clientes_processados = []

    for row in resultados:
        dt_ref = row['ultimo_pedido_real'] if row['ultimo_pedido_real'] else row['data_registro']
        dias_sem_comprar = None
        
        if dt_ref:
            if isinstance(dt_ref, datetime):
                dt_ref_date = dt_ref.date()
            elif isinstance(dt_ref, date):
                dt_ref_date = dt_ref
            elif isinstance(dt_ref, str):
                try:
                    dt_ref_date = datetime.strptime(dt_ref.split()[0], '%Y-%m-%d').date()
                except:
                    dt_ref_date = None
            else:
                dt_ref_date = None

            if dt_ref_date:
                dias_sem_comprar = (hoje - dt_ref_date).days
                if dias_sem_comprar < 0:
                    dias_sem_comprar = 0
                data_formatada = dt_ref_date.strftime('%d/%m/%Y')
            else:
                data_formatada = 'Nunca comprou'
                dias_sem_comprar = 99999
        else:
            data_formatada = 'Nunca comprou'
            dias_sem_comprar = 99999

        # Regras de Classificação rigorosas:
        # - Fiel: Até 15 dias sem comprar
        # - Oscilante: Entre 16 e 45 dias
        # - Inativo: Mais de 45 dias ou sem compras reais
        if dias_sem_comprar > 45 or row['ultimo_pedido_real'] is None:
            status = 'Cliente Inativo'
        elif dias_sem_comprar >= 16:
            status = 'Cliente Oscilante'
        else:
            status = 'Cliente Fiel'

        clientes_processados.append({
            'codigo_cliente': row['codigo_cliente'],
            'nome_cliente': row['nome_cliente'],
            'telefone': row['telefone'],
            'cidade': row['cidade'] or 'Bernardino de Campos',
            'ultimo_pedido_str': data_formatada,
            'dias_num': dias_sem_comprar,
            'dias_sem_comprar': f"{dias_sem_comprar} dias" if dias_sem_comprar != 99999 else "N/A",
            'status_atividade': status
        })

    # Contadores reais para os Cards do Dashboard
    total_fiel = sum(1 for x in clientes_processados if x['status_atividade'] == 'Cliente Fiel')
    total_oscilante = sum(1 for x in clientes_processados if x['status_atividade'] == 'Cliente Oscilante')
    total_inativo = sum(1 for x in clientes_processados if x['status_atividade'] == 'Cliente Inativo')

    # Filtros visuais da interface (Slider e Botões de Status)
    clientes_filtrados = []
    for c in clientes_processados:
        if max_dias and max_dias.isdigit():
            if c['dias_num'] > int(max_dias):
                continue
        
        if status_filtro:
            if status_filtro == 'fiel' and c['status_atividade'] != 'Cliente Fiel':
                continue
            if status_filtro == 'oscilante' and c['status_atividade'] != 'Cliente Oscilante':
                continue
            if status_filtro == 'inativo' and c['status_atividade'] != 'Cliente Inativo':
                continue

        clientes_filtrados.append(c)

    return render_template('index.html', 
                           clientes=clientes_filtrados, 
                           busca=busca,
                           status_filtro=status_filtro,
                           max_dias=max_dias,
                           ordem_data=ordem_data,
                           total_fiel=total_fiel,
                           total_oscilante=total_oscilante,
                           total_inativo=total_inativo)

if __name__ == '__main__':
    app.run(debug=True)