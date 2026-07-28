// ======================================================
// Shared API Layer
// ======================================================

let authToken = localStorage.getItem(STORAGE_KEYS.TOKEN);

// ------------------------------------------------------
// Helpers
// ------------------------------------------------------

function saveToken(token) {
    authToken = token;
    localStorage.setItem(STORAGE_KEYS.TOKEN, token);
}

function getHeaders(extra = {}) {

    const headers = {
        "Content-Type": "application/json",
        ...extra
    };

    if (authToken) {
        headers.Authorization = `Bearer ${authToken}`;
    }

    return headers;
}

// ------------------------------------------------------
// Guest Authentication
// ------------------------------------------------------

async function ensureGuestLogin() {
    if (authToken) return;

    const username = `guest_${Date.now()}`;
    const password = crypto && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    const email = `${username}@example.com`;

    // Try Register
    let response = await fetch(
        `${API_BASE}/auth/register`,
        {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({
                email,
                username,
                password
            })
        }
    );

    // If register failed (e.g., already exists) -> try Login
    if (!response.ok) {
        response = await fetch(
            `${API_BASE}/auth/login`,
            {
                method: "POST",
                headers: getHeaders(),
                body: JSON.stringify({
                    email,
                    password
                })
            }
        );
    }

    if (!response.ok) {
        throw new Error("Authentication failed.");
    }

    const data = await response.json();
    saveToken(data.token);
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(data));
}

// ------------------------------------------------------
// Generic Fetch
// ------------------------------------------------------
async function apiFetch(url, options = {}) {

    await ensureGuestLogin();

    let response = await fetch(
        API_BASE + url,
        {
            ...options,
            headers: getHeaders(options.headers)
        }
    );

    if (response.status === 401) {

        localStorage.removeItem(STORAGE_KEYS.TOKEN);
        authToken = null;

        await ensureGuestLogin();

        response = await fetch(
            API_BASE + url,
            {
                ...options,
                headers: getHeaders(options.headers)
            }
        );

    }

    if (!response.ok) {

        throw new Error(await response.text());

    }

    return response.json();

}

// ------------------------------------------------------
// Diagnose
// ------------------------------------------------------

async function diagnose(query, subject = "linear_algebra") {

    return apiFetch("/diagnose", {
        method: "POST",
        body: JSON.stringify({
            query,
            subject
        })
    });
}

// ------------------------------------------------------
// Next Question
// ------------------------------------------------------

async function nextQuestion(sessionId, nodeId) {

    return apiFetch(
        `/probe/next?session_id=${sessionId}&node_id=${nodeId}`
    );
}

// ------------------------------------------------------
// Submit Quiz Answer
// ------------------------------------------------------

async function submitAnswer(sessionId, questionId, answer) {

    return apiFetch("/probe/answer", {
        method: "POST",
        body: JSON.stringify({
            session_id: sessionId,
            question_id: questionId,
            answer
        })
    });
}

// ------------------------------------------------------
// Root Cause
// ------------------------------------------------------

async function explain(sessionId) {

    return apiFetch(
        `/diagnose/explain?session_id=${sessionId}`,
        {
            method: "GET"
        }
    );

}

// ------------------------------------------------------
// Lesson
// ------------------------------------------------------
async function remediation(nodeId) {

    return apiFetch(
        `/remediation/${nodeId}`,
        {
            method: "GET"
        }
    );

}
// ------------------------------------------------------
// Practice
// ------------------------------------------------------

async function practiceAnswer(
    sessionId,
    questionId,
    answer
) {

    return apiFetch("/practice/answer", {
        method: "POST",
        body: JSON.stringify({
            session_id: sessionId,
            question_id: questionId,
            answer
        })
    });
}

// ------------------------------------------------------
// Retest
// ------------------------------------------------------

async function retest(
    sessionId,
    nodeId
) {

    return apiFetch("/retest", {
        method: "POST",
        body: JSON.stringify({
            session_id: sessionId,
            original_node_id: nodeId
        })
    });
}