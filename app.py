import threading
import webview
import os
import uuid

from werkzeug.utils import secure_filename

from functools import wraps
from datetime import date, datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    abort,
    flash,
    url_for
)

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database.database import db
from database.models import (
    Livro,
    Usuario,
    Aluno,
    Emprestimo,
    Configuracao
)


# ============================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ============================================================

app = Flask(__name__)

app.secret_key = "chave-secreta-biblioteca"


# ============================================================
# LOGIN
# ============================================================

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"

login_manager.login_message = (
    "Faça login para acessar esta página."
)

login_manager.login_message_category = "error"


@login_manager.user_loader
def carregar_usuario(usuario_id):

    return db.session.get(
        Usuario,
        int(usuario_id)
    )


# ============================================================
# PERMISSÃO DE ADMINISTRADOR
# ============================================================

def admin_required(f):

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):

        if not current_user.admin:

            abort(403)

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# BANCO DE DADOS
# ============================================================

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///biblioteca.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

@app.context_processor
def injetar_configuracao():

    configuracao = Configuracao.query.first()

    if not configuracao:
        configuracao = Configuracao(
            nome_biblioteca="Biblioteca",
            cor_principal="#2f3e46"
        )

        db.session.add(configuracao)
        db.session.commit()

    return {
        "configuracao": configuracao
    }


# ============================================================
# ATUALIZAÇÃO AUTOMÁTICA
# ============================================================

@app.before_request
def verificar_emprestimos_atrasados():

    if current_user.is_authenticated:

        atualizar_emprestimos_atrasados()


# ============================================================
# INÍCIO
# ============================================================

@app.route("/")
@login_required
def index():

    hoje = date.today()

    total_livros = Livro.query.count()

    total_exemplares = db.session.query(
        db.func.sum(Livro.quantidade)
    ).scalar() or 0

    exemplares_disponiveis = db.session.query(
        db.func.sum(Livro.disponiveis)
    ).scalar() or 0

    total_alunos = Aluno.query.count()

    emprestimos_ativos = Emprestimo.query.filter(
    Emprestimo.status.in_([
        "emprestado",
        "atrasado"
    ])
    ).count()

    emprestimos_atrasados = Emprestimo.query.filter_by(
    status="atrasado"
    ).count()

    emprestimos_recentes = Emprestimo.query.order_by(
        Emprestimo.data_emprestimo.desc(),
        Emprestimo.id.desc()
    ).limit(5).all()

    return render_template(
        "index.html",
        total_livros=total_livros,
        total_exemplares=total_exemplares,
        exemplares_disponiveis=exemplares_disponiveis,
        total_alunos=total_alunos,
        emprestimos_ativos=emprestimos_ativos,
        emprestimos_atrasados=emprestimos_atrasados,
        emprestimos_recentes=emprestimos_recentes
    )

# ============================================================
# ATUALIZAR EMPRÉSTIMOS ATRASADOS
# ============================================================

def atualizar_emprestimos_atrasados():

    hoje = date.today()

    emprestimos = Emprestimo.query.filter(
        Emprestimo.status == "emprestado",
        Emprestimo.data_devolucao_prevista < hoje
    ).all()


    if not emprestimos:

        return


    for emprestimo in emprestimos:

        emprestimo.status = "atrasado"


    db.session.commit()


# ============================================================
# LIVROS
# ============================================================

@app.route("/livros")
@login_required
def livros():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()


    if pesquisa:

        livros = Livro.query.filter(
            db.or_(
                Livro.titulo.ilike(
                    f"%{pesquisa}%"
                ),

                Livro.autor.ilike(
                    f"%{pesquisa}%"
                ),

                Livro.isbn.ilike(
                    f"%{pesquisa}%"
                )
            )
        ).order_by(
            Livro.titulo
        ).all()

    else:

        livros = Livro.query.order_by(
            Livro.titulo
        ).all()


    return render_template(
        "livros.html",
        livros=livros,
        pesquisa=pesquisa
    )


# ============================================================
# CADASTRAR LIVRO
# ============================================================

