from flask import Flask, render_template, request
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# Configuração da conexão com o Banco de Dados (Ajuste usuário e senha conforme seu ambiente)
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        port=40115,
        user="root",
        password="",
        database="ajxfood"
    )

@app.route('/')
def index():
    busca = request.args.get('q', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query que traz os dados e classifica com base nas suas regras de negócio
    query = """
        SELECT 
            c.codigo AS codigo_cliente,
            c.nome_razao AS nome_cliente,
            c.tel_1 AS telefone,
            MAX(v.data_entrada) AS ultimo_pedido,
            DATEDIFF(NOW(), MAX(v.data_entrada)) AS dias_desde_ultimo_pedido,
            COUNT(CASE WHEN v.data_entrada >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) AS qtd_ult_30_dias,
            CASE 
                WHEN MAX(v.data_entrada) >= DATE_SUB(NOW(), INTERVAL 15 DAY) 
                     OR COUNT(CASE WHEN v.data_entrada >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) >= 2 
                THEN 'Cliente Fiel'
                WHEN MAX(v.data_entrada) BETWEEN DATE_SUB(NOW(), INTERVAL 45 DAY) AND DATE_SUB(NOW(), INTERVAL 16 DAY) 
                THEN 'Cliente Oscilante'
                ELSE 'Cliente Inativo'
            END AS status_atividade
        FROM clientes c
        LEFT JOIN vendas_retirada v ON c.codigo = v.codigo_cliente
    """

    params = []
    if busca:
        query += " WHERE c.nome_razao LIKE %s OR c.tel_1 LIKE %s"
        params = [f"%{busca}%", f"%{busca}%"]

    query += " GROUP BY c.codigo, c.nome_razao, c.tel_1 ORDER BY ultimo_pedido DESC;"

    cursor.execute(query, params)
    clientes = cursor.fetchall()

    # Contadores para o Dashboard simples
    total_fiel = sum(1 for x in clientes if x['status_atividade'] == 'Cliente Fiel')
    total_oscilante = sum(1 for x in clientes if x['status_atividade'] == 'Cliente Oscilante')
    total_inativo = sum(1 for x in clientes if x['status_atividade'] == 'Cliente Inativo')

    cursor.close()
    conn.close()

    return render_template('index.html', 
                           clientes=clientes, 
                           busca=busca,
                           total_fiel=total_fiel,
                           total_oscilante=total_oscilante,
                           total_inativo=total_inativo)

if __name__ == '__main__':
    app.run(debug=True)