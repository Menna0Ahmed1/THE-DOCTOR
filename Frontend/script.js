const API_URL = "http://127.0.0.1:8000";

// ===============================
// DOM ELEMENTS
// ===============================

const askBtn = document.getElementById("askBtn");
const questionInput = document.getElementById("question");
const clearBtn = document.getElementById("clearBtn");
const copyRecBtn = document.getElementById("copyRecBtn");

const result = document.getElementById("result");
const recommendation = document.getElementById("recommendation");
const evidence = document.getElementById("evidence");
const citation = document.getElementById("citation");
const confidence = document.getElementById("confidence");
const confidenceWarning = document.getElementById("confidenceWarning");

const historyModal = document.getElementById("historyModal");
const historyClose = document.getElementById("historyClose");
const historyContainer = document.getElementById("historyContainer");

const toastContainer = document.getElementById("toastContainer");


// ===============================
// TOAST NOTIFICATION SYSTEM
// ===============================

function showToast(message, type = "info") {
    const toast = document.createElement("div");

    toast.className = `toast ${type}`;

    let icon = "fa-circle-info";

    if (type === "success") {
        icon = "fa-circle-check";
    }

    if (type === "error") {
        icon = "fa-triangle-exclamation";
    }

    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span>${message}</span>
    `;

    if (toastContainer) {
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";

            setTimeout(() => {
                toast.remove();
            }, 300);

        }, 4000);
    }
}


// ===============================
// HISTORY MODAL
// ===============================

if (historyClose && historyModal) {

    historyClose.addEventListener("click", () => {
        historyModal.style.display = "none";
    });

    historyModal.addEventListener("click", (e) => {
        if (e.target === historyModal) {
            historyModal.style.display = "none";
        }
    });

}


// ===============================
// QUESTION BOX - CLEAR
// ===============================

if (clearBtn) {

    clearBtn.addEventListener("click", () => {

        questionInput.value = "";

        questionInput.focus();

        if (result) {
            result.style.display = "none";
        }

    });

}


// ===============================
// COPY RECOMMENDATION
// ===============================

if (copyRecBtn) {

    copyRecBtn.addEventListener("click", async () => {

        const text = recommendation.textContent;

        if (text && text !== "-") {

            try {

                await navigator.clipboard.writeText(text);

                showToast(
                    "Clinical recommendation copied to clipboard.",
                    "success"
                );

            } catch (error) {

                showToast(
                    "Unable to copy recommendation.",
                    "error"
                );

            }

        }

    });

}


// ===============================
// QUICK SUGGESTION CHIPS
// ===============================

document.querySelectorAll(".suggestion-chip").forEach(chip => {

    chip.addEventListener("click", () => {

        questionInput.value = chip.textContent
            .trim()
            .replace(/^"|"$/g, "");

        questionInput.focus();

    });

});


// ===============================
// ASK BUTTON
// ===============================

if (askBtn) {

    askBtn.addEventListener("click", askQuestion);

}


// ===============================
// CTRL + ENTER
// ===============================

if (questionInput) {

    questionInput.addEventListener("keydown", (e) => {

        if (
            (e.ctrlKey || e.metaKey) &&
            e.key === "Enter"
        ) {

            askQuestion();

        }

    });

}


// ===============================
// MAIN RAG FUNCTION
// ===============================

async function askQuestion() {

    const question = questionInput.value.trim();

    // -------------------------------
    // Validate question
    // -------------------------------

    if (!question) {

        showToast(
            "Please enter a medical or clinical question.",
            "error"
        );

        questionInput.focus();

        return;
    }


    // =====================================================
    // LOGIN REMOVED
    // =====================================================
    //
    // Previously the project checked:
    //
    // localStorage.getItem("doctor_jwt")
    //
    // and prevented the user from asking without login.
    //
    // This has been completely removed.
    //
    // =====================================================


    // ===============================
    // UI LOADING STATE
    // ===============================

    if (result) {
        result.style.display = "flex";
    }

    if (confidenceWarning) {
        confidenceWarning.style.display = "none";
    }


    const btnText = askBtn
        ? askBtn.querySelector(".btn-text")
        : null;

    const btnSpinner = askBtn
        ? askBtn.querySelector(".btn-spinner")
        : null;


    if (askBtn) {
        askBtn.disabled = true;
    }

    if (btnText) {
        btnText.style.display = "none";
    }

    if (btnSpinner) {
        btnSpinner.style.display = "inline-flex";
    }


    // ===============================
    // LOADING MESSAGES
    // ===============================

    recommendation.textContent =
        "Retrieving indexed guidelines and synthesizing verified response...";

    evidence.textContent =
        "Searching document vector space for ground truth.";

    citation.innerHTML = `
        <div class="citation-chip">
            <span class="citation-doc">
                Analyzing citations...
            </span>
        </div>
    `;

    confidence.textContent = "EVALUATING";

    confidence.className = "confidence-pill";


    // ===============================
    // CALL RAG API
    // ===============================

    try {

        const response = await fetch(`${API_URL}/ask`, {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                question: question
            })

        });


        // ===============================
        // API ERROR
        // ===============================

        if (!response.ok) {

            const errorText = await response.text();

            throw new Error(
                `Server returned ${response.status}: ${errorText}`
            );

        }


        // ===============================
        // GET RESPONSE
        // ===============================

        const data = await response.json();


        // ===============================
        // RECOMMENDATION
        // ===============================

        recommendation.textContent =
            data.recommendation ||
            "No recommendation available.";


        // ===============================
        // EVIDENCE
        // ===============================

        evidence.textContent =
            data.evidence ||
            "No direct text quote available.";


        // ===============================
        // CITATIONS
        // ===============================

        citation.innerHTML = "";


        if (
            Array.isArray(data.citations) &&
            data.citations.length > 0
        ) {

            data.citations.forEach((source) => {

                const chip = document.createElement("div");

                chip.className = "citation-chip";


                const docName =
                    source.document ||
                    "Clinical Guideline";


                const page =
                    source.page !== undefined
                        ? source.page
                        : "N/A";


                const section =
                    source.section &&
                    source.section !== "N/A"
                        ? ` • Sec: ${source.section}`
                        : "";


                chip.innerHTML = `
                    <span class="citation-doc">
                        <i class="fa-solid fa-file-pdf"></i>
                        ${escapeHtml(docName)}
                    </span>

                    <span class="citation-page">
                        <i class="fa-regular fa-bookmark"></i>
                        Page ${page}${section}
                    </span>
                `;


                citation.appendChild(chip);

            });

        } else {

            citation.innerHTML = `
                <div class="citation-chip">
                    <span class="citation-doc">
                        No specific citations attached
                    </span>
                </div>
            `;

        }


        // ===============================
        // CONFIDENCE LEVEL
        // ===============================

        const confValue =
            (data.confidence || "insufficient")
                .toLowerCase();


        confidence.textContent =
            confValue.toUpperCase();


        confidence.className =
            `confidence-pill ${confValue}`;


        // ===============================
        // LOW CONFIDENCE WARNING
        // ===============================

        if (confValue === "low") {

            confidenceWarning.style.display = "flex";

        } else {

            confidenceWarning.style.display = "none";

        }


        // ===============================
        // SUCCESS
        // ===============================

        showToast(
            "Guideline analysis complete.",
            "success"
        );

    }


    // ===============================
    // ERROR HANDLING
    // ===============================

    catch (error) {

        console.error(
            "Clinical RAG API Error:",
            error
        );


        recommendation.textContent =
            "Error communicating with THE DOCTOR API.";


        evidence.textContent =
            "Please verify the FastAPI server is running on http://127.0.0.1:8000";


        citation.innerHTML = `
            <div
                class="citation-chip"
                style="border-color: var(--danger);"
            >

                <span
                    class="citation-doc"
                    style="color: var(--danger);"
                >

                    ${escapeHtml(error.message)}

                </span>

            </div>
        `;


        confidence.textContent = "ERROR";

        confidence.className =
            "confidence-pill error";


        showToast(
            error.message,
            "error"
        );

    }


    // ===============================
    // RESET BUTTON
    // ===============================

    finally {

        if (askBtn) {
            askBtn.disabled = false;
        }

        if (btnText) {
            btnText.style.display = "inline-flex";
        }

        if (btnSpinner) {
            btnSpinner.style.display = "none";
        }

    }

}


// ===============================
// ESCAPE HTML
// ===============================

function escapeHtml(str) {

    if (!str) {
        return "";
    }

    return String(str)

        .replace(/&/g, "&amp;")

        .replace(/</g, "&lt;")

        .replace(/>/g, "&gt;")

        .replace(/"/g, "&quot;")

        .replace(/'/g, "&#039;");
}