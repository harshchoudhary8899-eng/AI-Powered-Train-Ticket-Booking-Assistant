(function () {
    const root = document.documentElement;
    const savedTheme = localStorage.getItem("railai-theme") || "light";
    root.setAttribute("data-bs-theme", savedTheme);

    const toggle = document.getElementById("themeToggle");
    if (toggle) {
        toggle.addEventListener("click", function () {
            const nextTheme = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
            root.setAttribute("data-bs-theme", nextTheme);
            localStorage.setItem("railai-theme", nextTheme);
        });
    }

    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const chatMessages = document.getElementById("chatMessages");

    function appendMessage(text, type) {
        if (!chatMessages) {
            return;
        }
        const message = document.createElement("div");
        message.className = "chat-message " + type;
        message.textContent = text;
        chatMessages.appendChild(message);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    if (chatForm && chatInput) {
        chatForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            const message = chatInput.value.trim();
            if (!message) {
                return;
            }
            appendMessage(message, "user");
            chatInput.value = "";

            try {
                const response = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: message })
                });
                const data = await response.json();
                appendMessage(data.reply || "I could not process that request.", "bot");
            } catch (error) {
                appendMessage("The assistant is temporarily unavailable.", "bot");
            }
        });
    }
})();

