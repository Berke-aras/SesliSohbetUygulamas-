const socket = io();

// Mesaj gönderme
document.getElementById("send").addEventListener("click", () => {
    let message = document.getElementById("message").value;
    if (message.trim() === "") return;
    socket.emit("send_message", { message: message });
    document.getElementById("message").value = "";
});

socket.on("receive_message", (data) => {
    addMessage(data);
});

function addMessage(data) {
    const li = document.createElement("li");
    let imgTag = data.profile_image_url
        ? `<img src="${data.profile_image_url}" alt="Profil" width="30" height="30">`
        : "";
    li.innerHTML = `${imgTag}<strong>${data.username}:</strong> ${data.message}`;
    document.getElementById("messages").appendChild(li);
}

// Online kullanıcılar güncelleme
socket.on("online_users", (users) => {
    const onlineList = document.getElementById("online-users");
    onlineList.innerHTML = "";
    users.forEach((user) => {
        let li = document.createElement("li");
        if (user.profile_image_url) {
            li.innerHTML = `<img src="${user.profile_image_url}" alt="Profil" width="30" height="30"> ${user.username}`;
        } else {
            li.textContent = user.username;
        }
        onlineList.appendChild(li);
    });
});

// Sesli sohbet bölümü
let localStream;
let peers = {};
let room = "default";

// "Onayla" butonu tıklandığında seçilen aygıtlarla ses akışını başlat
document
    .getElementById("confirm-devices")
    .addEventListener("click", async () => {
        document.getElementById("device-selection").style.display = "none"; // Menüyü gizle
        await startVoice(); // Ses akışını başlat
        document.getElementById("join-voice").style.display = "none";
        document.getElementById("leave-voice").style.display = "inline";
    });

// "Ses Kanalına Katıl" butonu tıklandığında aygıt seçim menüsünü göster
document.getElementById("join-voice").addEventListener("click", async () => {
    document.getElementById("device-selection").style.display = "block"; // Menüyü göster
    await enumerateDevices(); // Aygıtları listele
});

// Ses kanalından ayrılma
document.getElementById("leave-voice").addEventListener("click", () => {
    socket.emit("leave_voice", { room: room });
    document
        .querySelectorAll("[id^='audio-']")
        .forEach((elem) => elem.remove());
    document.getElementById("voice-status").innerText =
        "Ses kanalından ayrıldınız.";
    document.getElementById("leave-voice").style.display = "none";
    document.getElementById("join-voice").style.display = "inline";
});

// Aygıtları listeleme fonksiyonu
async function enumerateDevices() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const inputSelect = document.getElementById("input-device");
    const outputSelect = document.getElementById("output-device");
    inputSelect.innerHTML = "";
    outputSelect.innerHTML = "";
    devices.forEach((device) => {
        let option = document.createElement("option");
        option.value = device.deviceId;
        option.text = device.label || device.kind;
        if (device.kind === "audioinput") {
            inputSelect.appendChild(option);
        } else if (device.kind === "audiooutput") {
            outputSelect.appendChild(option);
        }
    });
}

async function startVoice() {
    // Giriş ve çıkış cihazlarını seçen HTML elemanlarını al
    const inputSelect = document.getElementById("input-device");
    const outputSelect = document.getElementById("output-device");

    // Mikrofon (giriş) için ayarlar
    const constraints = {
        audio: {
            deviceId: inputSelect.value
                ? { exact: inputSelect.value }
                : undefined,
            echoCancellation: true, // Yankı engelleme
            noiseSuppression: true, // Gürültü engelleme
            autoGainControl: true, // Otomatik kazanç kontrolü
        },
    };

    // Mikrofon akışını başlat
    try {
        localStream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (e) {
        console.error("Ses akışı alınamadı:", e);
        document.getElementById("voice-status").innerText =
            "Ses akışı başlatılamadı.";
        return;
    }

    // Ses kanalına katıldığınızı bildir
    document.getElementById("voice-status").innerText =
        "Ses kanalına katıldınız.";
    socket.emit("join_voice", { room: room });

    // Çıkış cihazını (hoparlör) ayarla
    const audioElements = document.querySelectorAll("audio");
    if (outputSelect.value) {
        audioElements.forEach((audio) => {
            audio.setSinkId(outputSelect.value).catch((e) => {
                console.error("Çıkış cihazı ayarlanamadı:", e);
            });
        });
    }

    // Kullanıcı katıldığında peer bağlantısı kur
    socket.on("user_joined", (data) => {
        let peerId = data.socketId;
        if (peerId === socket.id) return; // Kendi ID'nizi kontrol edin
        if (!peers[peerId]) {
            createPeerConnection(peerId, true);
        }
    });

    // Sinyal olaylarını işle
    socket.on("signal", async (data) => {
        let peerId = data.from;
        if (!peers[peerId]) {
            createPeerConnection(peerId, false);
        }
        let pc = peers[peerId];
        if (data.sdp) {
            await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
            if (data.sdp.type === "offer") {
                let answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);
                socket.emit("signal", {
                    room: room,
                    sdp: pc.localDescription,
                    to: peerId,
                    from: socket.id,
                });
            }
        } else if (data.candidate) {
            try {
                await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
            } catch (e) {
                console.error("ICE adayı eklenirken hata:", e);
            }
        }
    });
}

