(function() {
    // 1. Inject CSS if not already present
    // (Wait, I'll rely on the user adding the <link> tag for cleaner separation, 
    // but I can also inject it here for convenience. Let's stick to <link> for now).

    // 2. Create Modal HTML Structure
    // The new structure will be created dynamically within the hijackLinks function.

    // 3. Inject Modal into Body and hijack links
    document.addEventListener("DOMContentLoaded", () => {
        const modal = document.createElement('div');
        modal.id = "globalTermsModal";
        modal.className = "terms-modal"; // Assuming the CSS class is still needed for styling

        // Create modal content structure
        modal.innerHTML = `
            <div class="terms-modal-content" style="padding: 0; overflow: hidden; height: 85vh;">
                <span class="terms-close-modal" style="z-index: 10; font-size: 35px; top: 10px; right: 20px;">&times;</span>
                <div id="globalTermsContainer" style="height: 100%; width: 100%;">
                    <iframe id="termsFrame" style="width: 100%; height: 100%; border: none; border-radius: 24px;"></iframe>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        const container = modal.querySelector("#globalTermsContainer"); // Kept for consistency, though not directly used for content anymore
        const iframe = modal.querySelector("#termsFrame");
        const closeModal = modal.querySelector(".terms-close-modal"); // Updated class name to match original

        // Function to hijack each link
        document.querySelectorAll("a").forEach(link => {
            if (link.textContent.trim() === "Terms & Conditions") {
                link.addEventListener("click", (e) => {
                    e.preventDefault();
                    modal.style.display = "block";
                    
                    let targetUrl = link.getAttribute('href');
                    // Append mode=modal to handle self-cleaning
                    if (targetUrl) {
                        const separator = targetUrl.includes('?') ? '&' : '?';
                        iframe.src = targetUrl + separator + "mode=modal";
                    }
                });
            }
        });

        closeModal.onclick = () => {
            modal.style.display = "none";
            iframe.src = ""; // Clear src to stop any media/scripts
        };

        window.onclick = (e) => {
            if (e.target == modal) {
                modal.style.display = "none";
                iframe.src = "";
            }
        };
    });
})();
