from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
import sqlite3
import json
import secrets
import math
import time
from werkzeug.security import check_password_hash
from pathlib import Path
from datetime import date
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import RequestEntityTooLarge

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'lost_and_found.db'
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
UPLOADS = ROOT / 'static' / 'uploads'
UPLOADS.mkdir(parents=True, exist_ok=True)

INSTANCE = ROOT / 'instance'
INSTANCE.mkdir(exist_ok=True)
secret_file = INSTANCE / 'session.key'
if not secret_file.exists():
    secret_file.write_text(secrets.token_hex(32))
app.secret_key = secret_file.read_text().strip()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
ADMIN_CONFIG = INSTANCE / 'admin.json'
LOGIN_ATTEMPTS = {}

def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

def check_csrf():
    if not secrets.compare_digest(request.form.get('csrf_token', ''), session.get('csrf', 'missing')):
        abort(400)



def connection():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


# Additive migration: existing records and tables are retained.
with connection() as db:
    columns = {r['name'] for r in db.execute('PRAGMA table_info(items)')}
    if 'photo_path' not in columns:
        db.execute('ALTER TABLE items ADD COLUMN photo_path TEXT')
    for name, kind in [('map_floor', 'INTEGER'), ('map_x', 'REAL'), ('map_y', 'REAL')]:
        if name not in columns:
            db.execute(f'ALTER TABLE items ADD COLUMN {name} {kind}')
    # Legacy unreturned claims remain active under the simplified two-status workflow.
    db.execute("UPDATE items SET status='Active' WHERE status='Claimed'")
    db.commit()

@app.errorhandler(RequestEntityTooLarge)
def too_large(error):
    return 'Фото слишком большое. Вернитесь назад и выберите файл до 8 МБ.', 413

def save_photo(upload):
    if not upload or not upload.filename:
        return None
    data = upload.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('Фото должно быть не больше 8 МБ.')
    from io import BytesIO
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError('Выберите JPG, PNG или WebP.')
                from PIL import ImageOps
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((1800, 1800))
                name = uuid4().hex + '.jpg'
                image.save(UPLOADS / name, 'JPEG', quality=88)
                return 'uploads/' + name
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Не удалось прочитать фото. Выберите исправный JPG, PNG или WebP.')


def demo_user(db):
    # One dedicated account for unauthenticated *local demos*; never reuse real users' IDs.
    email = 'findly-demo@aitu.edu.kz'
    row = db.execute('SELECT user_id FROM users WHERE email=?', (email,)).fetchone()
    if row:
        return row['user_id']
    cur = db.execute('INSERT INTO users (email, password_hash, role, full_name) VALUES (?, ?, ?, ?)',
                     (email, 'DISABLED_DEMO_LOGIN', 'Student', 'Findly Demo'))
    return cur.lastrowid

@app.route('/')
def home():
    q = request.args.get('q', '').strip()[:100]
    category = request.args.get('category', '', type=str)
    status = request.args.get('status', '', type=str)
    where, params = [], []
    if q:
        where.append('(i.title LIKE ? OR i.description LIKE ? OR i.location LIKE ?)')
        params += [f'%{q}%'] * 3
    if category.isdecimal():
        where.append('i.category_id = ?')
        params.append(int(category))
    else:
        category = ''
    if status in ('Active', 'Returned'):
        where.append('i.status = ?')
        params.append(status)
    else:
        status = ''
    sql = '''SELECT i.photo_path, i.item_id, i.title, i.description, i.location, i.date_reported,
                    i.status, c.name AS category
             FROM items i JOIN categories c ON c.category_id = i.category_id'''
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY i.date_reported DESC, i.item_id DESC LIMIT 200'
    with connection() as db:
        items = db.execute(sql, params).fetchall()
        cats = db.execute('SELECT category_id, name FROM categories ORDER BY name').fetchall()
        total = db.execute('SELECT COUNT(*) FROM items').fetchone()[0]
        active = db.execute("SELECT COUNT(*) FROM items WHERE status='Active'").fetchone()[0]
        returned = db.execute("SELECT COUNT(*) FROM items WHERE status='Returned'").fetchone()[0]
    return render_template('index.html', items=items, categories=cats, q=q,
                           category=category, status=status, total=total, active=active, returned=returned)

@app.get('/statistics')
def statistics():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    with connection() as db:
        summary = db.execute("""SELECT COUNT(*) AS total,
            COALESCE(SUM(status='Active'),0) AS active,
            COALESCE(SUM(status='Returned'),0) AS returned FROM items""").fetchone()
        locations = db.execute("""SELECT COALESCE(NULLIF(TRIM(location),''),'Не указано') AS name,
            COUNT(*) AS total, SUM(status='Active') AS active FROM items
            GROUP BY COALESCE(NULLIF(TRIM(location),''),'Не указано')
            ORDER BY total DESC, name LIMIT 8""").fetchall()
        categories = db.execute("""SELECT c.name, COUNT(i.item_id) AS total,
            COALESCE(SUM(i.status='Returned'),0) AS returned
            FROM categories c LEFT JOIN items i ON i.category_id=c.category_id
            GROUP BY c.category_id, c.name ORDER BY total DESC, c.name""").fetchall()
    rate = round(100 * summary['returned'] / summary['total'], 1) if summary['total'] else 0
    return render_template('statistics.html', summary=summary, locations=locations,
                           categories=categories, rate=rate)

