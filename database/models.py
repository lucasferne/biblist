from database.database import db
from flask_login import UserMixin

class Livro(db.Model):
    __tablename__ = "livros"

    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=True)
    titulo = db.Column(db.String(200), nullable=False)
    autor = db.Column(db.String(150), nullable=False)
    editora = db.Column(db.String(150), nullable=True)
    ano = db.Column(db.Integer, nullable=True)
    categoria = db.Column(db.String(100), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    disponiveis = db.Column(db.Integer, nullable=False, default=1)
    localizacao = db.Column(db.String(100), nullable=True)
    tipo_exemplar = db.Column(db.String(30),nullable=False,default="Original")

class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    senha = db.Column(db.String(255), nullable=False)
    admin = db.Column(db.Boolean, nullable=False, default=False)

class Aluno(db.Model):
    __tablename__ = "alunos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    matricula = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    nome = db.Column(
        db.String(150),
        nullable=False
    )

    turma = db.Column(
        db.String(50),
        nullable=False
    )

    telefone = db.Column(
        db.String(20),
        nullable=True
    )


class Emprestimo(db.Model):
    __tablename__ = "emprestimos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    livro_id = db.Column(
        db.Integer,
        db.ForeignKey("livros.id"),
        nullable=False
    )

    aluno_id = db.Column(
        db.Integer,
        db.ForeignKey("alunos.id"),
        nullable=False
    )

    data_emprestimo = db.Column(
        db.Date,
        nullable=False
    )

    data_devolucao_prevista = db.Column(
        db.Date,
        nullable=False
    )

    data_devolucao = db.Column(
        db.Date,
        nullable=True
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="emprestado"
    )

    livro = db.relationship(
        "Livro",
        backref="emprestimos"
    )

    aluno = db.relationship(
        "Aluno",
        backref="emprestimos"
    )

class Configuracao(db.Model):
    __tablename__ = "configuracao"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome_biblioteca = db.Column(
        db.String(150),
        nullable=False,
        default="Biblioteca"
    )

    cor_principal = db.Column(
        db.String(20),
        nullable=False,
        default="#2f3e46"
    )

    logo = db.Column(
        db.String(255),
        nullable=True
    )