@app.route(
    "/livros/cadastrar",
    methods=["POST"]
)
@login_required
def cadastrar_livro():

    titulo = request.form.get(
        "titulo",
        ""
    ).strip()

    autor = request.form.get(
        "autor",
        ""
    ).strip()

    isbn = request.form.get(
        "isbn",
        ""
    ).strip()

    editora = request.form.get(
        "editora",
        ""
    ).strip()

    ano = request.form.get(
        "ano",
        ""
    ).strip()

    categoria = request.form.get(
        "categoria",
        ""
    ).strip()

    tipo_exemplar = request.form.get(
        "tipo_exemplar",
        ""
    ).strip()

    quantidade = request.form.get(
        "quantidade",
        ""
    ).strip()

    localizacao = request.form.get(
        "localizacao",
        ""
    ).strip()


    # --------------------------------------------------------
    # VALIDAÇÕES
    # --------------------------------------------------------

    if not titulo:

        flash(
            "O título do livro é obrigatório.",
            "error"
        )

        return redirect("/livros")


    if not autor:

        flash(
            "O autor do livro é obrigatório.",
            "error"
        )

        return redirect("/livros")


    try:

        quantidade_int = int(
            quantidade
        )

    except ValueError:

        flash(
            "A quantidade informada é inválida.",
            "error"
        )

        return redirect("/livros")


    if quantidade_int <= 0:

        flash(
            "A quantidade deve ser maior que zero.",
            "error"
        )

        return redirect("/livros")


    try:

        ano_int = (
            int(ano)
            if ano
            else None
        )

    except ValueError:

        flash(
            "O ano informado é inválido.",
            "error"
        )

        return redirect("/livros")


    # --------------------------------------------------------
    # VERIFICAR ISBN DUPLICADO
    # --------------------------------------------------------

    if isbn:

        livro_existente = Livro.query.filter_by(
            isbn=isbn
        ).first()


        if livro_existente:

            flash(
                "Já existe um livro cadastrado com este ISBN.",
                "error"
            )

            return redirect("/livros")


    # --------------------------------------------------------
    # CRIAR LIVRO
    # --------------------------------------------------------

    livro = Livro(

        titulo=titulo,

        autor=autor,

        isbn=isbn or None,

        editora=editora or None,

        ano=ano_int,

        categoria=categoria or None,

        tipo_exemplar=tipo_exemplar,

        quantidade=quantidade_int,

        disponiveis=quantidade_int,

        localizacao=localizacao or None

    )


    db.session.add(livro)


    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Não foi possível cadastrar o livro.",
            "error"
        )

        return redirect("/livros")


    flash(
        "O livro foi cadastrado com sucesso.",
        "success"
    )


    return redirect("/livros")


# ============================================================
# EDITAR LIVRO
# ============================================================

@app.route(
    "/livros/editar/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def editar_livro(id):

    livro = db.get_or_404(
        Livro,
        id
    )


    if request.method == "POST":

        titulo = request.form.get(
            "titulo",
            ""
        ).strip()

        autor = request.form.get(
            "autor",
            ""
        ).strip()

        isbn = request.form.get(
            "isbn",
            ""
        ).strip()

        editora = request.form.get(
            "editora",
            ""
        ).strip()

        ano = request.form.get(
            "ano",
            ""
        ).strip()

        categoria = request.form.get(
            "categoria",
            ""
        ).strip()

        tipo_exemplar = request.form.get(
            "tipo_exemplar",
            ""
        ).strip()

        quantidade = request.form.get(
            "quantidade",
            ""
        ).strip()

        localizacao = request.form.get(
            "localizacao",
            ""
        ).strip()


        # ----------------------------------------------------
        # VALIDAÇÕES
        # ----------------------------------------------------

        if not titulo:

            flash(
                "O título do livro é obrigatório.",
                "error"
            )

            return redirect(
                f"/livros/editar/{livro.id}"
            )


        if not autor:

            flash(
                "O autor do livro é obrigatório.",
                "error"
            )

            return redirect(
                f"/livros/editar/{livro.id}"
            )


        try:

            nova_quantidade = int(
                quantidade
            )

        except ValueError:

            flash(
                "A quantidade informada é inválida.",
                "error"
            )

            return redirect(
                f"/livros/editar/{livro.id}"
            )


        if nova_quantidade <= 0:

            flash(
                "A quantidade deve ser maior que zero.",
                "error"
            )

            return redirect(
                f"/livros/editar/{livro.id}"
            )


        try:

            ano_int = (
                int(ano)
                if ano
                else None
            )

        except ValueError:

            flash(
                "O ano informado é inválido.",
                "error"
            )

            return redirect(
                f"/livros/editar/{livro.id}"
            )


        # ----------------------------------------------------
        # VERIFICAR ISBN DUPLICADO
        # ----------------------------------------------------

        if isbn:

            livro_existente = Livro.query.filter(
                Livro.isbn == isbn,
                Livro.id != livro.id
            ).first()


            if livro_existente:

                flash(
                    "Já existe outro livro cadastrado com este ISBN.",
                    "error"
                )

                return redirect(
                    f"/livros/editar/{livro.id}"
                )


        # ----------------------------------------------------
        # EXEMPLARES EMPRESTADOS
        # ----------------------------------------------------

        emprestados = Emprestimo.query.filter(
            Emprestimo.livro_id == livro.id,
            Emprestimo.status.in_([
                "emprestado",
                "atrasado"
            ])
        ).count()


        if nova_quantidade < emprestados:

            flash(
                "A quantidade não pode ser menor que o número de exemplares emprestados.",
                "error"
            )

            return redirect(
                f"/livros/editar/{livro.id}"
            )


        # ----------------------------------------------------
        # ATUALIZAR LIVRO
        # ----------------------------------------------------

        livro.titulo = titulo

        livro.autor = autor

        livro.isbn = isbn or None

        livro.editora = editora or None

        livro.ano = ano_int

        livro.categoria = categoria or None

        livro.tipo_exemplar = tipo_exemplar

        livro.quantidade = nova_quantidade

        livro.disponiveis = (
            nova_quantidade - emprestados
        )

        livro.localizacao = (
            localizacao or None
        )


        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Não foi possível atualizar o livro.",
                "error"
            )

            return redirect(
                f"/livros/editar/{livro.id}"
            )


        flash(
            "O livro foi atualizado com sucesso.",
            "success"
        )


        return redirect(
            "/livros"
        )


    return render_template(
        "editar_livro.html",
        livro=livro
    )