@app.route('/new', methods=['GET', 'POST'])
def new():
    with connection() as db:
        cats = db.execute('SELECT category_id, name FROM categories ORDER BY name').fetchall()
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            location = request.form.get('location', '').strip()
            category = request.form.get('category', '')
            status = 'Active'
            map_floor = map_x = map_y = None
            map_fields = [request.form.get(k, '').strip() for k in ('map_floor', 'map_x', 'map_y')]
            if any(map_fields):
                try:
                    map_floor = int(map_fields[0])
                    map_x, map_y = float(map_fields[1]), float(map_fields[2])
                    if map_floor not in (1, 2, 3) or not all(math.isfinite(v) and 0 <= v <= 1 for v in (map_x, map_y)):
                        raise ValueError()
                except ValueError:
                    flash('Выберите место на карте заново.', 'error')
                    return render_template('new.html', categories=cats), 400
            valid_ids = {str(c['category_id']) for c in cats}
            if not (2 <= len(title) <= 120 and 2 <= len(location) <= 120 and len(description) <= 1000
                    and category in valid_ids and status in ('Active', 'Returned')):
                flash('Проверь обязательные поля и длину текста.', 'error')
            else:
                try:
                    photo_path = save_photo(request.files.get('photo'))
                except ValueError as error:
                    flash(str(error), 'error')
                    return render_template('new.html', categories=cats), 400
                reporter_id = demo_user(db)
                db.execute('''INSERT INTO items (title,description,location,date_reported,status,category_id,reporter_id,photo_path,map_floor,map_x,map_y)
                              VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                           (title, description, location, date.today().isoformat(), status, int(category), reporter_id, photo_path, map_floor, map_x, map_y))
                db.commit()
                flash('Объявление сохранено в локальной базе!', 'success')
                return redirect(url_for('home'))
    return render_template('new.html', categories=cats)

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    with connection() as db:
        item = db.execute('''SELECT i.map_floor,i.map_x,i.map_y,i.photo_path,i.item_id,i.title,i.description,i.location,i.date_reported,i.status,
                                    c.name AS category
                             FROM items i JOIN categories c ON c.category_id=i.category_id
                             WHERE i.item_id=?''', (item_id,)).fetchone()
    if item is None:
        abort(404)
    return render_template('detail.html', item=item)


@app.route('/campus-map')
def campus_map():
    selected = None
    try:
        floor = int(request.args.get('floor', '1'))
        x, y = float(request.args['x']), float(request.args['y'])
        if floor in (1, 2, 3) and all(math.isfinite(v) and 0 <= v <= 1 for v in (x, y)):
            selected = dict(floor=floor, x=x, y=y)
    except (KeyError, ValueError):
        pass
    overview = request.args.get('overview') == '1'
    markers = []
    if overview:
        with connection() as db:
            rows = db.execute("""SELECT item_id,title,location,map_floor,map_x,map_y FROM items
                                 WHERE status='Active' AND map_floor IN (1,2,3)
                                 AND map_x BETWEEN 0 AND 1 AND map_y BETWEEN 0 AND 1
                                 ORDER BY item_id DESC""").fetchall()
        markers = [dict(id=r['item_id'], title=r['title'], location=r['location'],
                        floor=r['map_floor'], x=r['map_x'], y=r['map_y'],
                        url=url_for('item_detail', item_id=r['item_id'])) for r in rows]
    return render_template('map.html', selected=selected, readonly=overview or request.args.get('readonly') == '1',
                           overview=overview, markers=markers)

@app.get('/map')
def lost_items_map():
    with connection() as db:
        items = db.execute("""SELECT item_id,title,location,photo_path,map_floor,map_x,map_y
                              FROM items WHERE status='Active' ORDER BY item_id DESC""").fetchall()
    mapped = [r for r in items if r['map_floor'] in (1, 2, 3)
              and r['map_x'] is not None and r['map_y'] is not None
              and 0 <= r['map_x'] <= 1 and 0 <= r['map_y'] <= 1]
    return render_template('overview.html', items=items, mapped_count=len(mapped))

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        check_csrf()
        key = request.remote_addr
        attempts = [t for t in LOGIN_ATTEMPTS.get(key, []) if time.monotonic() - t < 300]
        LOGIN_ATTEMPTS[key] = attempts
        if len(attempts) >= 5:
            flash('Слишком много попыток. Попробуйте через 5 минут.', 'error')
            return render_template('admin.html', configured=ADMIN_CONFIG.exists()), 429
        config = json.loads(ADMIN_CONFIG.read_text()) if ADMIN_CONFIG.exists() else {}
        if config.get('password_hash') and check_password_hash(config['password_hash'], request.form.get('password', '')):
            session.clear()
            session['admin'] = True
            LOGIN_ATTEMPTS.pop(key, None)
            flash('Вы вошли как администратор. Откройте нужное объявление.', 'success')
            return redirect(url_for('home'))
        attempts.append(time.monotonic())
        flash('Неверный пароль администратора.', 'error')
    return render_template('admin.html', configured=ADMIN_CONFIG.exists())

@app.post('/admin/logout')
def admin_logout():
    check_csrf()
    session.clear()
    return redirect(url_for('home'))

@app.post('/admin/item/<int:item_id>/status')
def update_status(item_id):
    if not session.get('admin'):
        abort(403)
    check_csrf()
    status = request.form.get('status')
    if status not in ('Active', 'Returned'):
        abort(400)
    with connection() as db:
        result = db.execute('UPDATE items SET status=? WHERE item_id=?', (status, item_id))
        if not result.rowcount:
            abort(404)
        db.commit()
    flash('Вещь отмечена как возвращённая.' if status == 'Returned' else 'Объявление снова активно.', 'success')
    return redirect(url_for('item_detail', item_id=item_id))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
