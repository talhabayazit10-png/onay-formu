import os
import sqlite3
import datetime
from flask import Flask, render_template, request, make_response, url_for, redirect, flash, send_from_directory
from werkzeug.utils import secure_filename
from weasyprint import HTML
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'supersecretkey_change_this_later'

# --- CONFIGURATIONS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads') 
PHOTO_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'photos')
DATABASE = os.path.join(BASE_DIR, 'adaylar.db')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(PHOTO_UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def calculate_score(aday):
    if not aday or not aday['genel_notlar']: return 0
    score = 50
    notes = aday['genel_notlar'].lower()
    if "diksiyonu başarılı" in notes: score += 15
    if "hitabeti başarılı" in notes: score += 15
    if "uyumlu bir izlenim" in notes: score += 10
    if "enerjisi pozisyon için uygun" in notes: score += 10
    if "dava/mahkeme süreci yok" in notes: score += 10
    if "çalışmasına engel bir durumu yok" in notes: score += 10
    if "sigara kullanmıyor" in notes: score += 5
    if "sağlık problemi yok" in notes: score += 5
    if "borcu yok" in notes: score += 5
    if "dava/mahkeme süreci var" in notes: score -= 20
    if "sağlık problemi var" in notes: score -= 10
    if "borcu var" in notes: score -= 5
    return max(0, score)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS adaylar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_soyad TEXT NOT NULL,
                ihtiyac_sube TEXT, ihtiyac_nedeni TEXT, yas TEXT,
                boy TEXT, kilo TEXT, medeni_durum TEXT,
                ikametgah TEXT, mezuniyet TEXT, telefon TEXT,
                basvuru_sitesi TEXT, is_deneyimi TEXT, onaya_sunan TEXT,
                gorusme1_yapan TEXT, gorusme2_yapan TEXT, genel_notlar TEXT,
                foto_path TEXT,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.close()

def get_aday(aday_id):
    conn = get_db_connection()
    aday = conn.execute('SELECT * FROM adaylar WHERE id = ?', (aday_id,)).fetchone()
    conn.close()
    return aday

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/adaylar')
def aday_listesi():
    conn = get_db_connection()
    adaylar_raw = conn.execute('SELECT * FROM adaylar ORDER BY id DESC').fetchall()
    conn.close()
    adaylar = []
    for aday in adaylar_raw:
        aday_dict = dict(aday)
        aday_dict['skor'] = calculate_score(aday_dict)
        adaylar.append(aday_dict)
    return render_template('adaylar.html', adaylar=adaylar)

@app.route('/aday/<int:aday_id>')
def aday_detay(aday_id):
    aday_raw = get_aday(aday_id)
    if aday_raw is None: return "Aday bulunamadı!", 404
    aday = dict(aday_raw)
    aday['skor'] = calculate_score(aday)
    return render_template('detay.html', aday=aday)

@app.route('/aday/<int:aday_id>/duzenle', methods=['POST'])
def aday_duzenle(aday_id):
    aday = get_aday(aday_id)
    if aday is None: return "Aday bulunamadı!", 404
    form_data = request.form.to_dict()
    foto_relative_path = aday['foto_path']
    if 'foto' in request.files:
        file = request.files['foto']
        if file and file.filename != '' and allowed_file(file.filename):
            if aday['foto_path'] and os.path.exists(os.path.join(UPLOAD_FOLDER, aday['foto_path'])):
                os.remove(os.path.join(UPLOAD_FOLDER, aday['foto_path']))
            filename = secure_filename(file.filename)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            file.save(os.path.join(PHOTO_UPLOAD_FOLDER, unique_filename))
            foto_relative_path = os.path.join('photos', unique_filename).replace('\\', '/')
    conn = get_db_connection()
    with conn:
        conn.execute('''
            UPDATE adaylar SET
                ad_soyad = :ad_soyad, ihtiyac_sube = :ihtiyac_sube, ihtiyac_nedeni = :ihtiyac_nedeni,
                yas = :yas, boy = :boy, kilo = :kilo, medeni_durum = :medeni_durum,
                ikametgah = :ikametgah, mezuniyet = :mezuniyet, telefon = :telefon,
                basvuru_sitesi = :basvuru_sitesi, is_deneyimi = :is_deneyimi, onaya_sunan = :onaya_sunan,
                gorusme1_yapan = :gorusme1_yapan, gorusme2_yapan = :gorusme2_yapan,
                genel_notlar = :genel_notlar, foto_path = :foto_path
            WHERE id = :id
        ''', {**form_data, 'foto_path': foto_relative_path, 'id': aday_id})
    conn.close()
    flash(f"'{form_data['ad_soyad']}' isimli aday başarıyla güncellendi!", "success")
    return redirect(url_for('aday_detay', aday_id=aday_id))

@app.route('/aday/<int:aday_id>/sil', methods=['POST'])
def aday_sil(aday_id):
    aday = get_aday(aday_id)
    if aday:
        if aday['foto_path'] and os.path.exists(os.path.join(UPLOAD_FOLDER, aday['foto_path'])):
            os.remove(os.path.join(UPLOAD_FOLDER, aday['foto_path']))
        conn = get_db_connection()
        with conn:
            conn.execute('DELETE FROM adaylar WHERE id = ?', (aday_id,))
        conn.close()
        flash(f"'{aday['ad_soyad']}' isimli aday başarıyla silindi.", "success")
    return redirect(url_for('aday_listesi'))

@app.route('/aday/<int:aday_id>/pdf')
def aday_pdf(aday_id):
    aday = get_aday(aday_id)
    if aday is None: return "Aday bulunamadı!", 404

    render_data = dict(aday)
    render_data['gorusme_tarihi'] = aday['olusturma_tarihi'].split(" ")[0]
    
    # <<< DEĞİŞİKLİK BURADA: PDF için skor hesaplaması eklendi >>>
    render_data['skor'] = calculate_score(render_data)

    if render_data['foto_path']:
        full_photo_path = os.path.join(UPLOAD_FOLDER, render_data['foto_path'])
        if os.path.exists(full_photo_path):
            render_data['foto_path'] = Path(full_photo_path).as_uri()
        else:
            render_data['foto_path'] = None
    
    html_icerik = render_template('sablon.html', data=render_data)
    pdf = HTML(string=html_icerik).write_pdf()

    aday_ad_soyad = aday['ad_soyad']
    pdf_dosya_adi = f"{aday_ad_soyad.replace(' ', '_')}_Onay_Formu.pdf"
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{pdf_dosya_adi}"'
    
    return response

@app.route('/pdf_olustur', methods=['POST'])
def pdf_olustur():
    foto_relative_path = None
    if 'foto' in request.files:
        file = request.files['foto']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            file.save(os.path.join(PHOTO_UPLOAD_FOLDER, unique_filename))
            foto_relative_path = os.path.join('photos', unique_filename).replace('\\', '/')
    form_data = request.form.to_dict()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO adaylar (
            ad_soyad, ihtiyac_sube, ihtiyac_nedeni, yas, boy, kilo, medeni_durum, 
            ikametgah, mezuniyet, telefon, basvuru_sitesi, is_deneyimi, 
            onaya_sunan, gorusme1_yapan, gorusme2_yapan, genel_notlar, foto_path
        ) VALUES (
            :ad_soyad, :ihtiyac_sube, :ihtiyac_nedeni, :yas, :boy, :kilo, :medeni_durum,
            :ikametgah, :mezuniyet, :telefon, :basvuru_sitesi, :is_deneyimi,
            :onaya_sunan, :gorusme1_yapan, :gorusme2_yapan, :genel_notlar, :foto_path
        )
    ''', {**form_data, 'foto_path': foto_relative_path})
    new_aday_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('aday_pdf', aday_id=new_aday_id))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)