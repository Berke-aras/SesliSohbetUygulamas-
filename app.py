from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from flask_socketio import SocketIO, join_room, emit, disconnect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os, socket, datetime

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

# -----------------
# Veritabanı Modelleri
# -----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_image_url = db.Column(db.String(200), default='')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Global kullanıcı takipleri
online_users = {}   # { socket_id: { 'username': ..., 'profile_image_url': ... } }
voice_users = {}    # { socket_id: { 'socketId': ..., 'username': ... } }


# -----------------
# Rotalar
# -----------------

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    messages = Message.query.order_by(Message.timestamp.asc()).all()
    return render_template('index.html', messages=messages)

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
            return redirect(url_for('index'))
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
        return redirect(url_for('index'))
    file = request.files['profile_image']
    if file.filename == '':
        return redirect(url_for('index'))
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# -----------------
# Socket.IO Olayları
# -----------------

@socketio.on('connect')
def on_connect():
    if 'user_id' in session:
        online_users[request.sid] = {'username': session.get('username'), 'profile_image_url': session.get('profile_image_url')}
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
    user_id = session.get('user_id')
    username = session.get('username')
    msg_text = data.get('message')
    msg = Message(user_id=user_id, username=username, text=msg_text)
    db.session.add(msg)
    db.session.commit()
    emit('receive_message', {
        'username': username,
        'message': msg_text,
        'profile_image_url': session.get('profile_image_url')
    }, broadcast=True)

@socketio.on('join_voice')
def handle_join_voice(data):
    room = data.get('room', 'default')
    join_room(room)
    user_info = {'socketId': request.sid, 'username': session.get('username')}
    voice_users[request.sid] = user_info
    emit('voice_users', list(voice_users.values()), broadcast=True)
    emit('user_joined', user_info, room=room)

@socketio.on('leave_voice')
def handle_leave_voice(data):
    room = data.get('room', 'default')
    if request.sid in voice_users:
        voice_users.pop(request.sid)
    emit('voice_users', list(voice_users.values()), broadcast=True)

@socketio.on('signal')
def handle_signal(data):
    room = data.get('room', 'default')
    emit('signal', data, room=room, include_self=False)

# -----------------
# Sunucu Başlangıcı ve IP Bilgisi
# -----------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Tabloları oluşturuyoruz
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print(f"Server IP: {ip_address}")
    socketio.run(app, host='0.0.0.0', debug=True)