function createPeerConnection(peerId, isOfferer) {
    const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });
    peers[peerId] = pc;
    localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));

    pc.onicecandidate = (event) => {
        if (event.candidate) {
            socket.emit("signal", {
                room: room,
                candidate: event.candidate,
                to: peerId,
                from: socket.id,
            });
        }
    };

    pc.ontrack = (event) => {
        let remoteAudio = document.getElementById("audio-" + peerId);
        if (!remoteAudio) {
            remoteAudio = document.createElement("audio");
            remoteAudio.id = "audio-" + peerId;
            remoteAudio.autoplay = true;
            document.getElementById("voice-status").appendChild(remoteAudio);

            // Ses kontrolü ekle
            let volumeControl = document.createElement("input");
            volumeControl.type = "range";
            volumeControl.min = 0;
            volumeControl.max = 100;
            volumeControl.value = 100;
            volumeControl.addEventListener("input", () => {
                remoteAudio.volume = volumeControl.value / 100;
            });
            document.getElementById("voice-status").appendChild(volumeControl);
        }
        remoteAudio.srcObject = event.streams[0];
    };

    if (isOfferer) {
        pc.onnegotiationneeded = async () => {
            try {
                let offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                socket.emit("signal", {
                    room: room,
                    sdp: pc.localDescription,
                    to: peerId,
                    from: socket.id,
                });
            } catch (e) {
                console.error("Teklif oluşturulurken hata:", e);
            }
        };
    }
}

// Ses kanalındaki kullanıcıları güncelleme (fotoğraf ekli)
socket.on("voice_users", (users) => {
    const voiceList = document.getElementById("voice-users");
    voiceList.innerHTML = "";
    users.forEach((user) => {
        let li = document.createElement("li");
        if (user.profile_image_url) {
            li.innerHTML = `<img src="${user.profile_image_url}" alt="Profil" width="30" height="30"> ${user.username}`;
        } else {
            li.textContent = user.username;
        }
        voiceList.appendChild(li);
    });
});

let isMuted = false;
document.getElementById("mute").addEventListener("click", () => {
    if (!localStream) return; // Ses akışı yoksa işlem yapma
    isMuted = !isMuted;
    localStream.getAudioTracks().forEach((track) => {
        track.enabled = !isMuted;
    });
    document.getElementById("mute").innerText = isMuted
        ? "Susturmayı Aç"
        : "Sustur";
});

// Elemanları al
const requestPermissionBtn = document.getElementById("request-permission");
const permissionContainer = document.getElementById("permission-container");
const voiceContainer = document.getElementById("voice-container");

// Butona tıklama olayı
requestPermissionBtn.addEventListener("click", async () => {
    try {
        // Mikrofon iznini iste
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: true,
        });

        // İzin verildiyse, izin ekranını gizle ve sesli sohbet ekranını göster
        permissionContainer.style.display = "none";
        voiceContainer.style.display = "block";

        // Bu stream yalnızca izin almak için kullanıldı, durduruyoruz
        stream.getTracks().forEach((track) => track.stop());
    } catch (error) {
        console.error("Mikrofon izni alınamadı:", error);
        alert("Mikrofon izni verilmedi. Sesli sohbete katılamazsınız.");
    }
});
