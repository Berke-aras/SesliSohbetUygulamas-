from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from flask_socketio import SocketIO, join_room, emit, disconnect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os, socket, datetime, random, string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app)
db = SQLAlchemy(app)

# Eğer uploads klasörü yoksa oluştur
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Çoktan çoğa ilişki: Sunucu üyeleri
server_members = db.Table('server_members',
    db.Column('server_id', db.Integer, db.ForeignKey('server.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

# -----------------
# Veritabanı Modelleri
# -----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_image_url = db.Column(db.String(200), default='')

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    invite_code = db.Column(db.String(64), unique=True, nullable=False)  # Rastgele oluşturulan benzersiz kod
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    members = db.relationship('User', secondary=server_members, backref='servers')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    profile_image_url = db.Column(db.String(200), default='')

# Global kullanıcı ve sesli sohbet takipleri
online_users = {}   # { socket_id: { 'username': ..., 'profile_image_url': ... } }
voice_users = {}    # { socket_id: { 'socketId': ..., 'username': ... } }

# -----------------
# Yardımcı Fonksiyonlar
# -----------------
def generate_invite_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# -----------------
# Rotalar
# -----------------

# Ana sayfa: Üye olunan sunucuları listeleme
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('home.html', servers=user.servers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['profile_image_url'] = user.profile_image_url
            return redirect(url_for('home'))
        else:
            flash("Geçersiz kullanıcı adı veya şifre")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash("Kullanıcı adı zaten alınmış")
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash("Kayıt başarılı, lütfen giriş yapın")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        username = request.form.get('username')
        if username != user.username and User.query.filter_by(username=username).first():
            flash("Bu kullanıcı adı zaten alınmış")
            return redirect(url_for('profile'))
        user.username = username
        new_password = request.form.get('password')
        if new_password:
            user.password = generate_password_hash(new_password)
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                user.profile_image_url = url_for('uploaded_file', filename=filename)
        db.session.commit()
        session['username'] = user.username
        session['profile_image_url'] = user.profile_image_url
        flash("Profil güncellendi")
    return render_template('profile.html', user=user)

@app.route('/upload', methods=['POST'])
def upload():
    if 'profile_image' not in request.files:
        return redirect(url_for('home'))
    file = request.files['profile_image']
    if file.filename == '':
        return redirect(url_for('home'))
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    response = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

# -----------------
# Sunucu (Server) İşlemleri
# -----------------

# Yeni sunucu oluşturma sayfası
@app.route('/create_server', methods=['GET', 'POST'])
def create_server():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        server_name = request.form.get('server_name')
        if Server.query.filter_by(name=server_name).first():
            flash("Bu isimde bir sunucu zaten var.")
            return redirect(url_for('create_server'))
        invite_code = generate_invite_code()
        while Server.query.filter_by(invite_code=invite_code).first():
            invite_code = generate_invite_code()
        new_server = Server(name=server_name, invite_code=invite_code, owner_id=session['user_id'])
        user = User.query.get(session['user_id'])
        new_server.members.append(user)  # Sunucu oluşturulduğunda kullanıcı otomatik üye olur
        db.session.add(new_server)
        db.session.commit()
        flash("Sunucu oluşturuldu!")
        return redirect(url_for('server_chat', invite_code=invite_code))
    return render_template('create_server.html')

# Davet linkiyle sunucuya katılma

@app.route('/join_server/<invite_code>')
def join_server(invite_code):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    server = Server.query.filter_by(invite_code=invite_code).first()
    if not server:
        flash("Geçersiz davet kodu!")
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if user not in server.members:
        server.members.append(user)
        db.session.commit()
    flash(f"{server.name} sunucusuna katıldınız!")
    return redirect(url_for('server_chat', invite_code=invite_code))

# Sunucu sohbet sayfası (eski index.html'in işlevselliğini burada sunuyoruz)
@app.route('/server/<invite_code>')
def server_chat(invite_code):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    server = Server.query.filter_by(invite_code=invite_code).first()
    if not server:
        flash("Sunucu bulunamadı!")
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if user not in server.members:
        flash("Bu sunucuya erişim izniniz yok.")
        return redirect(url_for('home'))
    messages = Message.query.filter_by(server_id=server.id).order_by(Message.timestamp.asc()).all()
    return render_template('server_chat.html', server=server, messages=messages)

# -----------------
# Socket.IO Olayları
# -----------------

@socketio.on('connect')
def on_connect():
    if 'user_id' in session:
        online_users[request.sid] = {'username': session.get('username'),
                                       'profile_image_url': session.get('profile_image_url')}
        emit('online_users', list(online_users.values()), broadcast=True)
    else:
        disconnect()

@socketio.on('disconnect')
def on_disconnect():
    if request.sid in online_users:
        online_users.pop(request.sid)
        emit('online_users', list(online_users.values()), broadcast=True)
    if request.sid in voice_users:
        voice_users.pop(request.sid)
        emit('voice_users', list(voice_users.values()), broadcast=True)

@socketio.on('send_message')
def handle_message(data):
    server_id = data.get('server_id')
    msg_text = data.get('message')
    user_id = session.get('user_id')
    username = session.get('username')
    profile_image_url = session.get('profile_image_url')
    msg = Message(server_id=server_id, user_id=user_id, username=username,
                  text=msg_text, profile_image_url=profile_image_url)
    db.session.add(msg)
    db.session.commit()
    # Sadece ilgili sunucunun oda (room) üyelerine mesaj gönderiyoruz
    emit('receive_message', {
        'username': username,
        'message': msg_text,
        'profile_image_url': profile_image_url
    }, room=f"server_{server_id}")

@socketio.on('join_server')
def on_join_server(data):
    try:
        server_id = data.get('server_id')
        if not server_id:
            print("[HATA] join_server: server_id eksik!")
            return

        # Kullanıcı oturumunu kontrol et
        if 'user_id' not in session:
            print("[HATA] join_server: Kullanıcı oturumu yok!")
            return

        # Odaya katıl
        room_name = f"server_{server_id}"
        join_room(room_name)
        # print(f"[LOG] Kullanıcı {session['username']}, {room_name} odasına katıldı.")

        # Debug için istemciye yanıt gönder
        emit('join_confirmation', {'status': 'success', 'room': room_name})

    except Exception as e:
        print(f"[HATA] join_server: {str(e)}")

@socketio.on('join_voice')
def handle_join_voice(data):
    server_id = data.get('server_id')
    room = f"server_voice_{server_id}"
    join_room(room)
    user_info = {
        'socketId': request.sid,
        'username': session.get('username'),
        'profile_image_url': session.get('profile_image_url')
    }
    voice_users[request.sid] = user_info
    emit('voice_users', list(voice_users.values()), broadcast=True)
    emit('user_joined', user_info, room=room)

@socketio.on('leave_voice')
def handle_leave_voice(data):
    server_id = data.get('server_id')
    room = f"server_voice_{server_id}"
    if request.sid in voice_users:
        voice_users.pop(request.sid)
    emit('voice_users', list(voice_users.values()), broadcast=True)

@socketio.on('signal')
def handle_signal(data):
    server_id = data.get('server_id')
    room = f"server_voice_{server_id}"
    emit('signal', data, room=room, include_self=False)

@app.route('/leave_server/<invite_code>', methods=['POST'])
def leave_server(invite_code):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    server = Server.query.filter_by(invite_code=invite_code).first()
    if not server:
        flash("Sunucu bulunamadı!")
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if user in server.members:
        if server.owner_id == user.id:
            flash("Sunucunun sahibi olduğunuz için çıkamazsınız. Sunucuyu silmek için aşağıdaki butonu kullanın.")
            return redirect(url_for('server_chat', invite_code=invite_code))
        else:
            server.members.remove(user)
            db.session.commit()
            flash("Sunucudan ayrıldınız.")
    return redirect(url_for('home'))

# Sunucu silme rotası (sadece sunucu sahibi silebilir)
@app.route('/delete_server/<invite_code>', methods=['POST'])
def delete_server(invite_code):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    server = Server.query.filter_by(invite_code=invite_code).first()
    if not server:
        flash("Sunucu bulunamadı!")
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if server.owner_id != user.id:
        flash("Yalnızca sunucu sahibi sunucuyu silebilir.")
        return redirect(url_for('server_chat', invite_code=invite_code))
    db.session.delete(server)
    db.session.commit()
    flash("Sunucu silindi.")
    return redirect(url_for('home'))


# -----------------
# Sunucu Başlangıcı
# -----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print(f"Server IP: {ip_address}")
    socketio.run(app, host='0.0.0.0', debug=True)
