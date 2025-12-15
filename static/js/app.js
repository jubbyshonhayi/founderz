// Simple mobile menu toggle (optional placeholder)
document.addEventListener('DOMContentLoaded', function(){
  const btn = document.getElementById('nav-toggle');
  const nav = document.getElementById('nav-links');
  if(btn && nav){
    btn.addEventListener('click', ()=>{
      nav.classList.toggle('open');
    });
  }
});

document.addEventListener("DOMContentLoaded", function () {
  const chat = document.getElementById("chatbot");
  const chatBody = document.getElementById("chat-body");
  const chatInput = document.getElementById("chat-text");
  const chatToggle = document.getElementById("chat-toggle"); // button to open chat
  const chatSend = document.getElementById("chat-send");     // send button
  const chatClose = document.getElementById("chat-close");   // X button to close chat

  // Clear chat on page load
  chatBody.innerHTML = "";

  // Open chat
  chatToggle.onclick = () => {
    chat.style.display = "flex";
    chatBody.innerHTML = "";
    addMessage("Hi 👋 How can I help you today?");
    chatInput.focus();
  };

  // Close chat
  chatClose.onclick = () => {
    chat.style.display = "none";
    chatBody.innerHTML = ""; // clear messages when closed
  };

  // Send message when button clicked
  chatSend.onclick = sendChat;

  // Send message on Enter key
  chatInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") sendChat();
  });

  function addMessage(text, from = "bot") {
    const div = document.createElement("div");
    div.style.marginBottom = "8px";
    div.innerText = (from === "bot" ? "🤖 " : "🧑 ") + text;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function sendChat() {
    const msg = chatInput.value.trim();
    if (!msg) return;
    addMessage(msg, "user");
    chatInput.value = "";

    // Show typing indicator
    addMessage("Typing...", "bot");
    const typingDiv = chatBody.lastChild;

    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    })
      .then((res) => res.json())
      .then((data) => {
        typingDiv.remove(); // remove typing
        addMessage(data.reply);
      })
      .catch((err) => {
        typingDiv.remove();
        addMessage("Sorry, I couldn't process your request.");
        console.error(err);
      });
  }
});

document.addEventListener("DOMContentLoaded", function () {
  const chat = document.getElementById("chatbot");
  const chatBody = document.getElementById("chat-body");
  const chatInput = document.getElementById("chat-text");
  const chatToggle = document.getElementById("chat-toggle");
  const chatSend = document.getElementById("chat-send");
  const chatClose = document.getElementById("chat-close");

  // Clear chat on page load
  chatBody.innerHTML = "";

  // Open chat
  chatToggle.onclick = () => {
    chat.style.display = "flex";
    chatBody.innerHTML = "";
    addMessage("Hi 👋 How can I help you today?");
    chatInput.focus();
  };

  // Close chat
  chatClose.onclick = () => {
    chat.style.display = "none";
    chatBody.innerHTML = "";
  };

  // Send message
  chatSend.onclick = sendChat;

  // Send on Enter key
  chatInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendChat();
  });

  // Add message to chat
  function addMessage(text, from = "bot") {
    const div = document.createElement("div");
    div.style.marginBottom = "8px";
    div.innerText = (from === "bot" ? "🤖 " : "🧑 ") + text;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  // Send chat to backend
  function sendChat() {
    const msg = chatInput.value.trim();
    if (!msg) return;
    addMessage(msg, "user");
    chatInput.value = "";

    // Show typing
    addMessage("Typing...", "bot");
    const typingDiv = chatBody.lastChild;

    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    })
      .then((res) => res.json())
      .then((data) => {
        typingDiv.remove();
        addMessage(data.reply);
      })
      .catch((err) => {
        typingDiv.remove();
        addMessage("Sorry, I couldn't process your request.");
        console.error(err);
      });
  }

  // Clear chat when user refreshes the page
  window.addEventListener("beforeunload", () => {
    chatBody.innerHTML = "";
  });
});

document.querySelector('.back-to-top').addEventListener('click', function(e) {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