# ============================================================
# DETALHES DO LIVRO
# ============================================================

@app.route(
    "/livros/detalhes/<int:id>"
)
@login_required
def detalhes_livro(id):

    livro = db.get_or_404(
        Livro,
        id
    )


    return render_template(
        "detalhes_livro.html",
        livro=livro
    )


# ============================================================
# EXCLUIR LIVRO
# SOMENTE ADMINISTRADOR
# ============================================================

@app.route(
    "/livros/excluir/<int:id>",
    methods=["POST"]
)
@admin_required
def excluir_livro(id):

    livro = db.get_or_404(
        Livro,
        id
    )


    # --------------------------------------------------------
    # VERIFICAR EMPRÉSTIMOS ATIVOS
    # --------------------------------------------------------

    emprestados = Emprestimo.query.filter(
        Emprestimo.livro_id == livro.id,
        Emprestimo.status.in_([
            "emprestado",
            "atrasado"
        ])
    ).count()


    if emprestados > 0:

        flash(
            "Este livro não pode ser excluído porque possui exemplares emprestados.",
            "error"
        )

        return redirect("/livros")


    try:

        db.session.delete(livro)

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Não foi possível excluir o livro.",
            "error"
        )

        return redirect("/livros")


    flash(
        "O livro foi excluído com sucesso.",
        "success"
    )


    return redirect("/livros")


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        )


        usuario = Usuario.query.filter_by(
            email=email
        ).first()


        if usuario and check_password_hash(
            usuario.senha,
            senha
        ):

            login_user(usuario)

            return redirect("/")


        return render_template(
            "login.html",
            erro="E-mail ou senha incorretos."
        )


    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect("/login")


# ============================================================
# USUÁRIOS
# SOMENTE ADMINISTRADOR
# ============================================================

@app.route("/usuarios")
@admin_required
def usuarios():

    usuarios = Usuario.query.order_by(
        Usuario.nome
    ).all()


    return render_template(
        "usuarios.html",
        usuarios=usuarios
    )


# ============================================================
# CADASTRAR USUÁRIO
# SOMENTE ADMINISTRADOR
# ============================================================

