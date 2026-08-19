const askBtn = document.getElementById("askBtn");
const questionInput = document.getElementById("question");

const result = document.getElementById("result");
const recommendation = document.getElementById("recommendation");
const evidence = document.getElementById("evidence");
const citation = document.getElementById("citation");
const confidence = document.getElementById("confidence");


// =========================
// Ask Question
// =========================

askBtn.addEventListener("click", askQuestion);


async function askQuestion() {

    const question = questionInput.value.trim();

    if (!question) {
        alert("Please enter a medical question.");
        return;
    }


    // Show result
    result.style.display = "block";


    // Loading state
    askBtn.disabled = true;
    askBtn.textContent = "Searching...";

    recommendation.textContent =
        "Searching the medical guideline...";

    evidence.textContent =
        "Retrieving supporting evidence...";

    citation.textContent = "";

    confidence.textContent = "SEARCHING";

    confidence.className = "confidence";


    try {

        const response = await fetch(
            "http://127.0.0.1:8000/ask",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    question: question
                })
            }
        );


        if (!response.ok) {
            throw new Error(
                `Server returned ${response.status}`
            );
        }


        const data = await response.json();


        // =========================
        // Recommendation
        // =========================

        recommendation.textContent =
            data.recommendation ||
            "No recommendation available.";


        // =========================
        // Evidence
        // =========================

        evidence.textContent =
            data.evidence ||
            "No supporting evidence available.";


        // =========================
        // Citations
        // =========================

        citation.innerHTML = "";

        if (
            data.citations &&
            data.citations.length > 0
        ) {

            data.citations.forEach((source) => {

                const sourceItem =
                    document.createElement("p");

                sourceItem.textContent =
                    `${source.document} — Page ${source.page}`;

                citation.appendChild(sourceItem);

            });

        } else {

            citation.textContent =
                "No citations available.";

        }


        // =========================
        // Confidence
        // =========================

        const confidenceValue =
            data.confidence || "insufficient";

        confidence.textContent =
            confidenceValue.toUpperCase();


        confidence.className =
            `confidence ${confidenceValue}`;


    } catch (error) {

        console.error("API Error:", error);


        recommendation.textContent =
            "Unable to connect to THE DOCTOR server.";


        evidence.textContent =
            "Please make sure FastAPI is running on http://127.0.0.1:8000";


        citation.textContent = "";


        confidence.textContent =
            "ERROR";


        confidence.className =
            "confidence error";

    }


    // Enable button
    askBtn.disabled = false;
    askBtn.textContent = "Ask Question";
}


// =========================
// Suggested Questions
// =========================

const suggestions =
    document.querySelectorAll(".suggestion");


suggestions.forEach((button) => {

    button.addEventListener("click", () => {

        questionInput.value =
            button.textContent.trim();

        questionInput.focus();

    });

});