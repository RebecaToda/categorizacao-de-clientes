from flask import Flask, render_template, request, jsonify
import mysql.connector
import sqlite3
from datetime import datetime, date

app = Flask(__name__)

def get_mysql_connection():
    return mysql.connector.connect(
        host="localhost",
        port=40115,
        user="root",
        password="",
        database="ajxfood"
    )

def init_sqlite():
    conn = sqlite3.connect('controle_contatos.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contatos (
            codigo_cliente INTEGER PRIMARY KEY,
            ultima_mensagem TEXT,
            resposta_cliente INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_sqlite()

@app.route('/')
def index():
    busca = request.args.get('q', '').strip()
    status_filtro = request.args.get('status', '').strip()
    max_dias = request.args.get('max_dias', '').strip()
    ordem_data = request.args.get('ordem', 'desc').strip()

    conn_sql = get_mysql_connection()
    cursor_sql = conn_sql.cursor(dictionary=True)

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

    if ordem_data == 'asc':
        query += " ORDER BY COALESCE(MAX(todas_vendas.data_venda), c.data) ASC, c.codigo ASC;"
    else:
        query += " ORDER BY COALESCE(MAX(todas_vendas.data_venda), c.data) DESC, c.codigo ASC;"

    cursor_sql.execute(query, params)
    resultados = cursor_sql.fetchall()
    
    cursor_sql.close()
    conn_sql.close()

    conn_sqlite = sqlite3.connect('controle_contatos.db')
    cursor_sqlite = conn_sqlite.cursor()
    cursor_sqlite.execute("SELECT codigo_cliente, ultima_mensagem, resposta_cliente FROM contatos")
    contatos_dict = {row[0]: {'ultima_mensagem': row[1], 'resposta_cliente': row[2]} for row in cursor_sqlite.fetchall()}
    conn_sqlite.close()

    hoje = datetime.now().date()
    clientes_processados = []

    for row in resultados:
        cli_id = row['codigo_cliente']
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

        if dias_sem_comprar > 45 or row['ultimo_pedido_real'] is None:
            status = 'Cliente Inativo'
        elif dias_sem_comprar >= 16:
            status = 'Cliente Oscilante'
        else:
            status = 'Cliente Fiel'

        info_contato = contatos_dict.get(cli_id, {'ultima_mensagem': '', 'resposta_cliente': 0})

        clientes_processados.append({
            'codigo_cliente': cli_id,
            'nome_cliente': row['nome_cliente'],
            'telefone': row['telefone'],
            'cidade': row['cidade'] or 'Bernardino de Campos',
            'ultimo_pedido_str': data_formatada,
            'dias_num': dias_sem_comprar,
            'dias_sem_comprar': f"{dias_sem_comprar} dias" if dias_sem_comprar != 99999 else "N/A",
            'status_atividade': status,
            'ultima_mensagem': info_contato['ultima_mensagem'] or '',
            'resposta_cliente': True if info_contato['resposta_cliente'] == 1 else False
        })

    total_fiel = sum(1 for x in clientes_processados if x['status_atividade'] == 'Cliente Fiel')
    total_oscilante = sum(1 for x in clientes_processados if x['status_atividade'] == 'Cliente Oscilante')
    total_inativo = sum(1 for x in clientes_processados if x['status_atividade'] == 'Cliente Inativo')

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

@app.route('/atualizar-contato', methods=['POST'])
def atualizar_contato():
    data = request.get_json()
    print("DADOS RECEBIDOS:", data)
    
    codigo_cliente = data.get('codigo')
    ultima_mensagem = data.get('ultima_mensagem') or None
    resposta_cliente = 1 if data.get('resposta_cliente') else 0

    try:
        conn = sqlite3.connect('controle_contatos.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO contatos (codigo_cliente, ultima_mensagem, resposta_cliente)
            VALUES (?, ?, ?)
            ON CONFLICT(codigo_cliente) DO UPDATE SET
                ultima_mensagem = excluded.ultima_mensagem,
                resposta_cliente = excluded.resposta_cliente
        ''', (codigo_cliente, ultima_mensagem, resposta_cliente))
        conn.commit()
        conn.close()
        print("SALVO COM SUCESSO NO SQLITE LOCAL!")
        return jsonify({'sucesso': True})
    except Exception as e:
        print("ERRO AO SALVAR:", str(e))
        return jsonify({'sucesso': False}), 500

if __name__ == '__main__':
    app.run(debug=True)