@app.route(
    "/usuarios/cadastrar",
    methods=["POST"]
)
@admin_required
def cadastrar_usuario():

    nome = request.form.get(
        "nome",
        ""
    ).strip()

    telefone = request.form.get(
        "telefone",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    senha = request.form.get(
        "senha",
        ""
    )

    admin = (
        request.form.get("admin")
        == "on"
    )


    # --------------------------------------------------------
    # VALIDAÇÕES
    # --------------------------------------------------------

    if not nome:

        flash(
            "O nome do usuário é obrigatório.",
            "error"
        )

        return redirect("/usuarios")


    if not email:

        flash(
            "O e-mail do usuário é obrigatório.",
            "error"
        )

        return redirect("/usuarios")


    if not senha:

        flash(
            "A senha do usuário é obrigatória.",
            "error"
        )

        return redirect("/usuarios")


    # --------------------------------------------------------
    # VERIFICAR E-MAIL DUPLICADO
    # --------------------------------------------------------

    usuario_existente = Usuario.query.filter_by(
        email=email
    ).first()


    if usuario_existente:

        flash(
            "Já existe um usuário cadastrado com este e-mail.",
            "error"
        )

        return redirect("/usuarios")


    # --------------------------------------------------------
    # CRIAR USUÁRIO
    # --------------------------------------------------------

    usuario = Usuario(

        nome=nome,

        telefone=telefone or None,

        email=email,

        senha=generate_password_hash(
            senha
        ),

        admin=admin

    )


    db.session.add(usuario)


    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Não foi possível cadastrar o usuário.",
            "error"
        )

        return redirect("/usuarios")


    flash(
        "O usuário foi cadastrado com sucesso.",
        "success"
    )


    return redirect("/usuarios")


# ============================================================
# EDITAR USUÁRIO
# SOMENTE ADMINISTRADOR
# ============================================================

@app.route(
    "/usuarios/editar/<int:id>",
    methods=["GET", "POST"]
)
@admin_required
def editar_usuario(id):

    usuario = db.get_or_404(
        Usuario,
        id
    )


    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        telefone = request.form.get(
            "telefone",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        )


        # ----------------------------------------------------
        # VALIDAÇÕES
        # ----------------------------------------------------

        if not nome:

            flash(
                "O nome do usuário é obrigatório.",
                "error"
            )

            return redirect(
                f"/usuarios/editar/{usuario.id}"
            )


        if not email:

            flash(
                "O e-mail do usuário é obrigatório.",
                "error"
            )

            return redirect(
                f"/usuarios/editar/{usuario.id}"
            )


        # ----------------------------------------------------
        # VERIFICAR E-MAIL DUPLICADO
        # ----------------------------------------------------

        usuario_existente = Usuario.query.filter(
            Usuario.email == email,
            Usuario.id != usuario.id
        ).first()


        if usuario_existente:

            flash(
                "Já existe outro usuário cadastrado com este e-mail.",
                "error"
            )

            return redirect(
                f"/usuarios/editar/{usuario.id}"
            )


        # ----------------------------------------------------
        # ATUALIZAR DADOS
        # ----------------------------------------------------

        usuario.nome = nome

        usuario.telefone = (
            telefone or None
        )

        usuario.email = email


        if senha:

            usuario.senha = (
                generate_password_hash(
                    senha
                )
            )


        usuario.admin = (
            request.form.get("admin")
            == "on"
        )


        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Não foi possível atualizar o usuário.",
                "error"
            )

            return redirect(
                f"/usuarios/editar/{usuario.id}"
            )


        flash(
            "O usuário foi atualizado com sucesso.",
            "success"
        )


        return redirect(
            "/usuarios"
        )


    return render_template(
        "editar_usuario.html",
        usuario=usuario
    )


# ============================================================
# EXCLUIR USUÁRIO
# SOMENTE ADMINISTRADOR
# ============================================================

@app.route(
    "/usuarios/excluir/<int:id>",
    methods=["POST"]
)
@admin_required
def excluir_usuario(id):

    usuario = db.get_or_404(
        Usuario,
        id
    )


    # --------------------------------------------------------
    # IMPEDIR ADMIN DE EXCLUIR A PRÓPRIA CONTA
    # --------------------------------------------------------

    if usuario.id == current_user.id:

        flash(
            "Você não pode excluir o próprio usuário.",
            "error"
        )

        return redirect("/usuarios")


    try:

        db.session.delete(usuario)

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Não foi possível excluir o usuário.",
            "error"
        )

        return redirect("/usuarios")


    flash(
        "O usuário foi excluído com sucesso.",
        "success"
    )


    return redirect("/usuarios")


# ============================================================
# BUSCAR ALUNO PELA MATRÍCULA
# ============================================================

