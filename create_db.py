from app import app, db

# Cria as tabelas do banco de dados
with app.app_context():
    db.create_all()
    print("Banco de dados e tabelas criadas com sucesso!")