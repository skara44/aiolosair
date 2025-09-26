var ws = new WebSocket("ws://localhost:8000/ws");

ws.onmessage = function(event) {
    document.getElementById('log').value += "Assistant: " + event.data + "\n";
    // Sesli yanıt
    var msg = new SpeechSynthesisUtterance(event.data);
    speechSynthesis.speak(msg);
};

function sendMessage() {
    var input = document.getElementById("msg");
    ws.send(input.value);
    document.getElementById('log').value += "🎤: " + input.value + "\n";
    input.value = '';
}