@app.route(
    "/alunos/buscar"
)
@login_required
def buscar_aluno():

    matricula = request.args.get(
        "matricula",
        ""
    ).strip()


    if not matricula:

        return {
            "encontrado": False
        }


    aluno = Aluno.query.filter_by(
        matricula=matricula
    ).first()


    if not aluno:

        return {
            "encontrado": False
        }


    return {

        "encontrado": True,

        "id": aluno.id,

        "matricula": aluno.matricula,

        "nome": aluno.nome,

        "turma": aluno.turma,

        "telefone": (
            aluno.telefone
            or ""
        )

    }


# ============================================================
# CADASTRAR EMPRÉSTIMO
# USUÁRIO COMUM E ADMINISTRADOR
# ============================================================

@app.route(
    "/emprestimos/cadastrar",
    methods=["POST"]
)
@login_required
def cadastrar_emprestimo():

    matricula = request.form.get(
        "matricula",
        ""
    ).strip()

    nome = request.form.get(
        "nome",
        ""
    ).strip()

    turma = request.form.get(
        "turma",
        ""
    ).strip()

    telefone = request.form.get(
        "telefone",
        ""
    ).strip()

    livro_id = request.form.get(
        "livro_id",
        ""
    ).strip()

    data_emprestimo = request.form.get(
        "data_emprestimo",
        ""
    ).strip()

    data_devolucao_prevista = request.form.get(
        "data_devolucao_prevista",
        ""
    ).strip()


    # --------------------------------------------------------
    # VALIDAÇÕES
    # --------------------------------------------------------

    if not matricula:

        flash(
            "A matrícula do aluno é obrigatória.",
            "error"
        )

        return redirect("/emprestimos/novo")


    if not nome:

        flash(
            "O nome do aluno é obrigatório.",
            "error"
        )

        return redirect("/emprestimos/novo")


    if not turma:

        flash(
            "A turma do aluno é obrigatória.",
            "error"
        )

        return redirect("/emprestimos/novo")


    if not livro_id:

        flash(
            "Nenhum livro foi selecionado.",
            "error"
        )

        return redirect("/emprestimos/novo")


    if not data_emprestimo:

        flash(
            "A data do empréstimo é obrigatória.",
            "error"
        )

        return redirect("/emprestimos/novo")


    if not data_devolucao_prevista:

        flash(
            "A data de devolução prevista é obrigatória.",
            "error"
        )

        return redirect("/emprestimos/novo")


    # --------------------------------------------------------
    # VALIDAR ID DO LIVRO
    # --------------------------------------------------------

    try:

        livro_id = int(
            livro_id
        )

    except ValueError:

        flash(
            "ID do livro inválido.",
            "error"
        )

        return redirect("/emprestimos/novo")


    # --------------------------------------------------------
    # BUSCAR LIVRO
    # --------------------------------------------------------

    livro = db.session.get(
        Livro,
        livro_id
    )


    if not livro:

        flash(
            "Livro não encontrado.",
            "error"
        )

        return redirect("/emprestimos/novo")


    # --------------------------------------------------------
    # VERIFICAR DISPONIBILIDADE
    # --------------------------------------------------------

    if livro.disponiveis <= 0:

        flash(
            "Este livro não possui exemplares disponíveis.",
            "error"
        )

        return redirect("/emprestimos/novo")


    # --------------------------------------------------------
    # CONVERTER DATAS
    # --------------------------------------------------------

    try:

        data_emprestimo_obj = date.fromisoformat(
            data_emprestimo
        )

        data_devolucao_prevista_obj = date.fromisoformat(
            data_devolucao_prevista
        )

    except ValueError:

        flash(
            "Uma das datas informadas é inválida.",
            "error"
        )

        return redirect("/emprestimos/novo")


    # --------------------------------------------------------
    # VALIDAR ORDEM DAS DATAS
    # --------------------------------------------------------

    if data_devolucao_prevista_obj < data_emprestimo_obj:

        flash(
            "A data de devolução não pode ser anterior à data do empréstimo.",
            "error"
        )

        return redirect("/emprestimos/novo")


    # --------------------------------------------------------
    # BUSCAR ALUNO
    # --------------------------------------------------------

    aluno = Aluno.query.filter_by(
        matricula=matricula
    ).first()


    # --------------------------------------------------------
    # CRIAR ALUNO SE NÃO EXISTIR
    # --------------------------------------------------------

    if not aluno:

        aluno = Aluno(

            matricula=matricula,

            nome=nome,

            turma=turma,

            telefone=telefone or None

        )

        db.session.add(
            aluno
        )

        db.session.flush()


    # --------------------------------------------------------
    # CRIAR EMPRÉSTIMO
    # --------------------------------------------------------

    emprestimo = Emprestimo(

        livro_id=livro.id,

        aluno_id=aluno.id,

        data_emprestimo=data_emprestimo_obj,

        data_devolucao_prevista=data_devolucao_prevista_obj,

        status="emprestado"

    )


    db.session.add(
        emprestimo
    )


    # --------------------------------------------------------
    # DIMINUIR DISPONIBILIDADE
    # --------------------------------------------------------

    livro.disponiveis -= 1


    # --------------------------------------------------------
    # SALVAR
    # --------------------------------------------------------

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Não foi possível registrar o empréstimo.",
            "error"
        )

        return redirect("/emprestimos/novo")


    flash(
        "O empréstimo foi registrado com sucesso.",
        "success"
    )


    return redirect(
        "/emprestimos"
    )


