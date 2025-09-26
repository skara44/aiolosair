# -*- coding: utf-8 -*-
import asyncio
import re
import pandas as pd
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from openai import OpenAI
from num2words import num2words
from langdetect import detect
import json
from dotenv import load_dotenv
import os
import openai

app = FastAPI()

load_dotenv()  # .env dosyasını oku

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Excel yükle ve normalize et

    
df_faults = pd.read_excel("ariza_kodlari.xlsx")
df_faults['LABEL_NORM'] = df_faults['LABEL'].astype(str).str.upper().str.replace(" ", "")

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Aiolos Air Smart Assistant</title>
    </head>
    <body>
        <h1>Aiolos Air Smart Assistant</h1>
        <label for="lang">Language:</label>
        <select id="lang">
            <option value="EN">English</option>
            <option value="DE">Deutsch</option>
            <option value="TR">Türkçe</option>
            <option value="FR">Français</option>
            <option value="ES">Español</option>
            <option value="RU">Русский</option>
        </select><br><br>

        <textarea id="log" rows="20" cols="80" readonly></textarea><br>
        <input type="text" id="msg" placeholder="Write a message"/>
        <button onclick="sendMessage()">Send</button>
        <button onclick="startRecognition()">🎤 Microphone</button>

        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");
            ws.onopen = function() { console.log("WebSocket bağlandı."); }
            ws.onmessage = function(event) {
                var data = JSON.parse(event.data);
                document.getElementById('log').value += "Assistant: " + data.text + "\\n";
                
                // Sesli yanıt
                var msg = new SpeechSynthesisUtterance(data.text);
                msg.lang = data.lang;
                speechSynthesis.speak(msg);
            };

            function sendMessage() {
                var input = document.getElementById("msg");
                var lang = document.getElementById("lang").value;
                if(input.value.trim() === "") return;
                ws.send(JSON.stringify({message: input.value, lang: lang}));
                document.getElementById('log').value += "🎤: " + input.value + "\\n";
                input.value = '';
            }

            // Mikrofon ile ses tanıma
            function startRecognition() {
                if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                    alert("Bu tarayıcı ses tanımayı desteklemiyor.");
                    return;
                }

                var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = document.getElementById("lang").value.toLowerCase() || "tr-TR";
    recognition.interimResults = false;
    recognition.continuous = true; // sürekli dinle
    recognition.maxAlternatives = 1;

    recognition.onstart = function() {
        console.log("Mikrofon açık, dinleniyor...");
        isListening = true;
    };

    recognition.onresult = function(event) {
        let lastResult = event.results[event.results.length - 1];
        let text = lastResult[0].transcript;
        console.log("Tanındı:", text);
        document.getElementById("msg").value = text;
        sendMessage();

        // Sessizlik zamanlayıcısını sıfırla
        resetSilenceTimer();
    };

    recognition.onspeechend = function() {
        console.log("Konuşma bitti, sessizlik sayacı başlatılıyor...");
        resetSilenceTimer();
    };

    recognition.onerror = function(event) {
        console.error("Tanıma hatası:", event.error);
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
            alert("Mikrofon izni verilmedi.");
        }
    };

    recognition.onend = function() {
        console.log("Tanıma durdu.");
        if (isListening) {
            // Chrome bazen kendi kendine kapanıyor, tekrar başlat
            recognition.start();
        }
    };

    recognition.start();

    // 5 saniye sessizlik kontrolü
    function resetSilenceTimer() {
        if (silenceTimer) clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => {
            console.log("5 sn sessizlik - mikrofon kapatılıyor.");
            recognition.stop();
            isListening = false;
        }, 5000); // 5 saniye sessizlik
    }
}
</script>
        
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

LANG_MAP = {
    "en": "en",
    "de": "de",
    "tr": "tr",
    "fr": "fr",
    "es": "es",
    "ru": "ru"
}

def get_fault_info(label, lang='tr'):
    """Excel'den arıza kodu satırını bul ve metni hazırla"""
    label_norm = str(label).strip().upper().replace(" ", "")
    row = df_faults[df_faults['LABEL_NORM'] == label_norm]

    if row.empty:
        return None, lang

    row = row.fillna("").iloc[0]  # NaN yerine boş string koy

    lang = lang.upper()  # Dili normalize et (TR, EN vs)
    
    description = row.get(f"DESCRIPTION_{lang}", "")
    explanation = row.get(f"Aciklama_{lang}", "")
    

    text = ""
    if description:
        text += f"{description}\n"
    if explanation:
        text += f"{explanation}\n"
    
    return text, lang


def parse_input(text: str, selected_lang: str = None):
    """
    Kullanıcıdan gelen metni analiz et:
    - Kod (A01 gibi) varsa çıkar
    - Dili tespit et (ya da kullanıcı seçimini kullan)
    - Dili normalize et (TR, EN vs.)
    """
    clean_text = re.sub(r"\s+", "", text).upper()
    code_match = re.search(r"\b([A-Z]\d{2,3})\b", clean_text)
    code = code_match.group(1) if code_match else None

    # 1) Öncelik: Kullanıcı seçimi
    if selected_lang:
        lang = selected_lang.upper()
    else:
        # 2) Dil tespiti yap
        try:
            detected_lang = detect(text)
        except:
            detected_lang = "tr"
        lang = LANG_MAP.get(detected_lang, "tr").upper()

    return code, lang


def convert_numbers_to_words(text: str, lang: str) -> str:
    def replacer(match):
        num = int(match.group(0))
        try:
            return num2words(num, lang=lang.lower(), to="ordinal")
        except:
            return str(num)
    return re.sub(r'\d+', replacer, text)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Kullanıcı bağlandı")
    try:
        while True:
            data = await websocket.receive_text()
            obj = json.loads(data)
            user_msg = obj.get("message")
            selected_lang = obj.get("lang")
            
            # Burada dili normalize ediyoruz
            code, lang = parse_input(user_msg, selected_lang)

            print(f"Kullanıcıdan: {user_msg} (Dil: {lang})")

            # Eğer arıza kodu girildiyse Excel'den cevap çek
            if code:
                fault_text, _ = get_fault_info(code, lang)
                if fault_text:
                    yanit = fault_text
                else:
                    yanit = f"{code} için bilgi bulunamadı."
            else:
                # GPT yanıtını al
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Sen çok dilli bir asistanısın. Kullanıcının dili {lang} ve cevaplarını sadece bu dilde ver. Detaylı yorum yapma. Rakamları yazıyla yaz."},
                        {"role": "user", "content": user_msg},
                    ]
                )
                yanit = response.choices[0].message.content

            yanit = convert_numbers_to_words(yanit, lang)
            print(f"Assistant: {yanit}")

            await websocket.send_text(json.dumps({"text": yanit, "lang": lang.lower()}))

    except Exception as e:
        print(f"Hata: {str(e)}")
    finally:
        await websocket.close()
        print("Kullanıcı bağlantısı kapandı")

