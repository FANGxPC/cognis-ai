// ======================================================
// Session State Manager
// ======================================================
// Centralizes all diagnostic session state in sessionStorage
// so it persists across page navigations during the flow:
//   scan → quiz → rootcause → lesson → success

const SESSION_KEYS = {
    SESSION_ID:       "xr_session_id",
    SUBJECT:          "selectedSubject",
    CONCEPT:          "selectedConcept",
    TRAVERSAL_PATH:   "xr_traversal_path",
    CURRENT_NODE_IDX: "xr_current_node_idx",
    MATCHED_NODE_ID:  "xr_matched_node_id",
    ROOT_CAUSE_NODE:  "xr_root_cause_node",
    TRACE_LOG:        "xr_trace_log",
    SIMILARITY_SCORE: "xr_similarity_score",
    QUIZ_SCORE:       "xr_quiz_score",
    TOTAL_QUESTIONS:  "xr_total_questions",
};

const Session = {

    // --------------------------------------------------
    // Getters
    // --------------------------------------------------

    getSessionId() {
        let sid = sessionStorage.getItem(SESSION_KEYS.SESSION_ID);
        if (!sid || sid === "null" || sid === "undefined") {
            sid = "sess_" + Math.random().toString(36).substring(2, 11) + "_" + Date.now();
            sessionStorage.setItem(SESSION_KEYS.SESSION_ID, sid);
        }
        return sid;
    },


    getSubject() {
        return sessionStorage.getItem(SESSION_KEYS.SUBJECT) || "";
    },

    getConcept() {
        return sessionStorage.getItem(SESSION_KEYS.CONCEPT) || "";
    },

    getTraversalPath() {
        try {
            return JSON.parse(sessionStorage.getItem(SESSION_KEYS.TRAVERSAL_PATH)) || [];
        } catch {
            return [];
        }
    },

    getCurrentNodeIndex() {
        return parseInt(sessionStorage.getItem(SESSION_KEYS.CURRENT_NODE_IDX) || "0", 10);
    },

    getCurrentNodeId() {
        const path = this.getTraversalPath();
        const idx = this.getCurrentNodeIndex();
        return path[idx] || null;
    },

    getMatchedNodeId() {
        const val = sessionStorage.getItem(SESSION_KEYS.MATCHED_NODE_ID);
        if (!val || val === "null" || val === "undefined") return null;
        return val;
    },

    getRootCauseNode() {
        const val = sessionStorage.getItem(SESSION_KEYS.ROOT_CAUSE_NODE);
        if (!val || val === "null" || val === "undefined") return null;
        return val;
    },


    getTraceLog() {
        try {
            return JSON.parse(sessionStorage.getItem(SESSION_KEYS.TRACE_LOG)) || [];
        } catch {
            return [];
        }
    },

    getSimilarityScore() {
        return parseFloat(sessionStorage.getItem(SESSION_KEYS.SIMILARITY_SCORE) || "0");
    },

    getQuizScore() {
        return parseInt(sessionStorage.getItem(SESSION_KEYS.QUIZ_SCORE) || "0", 10);
    },

    getTotalQuestions() {
        return parseInt(sessionStorage.getItem(SESSION_KEYS.TOTAL_QUESTIONS) || "0", 10);
    },

    // --------------------------------------------------
    // Setters
    // --------------------------------------------------

    setSessionId(id) {
        sessionStorage.setItem(SESSION_KEYS.SESSION_ID, id);
    },

    setSubject(slug) {
        sessionStorage.setItem(SESSION_KEYS.SUBJECT, slug);
    },

    setConcept(concept) {
        sessionStorage.setItem(SESSION_KEYS.CONCEPT, concept);
    },

    setTraversalPath(path) {
        sessionStorage.setItem(SESSION_KEYS.TRAVERSAL_PATH, JSON.stringify(path));
    },

    setCurrentNodeIndex(idx) {
        sessionStorage.setItem(SESSION_KEYS.CURRENT_NODE_IDX, String(idx));
    },

    advanceNode() {
        const idx = this.getCurrentNodeIndex() + 1;
        this.setCurrentNodeIndex(idx);
        return idx;
    },

    setMatchedNodeId(id) {
        sessionStorage.setItem(SESSION_KEYS.MATCHED_NODE_ID, id);
    },

    setRootCauseNode(id) {
        sessionStorage.setItem(SESSION_KEYS.ROOT_CAUSE_NODE, id);
    },

    setTraceLog(log) {
        sessionStorage.setItem(SESSION_KEYS.TRACE_LOG, JSON.stringify(log));
    },

    setSimilarityScore(score) {
        sessionStorage.setItem(SESSION_KEYS.SIMILARITY_SCORE, String(score));
    },

    setQuizScore(score) {
        sessionStorage.setItem(SESSION_KEYS.QUIZ_SCORE, String(score));
    },

    setTotalQuestions(count) {
        sessionStorage.setItem(SESSION_KEYS.TOTAL_QUESTIONS, String(count));
    },

    // --------------------------------------------------
    // Bulk operations
    // --------------------------------------------------

    /** Store the full result from POST /api/diagnose */
    storeDiagnoseResult(result) {
        this.setSessionId(result.session_id);
        this.setSubject(result.subject);
        this.setMatchedNodeId(result.matched_node_id);
        this.setSimilarityScore(result.similarity_score);
        this.setTraversalPath(result.traversal_path);
        this.setTraceLog(result.trace_log);
        this.setCurrentNodeIndex(0);
        this.setQuizScore(0);
        this.setTotalQuestions(result.traversal_path.length);
    },

    /** Clear all diagnostic session data (but keep login state) */
    clearDiagnosticState() {
        Object.values(SESSION_KEYS).forEach(key => {
            if (key !== "loggedIn") {
                sessionStorage.removeItem(key);
            }
        });
    },

    /** Check if a diagnostic session is active */
    hasActiveSession() {
        return !!this.getSessionId() && this.getTraversalPath().length > 0;
    },
};