# ============================================================
# LISTAR EMPRÉSTIMOS
# ============================================================

@app.route(
    "/emprestimos"
)
@login_required
def emprestimos():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()


    query = Emprestimo.query.join(
        Emprestimo.livro
    ).join(
        Emprestimo.aluno
    )


    if pesquisa:

        pesquisa_sql = f"%{pesquisa}%"


        query = query.filter(
            db.or_(
                Livro.titulo.ilike(
                    pesquisa_sql
                ),

                Livro.autor.ilike(
                    pesquisa_sql
                ),

                Livro.isbn.ilike(
                    pesquisa_sql
                ),

                Aluno.matricula.ilike(
                    pesquisa_sql
                ),

                Aluno.nome.ilike(
                    pesquisa_sql
                ),

                Aluno.turma.ilike(
                    pesquisa_sql
                ),

                Aluno.telefone.ilike(
                    pesquisa_sql
                ),

                Emprestimo.status.ilike(
                    pesquisa_sql
                )
            )
        )


    emprestimos = query.order_by(
        Emprestimo.data_emprestimo.desc(),
        Emprestimo.id.desc()
    ).all()


    return render_template(
        "emprestimos.html",
        emprestimos=emprestimos,
        pesquisa=pesquisa
    )


# ============================================================
# DEVOLVER EMPRÉSTIMO
# USUÁRIO COMUM E ADMINISTRADOR
# ============================================================

@app.route(
    "/emprestimos/devolver/<int:id>",
    methods=["POST"]
)
@login_required
def devolver_emprestimo(id):

    emprestimo = db.get_or_404(
        Emprestimo,
        id
    )


    # --------------------------------------------------------
    # NÃO PERMITIR DEVOLVER DUAS VEZES
    # --------------------------------------------------------

    if emprestimo.status not in [
        "emprestado",
        "atrasado"
    ]:

        flash(
            "Este empréstimo já foi devolvido.",
            "error"
        )

        return redirect("/emprestimos")


    # --------------------------------------------------------
    # REGISTRAR DEVOLUÇÃO
    # --------------------------------------------------------

    emprestimo.data_devolucao = date.today()

    emprestimo.status = "devolvido"


    # --------------------------------------------------------
    # DEVOLVER EXEMPLAR AO ESTOQUE
    # --------------------------------------------------------

    emprestimo.livro.disponiveis += 1


    # --------------------------------------------------------
    # SALVAR
    # --------------------------------------------------------

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Não foi possível registrar a devolução.",
            "error"
        )

        return redirect("/emprestimos")


    flash(
        "O livro foi devolvido com sucesso.",
        "success"
    )


    return redirect(
        "/emprestimos"
    )


# ============================================================
# DETALHES DO EMPRÉSTIMO
# ============================================================

@app.route(
    "/emprestimos/detalhes/<int:id>"
)
@login_required
def detalhes_emprestimo(id):

    emprestimo = db.get_or_404(
        Emprestimo,
        id
    )


    data_geracao = datetime.now()


    return render_template(
        "detalhes_emprestimo.html",
        emprestimo=emprestimo,
        data_geracao=data_geracao
    )


# ============================================================
# COMPROVANTE DO EMPRÉSTIMO
# ============================================================

@app.route(
    "/emprestimos/pdf/<int:id>"
)
@login_required
def comprovante_emprestimo(id):

    emprestimo = db.get_or_404(
        Emprestimo,
        id
    )


    data_geracao = datetime.now()


    return render_template(
        "comprovante_emprestimo.html",
        emprestimo=emprestimo,
        data_geracao=data_geracao
    )



