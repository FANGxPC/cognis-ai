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

    // Backend doesn't enforce JWT auth, just generate a random token to satisfy the frontend state
    const username = `guest_${Date.now()}`;
    const token = crypto && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
    
    saveToken(token);
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify({ username, token }));
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
async function remediation(nodeId, sessionId = null, subject = null) {
    let url = `/remediation/${nodeId}`;
    const params = new URLSearchParams();
    if (sessionId) params.append("session_id", sessionId);
    if (subject) params.append("subject", subject);
    if (params.toString()) url += `?${params.toString()}`;

    return apiFetch(url, { method: "GET" });
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

// ------------------------------------------------------
// Subjects and Graph
// ------------------------------------------------------

async function getSubjects() {
    return apiFetch("/subjects");
}

async function getGraph(subject, sessionId = null) {
    let url = `/graph?subject=${subject}`;
    if (sessionId) url += `&session_id=${sessionId}`;
    return apiFetch(url);
}

async function addSubject(topic) {
    return apiFetch("/subjects/add", {
        method: "POST",
        body: JSON.stringify({ topic })
    });
}

async function uploadSubject(file) {
    const formData = new FormData();
    formData.append("file", file);
    
    await ensureGuestLogin();
    
    let response = await fetch(API_BASE + "/subjects/upload", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${authToken}`
        },
        body: formData
    });
    
    if (!response.ok) {
        throw new Error(await response.text());
    }
    return response.json();
}

// ------------------------------------------------------
// AI Chat Tutor
// ------------------------------------------------------

async function chatWithTutor(sessionId, nodeId, message) {
    return apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify({
            session_id: sessionId,
            node_id: nodeId,
            message
        })
    });
}

async function getChatHistory(sessionId, nodeId) {
    return apiFetch(`/chat/history?session_id=${sessionId}&node_id=${nodeId}`);
}

// ------------------------------------------------------
// History & Stats
// ------------------------------------------------------

async function getHistory(limit = 20) {
    return apiFetch(`/history?limit=${limit}`);
}

async function getStats() {
    return apiFetch("/stats");
}