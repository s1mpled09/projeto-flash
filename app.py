import os, sqlite3, secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', secrets.token_hex(32)),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('HTTPS_ONLY') == '1',
    MAX_CONTENT_LENGTH=1024*1024,
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0
)
default_db = '/tmp/flash.db' if os.environ.get('VERCEL') else os.path.join(os.path.dirname(__file__), 'flash.db')
DB = os.environ.get('FLASH_DB', default_db)
CATEGORIES = ['Montagem de móveis','Elétrica','Encanamento','Limpeza','Pintura','Jardinagem','Informática','Reparos gerais']

def conn():
    db=sqlite3.connect(DB); db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON'); return db

def init_db():
    with conn() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('cliente','profissional')), city TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL, city TEXT NOT NULL, budget REAL NOT NULL CHECK(budget>0), status TEXT NOT NULL DEFAULT 'aberto' CHECK(status IN ('aberto','contratado','concluido')), hired_proposal_id INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS proposals (id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id), professional_id INTEGER NOT NULL REFERENCES users(id), amount REAL NOT NULL CHECK(amount>0), message TEXT NOT NULL, UNIQUE(job_id,professional_id));
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id), sender_id INTEGER NOT NULL REFERENCES users(id), body TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS disputes (id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id), opened_by INTEGER NOT NULL REFERENCES users(id), reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'aberta', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS progress (job_id INTEGER PRIMARY KEY REFERENCES jobs(id), professional_done INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY, job_id INTEGER UNIQUE NOT NULL REFERENCES jobs(id), professional_id INTEGER NOT NULL REFERENCES users(id), rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), comment TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS services_offered (id INTEGER PRIMARY KEY, professional_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, category TEXT NOT NULL, area_of_expertise TEXT NOT NULL, description TEXT NOT NULL, city TEXT NOT NULL, region TEXT NOT NULL, pricing_details TEXT NOT NULL, base_price REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);''')

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response

@app.get('/manifest.webmanifest')
def manifest():
    return send_from_directory(app.static_folder, 'manifest.webmanifest', mimetype='application/manifest+json')

@app.get('/sw.js')
def service_worker():
    response = send_from_directory(app.static_folder, 'sw.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.get('/offline')
def offline():
    return render_template('offline.html')

@app.before_request
def csrf_guard():
    if 'csrf' not in session: session['csrf']=secrets.token_urlsafe(24)
    if request.method=='POST' and not secrets.compare_digest(session['csrf'], request.form.get('csrf','')): abort(400)

@app.context_processor
def globals_for_templates(): return dict(me=current_user(), categories=CATEGORIES, csrf=session.get('csrf'))

def current_user():
    if not session.get('uid'): return None
    with conn() as db: return db.execute('SELECT id,name,email,role,city FROM users WHERE id=?',(session['uid'],)).fetchone()

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args,**kwargs):
            user=current_user()
            if not user: return redirect(url_for('login'))
            if role and user['role']!=role: abort(403)
            return fn(*args,**kwargs)
        return wrapper
    return decorator

@app.route('/')
def index():
    with conn() as db:
        jobs=db.execute('SELECT j.*,u.name client_name FROM jobs j JOIN users u ON u.id=j.client_id WHERE j.status="aberto" ORDER BY j.id DESC LIMIT 6').fetchall()
    return render_template('index.html',jobs=jobs)

@app.route('/cadastro',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip()[:90]; email=request.form.get('email','').strip().lower()[:150]; password=request.form.get('password',''); role=request.form.get('role'); city=request.form.get('city','').strip()[:100]
        if not all([name,email,city]) or '@' not in email or len(password)<8 or role not in ('cliente','profissional'):
            flash('Preencha os campos corretamente. A senha deve ter 8 caracteres ou mais.','error')
        else:
            try:
                with conn() as db:
                    cur=db.execute('INSERT INTO users(name,email,password,role,city) VALUES(?,?,?,?,?)',(name,email,generate_password_hash(password),role,city)); session.clear(); session['uid']=cur.lastrowid
                return redirect(url_for('dashboard'))
            except sqlite3.IntegrityError: flash('Este e-mail já está cadastrado.','error')
    return render_template('auth.html',mode='cadastro')

@app.route('/entrar',methods=['GET','POST'])
def login():
    if request.method=='POST':
        with conn() as db: user=db.execute('SELECT * FROM users WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
        if user and check_password_hash(user['password'],request.form.get('password','')):
            session.clear(); session['uid']=user['id']; return redirect(url_for('dashboard'))
        flash('Credenciais inválidas.','error')
    return render_template('auth.html',mode='entrar')

@app.post('/sair')
@login_required()
def logout(): session.clear(); return redirect(url_for('index'))

@app.route('/painel')
@login_required()
def dashboard():
    me = current_user()
    with conn() as db:
        if me['role'] == 'cliente':
            jobs = db.execute('SELECT * FROM jobs WHERE client_id=? ORDER BY id DESC', (me['id'],)).fetchall()
            proposals = []
            my_services = []
        else:
            jobs = db.execute('SELECT j.* FROM jobs j WHERE j.status="aberto" AND lower(j.city)=lower(?) ORDER BY j.id DESC', (me['city'],)).fetchall()
            proposals = db.execute('SELECT p.*, j.title, j.status FROM proposals p JOIN jobs j ON j.id=p.job_id WHERE p.professional_id=? ORDER BY p.id DESC', (me['id'],)).fetchall()
            my_services = db.execute('SELECT * FROM services_offered WHERE professional_id=? ORDER BY id DESC', (me['id'],)).fetchall()
    return render_template('dashboard.html', jobs=jobs, proposals=proposals, my_services=my_services)

@app.route('/meu-servico/novo', methods=['GET', 'POST'])
@login_required('profissional')
def new_service_offered():
    me = current_user()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()[:120]
        category = request.form.get('category')
        area_of_expertise = request.form.get('area_of_expertise', '').strip()[:120]
        city = request.form.get('city', '').strip()[:100]
        region = request.form.get('region', '').strip()[:150]
        pricing_details = request.form.get('pricing_details', '').strip()[:2000]
        description = request.form.get('description', '').strip()[:2000]
        try:
            base_price = float(request.form.get('base_price', '0'))
        except ValueError:
            base_price = 0.0

        if not all([title, category in CATEGORIES, area_of_expertise, city, region]) or len(pricing_details) < 10 or len(description) < 15:
            flash('Preencha os campos obrigatórios. Detalhe sua área de atuação, região e tabela de valores.', 'error')
        else:
            with conn() as db:
                db.execute(
                    'INSERT INTO services_offered(professional_id, title, category, area_of_expertise, description, city, region, pricing_details, base_price) VALUES (?,?,?,?,?,?,?,?,?)',
                    (me['id'], title, category, area_of_expertise, description, city, region, pricing_details, base_price)
                )
            flash('Serviço profissional publicado com sucesso! Agora os clientes podem encontrar seu perfil nas buscas.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('new_service_offered.html')

@app.post('/meu-servico/<int:service_id>/excluir')
@login_required('profissional')
def delete_service_offered(service_id):
    me = current_user()
    with conn() as db:
        res = db.execute('DELETE FROM services_offered WHERE id=? AND professional_id=?', (service_id, me['id']))
        if res.rowcount == 0:
            abort(404)
    flash('Serviço oferecido excluído com sucesso.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/servico-oferecido/<int:service_id>')
def service_detail(service_id):
    with conn() as db:
        service = db.execute('''
            SELECT s.*, u.name professional_name, u.email professional_email, u.city professional_city,
                   COALESCE((SELECT ROUND(AVG(r.rating), 1) FROM reviews r WHERE r.professional_id = u.id), 0) avg_rating,
                   (SELECT COUNT(*) FROM reviews r WHERE r.professional_id = u.id) total_reviews
            FROM services_offered s
            JOIN users u ON u.id = s.professional_id
            WHERE s.id = ? AND s.active = 1
        ''', (service_id,)).fetchone()
        if not service:
            abort(404)
        reviews = db.execute('''
            SELECT r.*, j.title job_title, j.category FROM reviews r
            JOIN jobs j ON j.id = r.job_id
            WHERE r.professional_id = ?
            ORDER BY r.id DESC LIMIT 6
        ''', (service['professional_id'],)).fetchall()
    return render_template('service_detail.html', service=service, reviews=reviews)

@app.route('/novo-servico',methods=['GET','POST'])
@login_required('cliente')
def new_job():
    if request.method=='POST':
        title=request.form.get('title','').strip()[:110]; cat=request.form.get('category'); description=request.form.get('description','').strip()[:2000]; city=request.form.get('city','').strip()[:100]
        try: budget=float(request.form.get('budget','0'))
        except ValueError: budget=0
        if title and cat in CATEGORIES and len(description)>=15 and city and 0<budget<=1000000:
            with conn() as db: db.execute('INSERT INTO jobs(client_id,title,category,description,city,budget) VALUES(?,?,?,?,?,?)',(current_user()['id'],title,cat,description,city,budget))
            flash('Pedido publicado!','success'); return redirect(url_for('dashboard'))
        flash('Revise os dados. A descrição precisa ter ao menos 15 caracteres.','error')
    return render_template('new_job.html')

@app.route('/servicos')
def jobs():
    cat = request.args.get('categoria', '')
    city = request.args.get('cidade', '').strip()[:100]
    tab = request.args.get('tipo', 'profissionais')

    with conn() as db:
        # 1. Serviços e profissionais cadastrados
        serv_sql = '''
            SELECT s.*, u.name professional_name, u.city professional_city,
                   COALESCE((SELECT ROUND(AVG(r.rating), 1) FROM reviews r WHERE r.professional_id = u.id), 0) avg_rating,
                   (SELECT COUNT(*) FROM reviews r WHERE r.professional_id = u.id) total_reviews
            FROM services_offered s
            JOIN users u ON u.id = s.professional_id
            WHERE s.active = 1
        '''
        serv_args = []
        if cat in CATEGORIES:
            serv_sql += ' AND s.category = ?'
            serv_args.append(cat)
        if city:
            serv_sql += ' AND (LOWER(s.city) LIKE LOWER(?) OR LOWER(s.region) LIKE LOWER(?) OR LOWER(u.city) LIKE LOWER(?))'
            serv_args.extend(['%' + city + '%', '%' + city + '%', '%' + city + '%'])
        serv_sql += ' ORDER BY s.id DESC LIMIT 100'
        services = db.execute(serv_sql, serv_args).fetchall()

        # 2. Pedidos publicados por clientes
        jobs_sql = 'SELECT j.*, u.name client_name FROM jobs j JOIN users u ON u.id = j.client_id WHERE j.status = "aberto"'
        jobs_args = []
        if cat in CATEGORIES:
            jobs_sql += ' AND j.category = ?'
            jobs_args.append(cat)
        if city:
            jobs_sql += ' AND LOWER(j.city) LIKE LOWER(?)'
            jobs_args.append('%' + city + '%')
        jobs_sql += ' ORDER BY j.id DESC LIMIT 100'
        items = db.execute(jobs_sql, jobs_args).fetchall()

    return render_template('jobs.html', jobs=items, services=services, cat=cat, city=city, tab=tab)

@app.route('/servico/<int:job_id>')
def job_detail(job_id):
    with conn() as db:
        job=db.execute('SELECT j.*,u.name client_name FROM jobs j JOIN users u ON u.id=j.client_id WHERE j.id=?',(job_id,)).fetchone()
        if not job: abort(404)
        proposals=db.execute('SELECT p.*,u.name professional_name,coalesce((SELECT round(avg(r.rating),1) FROM reviews r WHERE r.professional_id=u.id),0) avg_rating FROM proposals p JOIN users u ON u.id=p.professional_id WHERE p.job_id=? ORDER BY p.amount',(job_id,)).fetchall()
        review=db.execute('SELECT * FROM reviews WHERE job_id=?',(job_id,)).fetchone()
        dispute_record=db.execute('SELECT * FROM disputes WHERE job_id=?',(job_id,)).fetchone()
        progress_record=db.execute('SELECT * FROM progress WHERE job_id=?',(job_id,)).fetchone()
        assigned_id=hired_professional(db,job)
    return render_template('detail.html',job=job,proposals=proposals,review=review,dispute_record=dispute_record,progress_record=progress_record,assigned_id=assigned_id)

@app.post('/servico/<int:job_id>/proposta')
@login_required('profissional')
def propose(job_id):
    try: amount=float(request.form.get('amount','0'))
    except ValueError: amount=0
    message=request.form.get('message','').strip()[:1000]
    with conn() as db:
        job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job: abort(404)
        if job['status']!='aberto' or not (0<amount<=1000000) or len(message)<10: abort(400)
        try: db.execute('INSERT INTO proposals(job_id,professional_id,amount,message) VALUES(?,?,?,?)',(job_id,current_user()['id'],amount,message)); flash('Proposta enviada!','success')
        except sqlite3.IntegrityError: flash('Você já enviou uma proposta para este pedido.','error')
    return redirect(url_for('job_detail',job_id=job_id))

@app.post('/servico/<int:job_id>/contratar/<int:proposal_id>')
@login_required('cliente')
def hire(job_id,proposal_id):
    with conn() as db:
        proposal=db.execute('SELECT p.id FROM proposals p JOIN jobs j ON j.id=p.job_id WHERE p.id=? AND p.job_id=? AND j.client_id=? AND j.status="aberto"',(proposal_id,job_id,current_user()['id'])).fetchone()
        if not proposal: abort(403)
        db.execute('UPDATE jobs SET hired_proposal_id=?,status="contratado" WHERE id=?',(proposal_id,job_id))
    flash('Profissional contratado! O pagamento protegido é apenas demonstrativo nesta versão.','success'); return redirect(url_for('job_detail',job_id=job_id))

@app.post('/servico/<int:job_id>/concluir')
@login_required('cliente')
def complete(job_id):
    with conn() as db:
        result=db.execute('UPDATE jobs SET status="concluido" WHERE id=? AND client_id=? AND status="contratado" AND EXISTS (SELECT 1 FROM progress WHERE progress.job_id=jobs.id AND professional_done=1) AND NOT EXISTS (SELECT 1 FROM disputes WHERE disputes.job_id=jobs.id AND status="aberta")',(job_id,current_user()['id']))
        if result.rowcount!=1: abort(403)
    flash('Serviço marcado como concluído. Nenhuma transferência financeira foi realizada.','success'); return redirect(url_for('job_detail',job_id=job_id))

@app.post('/servico/<int:job_id>/avaliar')
@login_required('cliente')
def review(job_id):
    try: rating=int(request.form.get('rating','0'))
    except ValueError: rating=0
    comment=request.form.get('comment','').strip()[:500]
    with conn() as db:
        job=db.execute('SELECT j.*,p.professional_id FROM jobs j JOIN proposals p ON p.id=j.hired_proposal_id WHERE j.id=? AND j.client_id=? AND j.status="concluido"',(job_id,current_user()['id'])).fetchone()
        if not job or rating not in range(1,6) or len(comment)<5: abort(400)
        try: db.execute('INSERT INTO reviews(job_id,professional_id,rating,comment) VALUES(?,?,?,?)',(job_id,job['professional_id'],rating,comment)); flash('Avaliação publicada!','success')
        except sqlite3.IntegrityError: flash('Este serviço já foi avaliado.','error')
    return redirect(url_for('job_detail',job_id=job_id))



def hired_professional(db, job):
    if not job['hired_proposal_id']: return None
    row=db.execute('SELECT professional_id FROM proposals WHERE id=? AND job_id=?',(job['hired_proposal_id'],job['id'])).fetchone()
    return row['professional_id'] if row else None

def participant(db,job,user):
    return user['id']==job['client_id'] or user['id']==hired_professional(db,job)

@app.route('/profissional/<int:user_id>')
def professional_profile(user_id):
    with conn() as db:
        person = db.execute("SELECT id, name, city, role FROM users WHERE id=? AND role='profissional'", (user_id,)).fetchone()
        if not person:
            abort(404)
        stats = db.execute('SELECT COUNT(*) AS total, ROUND(AVG(rating), 1) AS average FROM reviews WHERE professional_id=?', (user_id,)).fetchone()
        reviews = db.execute('SELECT r.rating, r.comment, j.category FROM reviews r JOIN jobs j ON j.id=r.job_id WHERE r.professional_id=? ORDER BY r.id DESC LIMIT 12', (user_id,)).fetchall()
        services = db.execute('SELECT * FROM services_offered WHERE professional_id=? AND active=1 ORDER BY id DESC', (user_id,)).fetchall()
    return render_template('profile.html', person=person, stats=stats, reviews=reviews, services=services)

@app.route('/servico/<int:job_id>/conversa',methods=['GET','POST'])
@login_required()
def conversation(job_id):
    user=current_user()
    with conn() as db:
        job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job: abort(404)
        if not participant(db,job,user) or job['status']=='aberto': abort(403)
        if request.method=='POST':
            body=request.form.get('body','').strip()
            if not 1<=len(body)<=1500: flash('Mensagem deve ter entre 1 e 1500 caracteres.','error')
            else:
                db.execute('INSERT INTO messages(job_id,sender_id,body) VALUES(?,?,?)',(job_id,user['id'],body))
                return redirect(url_for('conversation',job_id=job_id))
        messages=db.execute('SELECT m.*,u.name sender FROM messages m JOIN users u ON u.id=m.sender_id WHERE m.job_id=? ORDER BY m.id ASC LIMIT 200',(job_id,)).fetchall()
    return render_template('conversation.html',job=job,messages=messages)

@app.post('/servico/<int:job_id>/finalizar-execucao')
@login_required('profissional')
def finish_work(job_id):
    user=current_user()
    with conn() as db:
        job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job or job['status']!='contratado' or hired_professional(db,job)!=user['id']: abort(403)
        db.execute('INSERT INTO progress(job_id,professional_done) VALUES(?,1) ON CONFLICT(job_id) DO UPDATE SET professional_done=1,updated_at=CURRENT_TIMESTAMP',(job_id,))
    flash('Cliente avisado no acompanhamento: serviço informado como finalizado.','success')
    return redirect(url_for('job_detail',job_id=job_id))

@app.post('/servico/<int:job_id>/contestar')
@login_required()
def dispute(job_id):
    user=current_user(); reason=request.form.get('reason','').strip()
    if not 15<=len(reason)<=1000: abort(400)
    with conn() as db:
        job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job or job['status']!='contratado' or not participant(db,job,user): abort(403)
        try: db.execute('INSERT INTO disputes(job_id,opened_by,reason) VALUES(?,?,?)',(job_id,user['id'],reason))
        except sqlite3.IntegrityError: flash('Já existe uma contestação para este serviço.','error')
        else: flash('Contestação registrada para análise. Nenhum pagamento foi movimentado.','success')
    return redirect(url_for('job_detail',job_id=job_id))

init_db()
if __name__=='__main__':
    app.run(debug=True)