# ============================================================
# BUSCAR LIVROS PARA NOVO EMPRÉSTIMO
# ============================================================

@app.route("/livros/buscar")
@login_required
def buscar_livros():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()


    if not pesquisa:

        return {
            "livros": []
        }


    pesquisa_sql = f"%{pesquisa}%"


    livros = Livro.query.filter(
        db.or_(
            Livro.titulo.ilike(
                pesquisa_sql
            ),

            Livro.autor.ilike(
                pesquisa_sql
            ),

            Livro.isbn.ilike(
                pesquisa_sql
            )
        )
    ).order_by(
        Livro.titulo
    ).limit(10).all()


    resultados = []


    for livro in livros:

        # ----------------------------------------------------
        # VERIFICAR EMPRÉSTIMOS ATIVOS
        # ----------------------------------------------------

        emprestimos_ativos = Emprestimo.query.filter(
            Emprestimo.livro_id == livro.id,
            Emprestimo.status.in_([
                "emprestado",
                "atrasado"
            ])
        ).order_by(
            Emprestimo.data_devolucao_prevista
        ).all()


        # ----------------------------------------------------
        # DATA DE DEVOLUÇÃO
        # ----------------------------------------------------

        data_devolucao = None


        if emprestimos_ativos:

            data_devolucao = (
                emprestimos_ativos[0]
                .data_devolucao_prevista
                .strftime("%d/%m/%Y")
            )


        # ----------------------------------------------------
        # SITUAÇÃO
        # ----------------------------------------------------

        if livro.disponiveis > 0:

            situacao = "disponivel"

        else:

            situacao = "emprestado"


        resultados.append({

            "id": livro.id,

            "titulo": livro.titulo,

            "autor": livro.autor,

            "isbn": livro.isbn or "",

            "quantidade": livro.quantidade,

            "disponiveis": livro.disponiveis,

            "situacao": situacao,

            "data_devolucao": data_devolucao

        })


    return {
        "livros": resultados
    }


# ============================================================
# ALUNOS
# ============================================================

@app.route("/alunos")
@login_required
def alunos():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()


    query = Aluno.query


    if pesquisa:

        pesquisa_sql = f"%{pesquisa}%"


        query = query.filter(
            db.or_(
                Aluno.nome.ilike(
                    pesquisa_sql
                ),

                Aluno.matricula.ilike(
                    pesquisa_sql
                )
            )
        )


    alunos = query.order_by(
        Aluno.nome.asc()
    ).all()


    alunos_com_emprestimos = []


    for aluno in alunos:

        livros_em_posse = Emprestimo.query.filter(
            Emprestimo.aluno_id == aluno.id,
            Emprestimo.status.in_([
                "emprestado",
                "atrasado"
            ])
        ).count()


        alunos_com_emprestimos.append({

            "aluno": aluno,

            "livros_em_posse": livros_em_posse

        })


    return render_template(
        "alunos.html",
        alunos=alunos_com_emprestimos,
        pesquisa=pesquisa
    )


# ============================================================
# DETALHES DO ALUNO
# ============================================================

@app.route(
    "/alunos/detalhes/<int:id>"
)
@login_required
def detalhes_aluno(id):

    aluno = db.get_or_404(
        Aluno,
        id
    )


    emprestimos = Emprestimo.query.filter(
        Emprestimo.aluno_id == aluno.id,
        Emprestimo.status.in_([
            "emprestado",
            "atrasado"
        ])
    ).order_by(
        Emprestimo.data_devolucao_prevista
    ).all()


    return render_template(
        "detalhes_aluno.html",
        aluno=aluno,
        emprestimos=emprestimos
    )

@app.route("/minha-conta/senha", methods=["GET", "POST"])
@login_required
def alterar_senha():

    if request.method == "POST":

        senha_atual = request.form.get("senha_atual", "")
        nova_senha = request.form.get("nova_senha", "")
        confirmar_senha = request.form.get("confirmar_senha", "")

        if not check_password_hash(
            current_user.senha,
            senha_atual
        ):
            flash(
                "A senha atual está incorreta.",
                "error"
            )

            return redirect(
                url_for("alterar_senha")
            )

        if nova_senha != confirmar_senha:
            flash(
                "A nova senha não corresponde à confirmação.",
                "error"
            )

            return redirect(
                url_for("alterar_senha")
            )

        if nova_senha == senha_atual:
            flash(
                "A nova senha deve ser diferente da senha atual.",
                "error"
            )

            return redirect(
                url_for("alterar_senha")
            )

        current_user.senha = generate_password_hash(
            nova_senha
        )

        db.session.commit()

        flash(
            "Senha alterada com sucesso.",
            "success"
        )

        return redirect(
            url_for("alterar_senha")
        )

    return render_template(
        "alterar_senha.html"
    )

@app.route("/configuracoes", methods=["GET", "POST"])
@login_required
@admin_required
def configuracoes():

    configuracao = Configuracao.query.first()

    if not configuracao:
        configuracao = Configuracao()
        db.session.add(configuracao)
        db.session.commit()

    if request.method == "POST":

        configuracao.nome_biblioteca = request.form.get(
            "nome_biblioteca",
            "Biblioteca"
        ).strip()

        configuracao.cor_principal = request.form.get(
            "cor_principal",
            "#2f3e46"
        ).strip()

        arquivo_logo = request.files.get("logo")

        if arquivo_logo and arquivo_logo.filename:

            extensoes_permitidas = {
                "png",
                "jpg",
                "jpeg",
                "webp"
            }

            nome_original = secure_filename(
                arquivo_logo.filename
            )

            extensao = os.path.splitext(
                nome_original
            )[1].lower().lstrip(".")

            if extensao not in extensoes_permitidas:

                flash(
                    "Formato de logo não permitido. "
                    "Use PNG, JPG, JPEG ou WEBP.",
                    "error"
                )

                return redirect(
                    url_for("configuracoes")
                )

            pasta_uploads = os.path.join(
                app.root_path,
                "static",
                "uploads"
            )

            os.makedirs(
                pasta_uploads,
                exist_ok=True
            )

            novo_nome = (
                f"{uuid.uuid4().hex}"
                f".{extensao}"
            )

            caminho_novo_logo = os.path.join(
                pasta_uploads,
                novo_nome
            )

            arquivo_logo.save(
                caminho_novo_logo
            )

            if configuracao.logo:

                caminho_logo_antigo = os.path.join(
                    pasta_uploads,
                    configuracao.logo
                )

                if os.path.exists(
                    caminho_logo_antigo
                ):

                    os.remove(
                        caminho_logo_antigo
                    )

            configuracao.logo = novo_nome

        db.session.commit()

        flash(
            "Configurações salvas com sucesso.",
            "success"
        )

        return redirect(
            url_for("configuracoes")
        )

    return render_template(
        "configuracoes.html",
        configuracao=configuracao
    )

@app.route(
    "/configuracoes/logo/remover",
    methods=["POST"]
)
@login_required
@admin_required
def remover_logo():

    configuracao = Configuracao.query.first()

    if configuracao and configuracao.logo:

        nome_logo = configuracao.logo

        configuracao.logo = None

        db.session.commit()

        pasta_uploads = os.path.join(
            app.root_path,
            "static",
            "uploads"
        )

        caminho_logo = os.path.join(
            pasta_uploads,
            nome_logo
        )

        if os.path.exists(caminho_logo):

            os.remove(caminho_logo)

        flash(
            "Logo removido com sucesso.",
            "success"
        )

    return redirect(
        url_for("configuracoes")
    )




# ============================================================
# INICIALIZAÇÃO DO FLASK
# ============================================================

def iniciar_flask():

    with app.app_context():

        db.create_all()


        # ----------------------------------------------------
        # CRIAR ADMINISTRADOR PADRÃO
        # ----------------------------------------------------

        admin = Usuario.query.filter_by(
            email="admin@biblioteca.local"
        ).first()


        if not admin:

            admin = Usuario(

                nome="Administrador",

                email="admin@biblioteca.local",

                senha=generate_password_hash(
                    "admin123"
                ),

                admin=True

            )


            db.session.add(
                admin
            )

            db.session.commit()


    app.run(

        host="127.0.0.1",

        port=5000,

        debug=False,

        use_reloader=False

    )


# ============================================================
# EXECUÇÃO DA APLICAÇÃO
# ============================================================

if __name__ == "__main__":

    flask_thread = threading.Thread(

        target=iniciar_flask,

        daemon=True

    )


    flask_thread.start()


    webview.create_window(

        "biblist",

        "http://127.0.0.1:5000",

        maximized=True,

        resizable=True

    )


    webview.start()