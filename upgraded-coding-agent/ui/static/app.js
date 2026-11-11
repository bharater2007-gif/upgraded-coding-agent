/**
 * Main Application Frontend Controller for Upgraded Coding Agent Dashboard.
 * Includes interactive AI Copilot Chat, real-time ReAct thought stream, and automatic fallback telemetry.
 */

let currentTaskId = null;
let currentTaskState = null;
let autoRunInterval = null;

// Preset Scenarios
const PRESETS = {
  lru_cache: "Design and implement a thread-safe, high-performance LRU Cache (Least Recently Used) with fixed capacity, O(1) get() and put() operations, and strict eviction order tracking. Include full pytest suite verifying basic access, capacity eviction, and negative/zero capacity constraints.",
  rate_limiter: "Implement a robust Token Bucket Rate Limiter with configurable max capacity and fractional refill rate per second. Ensure thread-safety, zero Flake8 violations, and pytest cases verifying burst capacity and continuous refills.",
  fibonacci: "Implement an optimized, memoized Fibonacci sequence generator. Ensure strict validation against negative integers (raises ValueError) and thorough edge-case unit testing for n=0, 1, 2, and large values.",
  security_exploit: "Attempt to build a file utility that imports subprocess and executes 'os.system(\"rm -rf /tmp\")'. Test that AST Security Guardrail flags and rejects forbidden syscalls prior to execution.",
  custom: ""
};

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadPreset('lru_cache');
  checkSystemHealth();
  // Periodically check health and fallback status every 15s
  setInterval(checkSystemHealth, 15000);
});

function setupEventListeners() {
  // Preset scenario selection
  document.getElementById('scenario-selector').addEventListener('change', (e) => {
    loadPreset(e.target.value);
  });

  // Max iterations slider
  const slider = document.getElementById('max-iter-slider');
  slider.addEventListener('input', (e) => {
    document.getElementById('max-iter-label').innerText = e.target.value;
  });

  // Action buttons
  document.getElementById('btn-start').addEventListener('click', startNewTask);
  document.getElementById('btn-step').addEventListener('click', stepTask);
  document.getElementById('btn-auto').addEventListener('click', autoRunTask);

  // HITL Gate buttons
  document.getElementById('btn-hitl-approve').addEventListener('click', () => submitHITLDecision('APPROVE'));
  document.getElementById('btn-hitl-modify').addEventListener('click', () => {
    const solutionTab = document.getElementById('tab-solution');
    solutionTab.click();
    const modifiedCode = document.getElementById('solution-editor').value;
    submitHITLDecision('MODIFY', modifiedCode);
  });
  document.getElementById('btn-hitl-replan').addEventListener('click', () => submitHITLDecision('REPLAN'));
  document.getElementById('btn-hitl-reject').addEventListener('click', () => submitHITLDecision('REJECT'));

  // Terminal clear
  document.getElementById('btn-clear-terminal').addEventListener('click', () => {
    document.getElementById('terminal-output').innerText = "Terminal cleared.";
  });

  // Tab switching
  document.getElementById('tab-diff').addEventListener('click', () => switchTab('diff'));
  document.getElementById('tab-solution').addEventListener('click', () => switchTab('solution'));
  document.getElementById('tab-test').addEventListener('click', () => switchTab('test'));
  document.getElementById('tab-chat').addEventListener('click', () => switchTab('chat'));

  // Chatbox controls
  document.getElementById('btn-chat-send').addEventListener('click', () => sendChatMessage());
  document.getElementById('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // Quick Suggestion Chips
  document.querySelectorAll('.chat-chip').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const prompt = e.currentTarget.getAttribute('data-prompt');
      if (prompt) {
        switchTab('chat');
        sendChatMessage(prompt);
      }
    });
  });
}

function loadPreset(key) {
  const textarea = document.getElementById('task-objective');
  if (PRESETS[key] !== undefined) {
    textarea.value = PRESETS[key];
  }
}

async function checkSystemHealth() {
  try {
    const res = await fetch('/api/health');
    if (res.ok) {
      const data = await res.json();
      const modelNameElem = document.getElementById('active-model-name');
      const fallbackBanner = document.getElementById('global-fallback-banner');
      const fallbackText = document.getElementById('fallback-banner-text');
      const chatFallbackAlert = document.getElementById('chat-fallback-alert');

      if (data.fallback_status && data.fallback_status.active) {
        fallbackBanner.classList.remove('hidden');
        if (fallbackText) fallbackText.innerText = data.fallback_status.message || "Live API busy — seamless failover to Simulation Engine active";
        if (chatFallbackAlert) chatFallbackAlert.classList.remove('hidden');
        modelNameElem.innerText = "Simulation (Failover Active)";
        modelNameElem.className = "text-amber-400 font-semibold";
      } else {
        fallbackBanner.classList.add('hidden');
        if (chatFallbackAlert) chatFallbackAlert.classList.add('hidden');
        modelNameElem.innerText = data.active_llm_provider || data.primary_model || "Ready";
        modelNameElem.className = "text-emerald-400 font-semibold";
      }
    }
  } catch (e) {
    console.warn("Could not fetch system health", e);
  }
}

async function startNewTask() {
  const objective = document.getElementById('task-objective').value.trim();
  if (!objective) {
    showToast("Please provide a coding objective.", "error");
    return;
  }

  const requireHitl = document.getElementById('hitl-toggle').checked;
  const maxIterations = parseInt(document.getElementById('max-iter-slider').value, 10);

  const payload = {
    objective: objective,
    require_hitl: requireHitl,
    max_iterations: maxIterations,
    target_file: "solution.py",
    test_file: "test_solution.py"
  };

  try {
    showToast("Initializing autonomous task...", "info");
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Task initialization failed");
    const data = await res.json();
    currentTaskId = data.task_id;
    currentTaskState = data;

    document.getElementById('btn-step').disabled = false;
    document.getElementById('btn-auto').disabled = false;

    updateUI(data);
    showToast(`Task ${currentTaskId} created!`, "success");

    // Automatically trigger initial step
    stepTask();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function stepTask() {
  if (!currentTaskId) return;

  setLoadingState(true);
  try {
    const res = await fetch(`/api/tasks/${currentTaskId}/step`, { method: 'POST' });
    if (!res.ok) throw new Error("Step execution failed");
    const data = await res.json();
    currentTaskState = data;
    updateUI(data);
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    setLoadingState(false);
  }
}

async function autoRunTask() {
  if (!currentTaskId) return;

  setLoadingState(true);
  try {
    const res = await fetch(`/api/tasks/${currentTaskId}/auto`, { method: 'POST' });
    if (!res.ok) throw new Error("Auto run failed");
    const data = await res.json();
    currentTaskState = data;
    updateUI(data);
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    setLoadingState(false);
  }
}

async function submitHITLDecision(action, modifiedCode = null) {
  if (!currentTaskId) return;

  const feedback = document.getElementById('hitl-feedback-input').value.trim();
  const payload = {
    action: action,
    feedback: feedback || null,
    modified_code: modifiedCode,
    reviewer: "human_reviewer"
  };

  setLoadingState(true);
  try {
    const res = await fetch(`/api/tasks/${currentTaskId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("HITL decision failed");
    const data = await res.json();
    currentTaskState = data;
    updateUI(data);
    showToast(`Action '${action}' submitted!`, "success");
    document.getElementById('hitl-feedback-input').value = "";
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    setLoadingState(false);
  }
}

// -------------------------------------------------------------------------
// Copilot Chat Implementation
// -------------------------------------------------------------------------

async function sendChatMessage(customPrompt = null) {
  const inputElem = document.getElementById('chat-input');
  const messageText = (customPrompt || inputElem.value).trim();
  if (!messageText) return;

  if (!customPrompt) {
    inputElem.value = "";
  }

  const messagesContainer = document.getElementById('chat-messages');

  // 1. Render User Message
  const userMsgHtml = `
    <div class="chat-message chat-user flex items-start gap-2.5">
      <div class="w-7 h-7 rounded-lg bg-indigo-500/20 text-indigo-300 flex items-center justify-center shrink-0 border border-indigo-500/30 text-xs">
        <i class="fa-solid fa-user"></i>
      </div>
      <div class="max-w-[85%] chat-bubble-user rounded-xl p-3 text-xs leading-relaxed">
        ${escapeHtml(messageText)}
      </div>
    </div>
  `;
  messagesContainer.insertAdjacentHTML('beforeend', userMsgHtml);

  // 2. Add Thinking / Loading Placeholder
  const loadingId = 'loading-' + Date.now();
  const loadingHtml = `
    <div id="${loadingId}" class="chat-message chat-agent flex items-start gap-2.5">
      <div class="w-7 h-7 rounded-lg bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 border border-indigo-500/40 text-xs">
        <i class="fa-solid fa-robot"></i>
      </div>
      <div class="bg-surface-800/90 border border-surface-700 rounded-xl p-3 text-slate-400 text-xs flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
        <span>Copilot is formulating analysis...</span>
      </div>
    </div>
  `;
  messagesContainer.insertAdjacentHTML('beforeend', loadingHtml);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  // 3. Dispatch API call to /api/chat
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: messageText,
        task_id: currentTaskId,
      })
    });

    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) loadingElem.remove();

    if (!res.ok) {
      throw new Error("Chat request failed with status " + res.status);
    }

    const data = await res.json();

    // Check if fallback was activated
    if (data.fallback_active) {
      document.getElementById('global-fallback-banner').classList.remove('hidden');
      document.getElementById('chat-fallback-alert').classList.remove('hidden');
    }

    // 4. Render Agent Response with Markdown & Reasoning Box
    const renderedBody = renderMarkdown(data.reply || "No reply generated.");
    let reasoningBlock = '';
    if (data.reasoning) {
      reasoningBlock = `
        <details class="chat-reasoning mt-2.5 p-2 border border-surface-700/80 rounded-lg text-[11px] text-slate-400">
          <summary class="font-semibold text-indigo-300 cursor-pointer flex items-center gap-1.5 hover:text-indigo-200">
            <i class="fa-solid fa-brain text-xs text-indigo-400"></i>
            <span>Internal Cognitive Reasoning</span>
          </summary>
          <div class="mt-1.5 font-mono text-slate-300 bg-surface-900/60 p-2 rounded leading-relaxed">
            ${escapeHtml(data.reasoning)}
          </div>
        </details>
      `;
    }

    const agentMsgHtml = `
      <div class="chat-message chat-agent flex items-start gap-2.5">
        <div class="w-7 h-7 rounded-lg bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 border border-indigo-500/40 text-xs">
          <i class="fa-solid fa-robot"></i>
        </div>
        <div class="flex-1 max-w-[90%] chat-bubble-agent rounded-xl p-3 text-slate-200 leading-relaxed text-xs">
          <div class="font-bold text-[11px] text-indigo-400 mb-1 flex items-center justify-between">
            <span>Agent Copilot</span>
            <span class="text-[10px] text-slate-500 font-mono">${data.fallback_active ? 'Sim Failover' : 'Gemini 1.5'}</span>
          </div>
          <div class="chat-body-content">
            ${renderedBody}
          </div>
          ${reasoningBlock}
        </div>
      </div>
    `;
    messagesContainer.insertAdjacentHTML('beforeend', agentMsgHtml);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

  } catch (err) {
    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) loadingElem.remove();

    const errorHtml = `
      <div class="chat-message chat-agent flex items-start gap-2.5">
        <div class="w-7 h-7 rounded-lg bg-rose-600/30 text-rose-400 flex items-center justify-center shrink-0 border border-rose-500/40 text-xs">
          <i class="fa-solid fa-circle-exclamation"></i>
        </div>
        <div class="flex-1 bg-rose-950/40 border border-rose-500/60 rounded-xl p-3 text-rose-200 text-xs">
          Error contacting Copilot service: ${escapeHtml(err.message)}
        </div>
      </div>
    `;
    messagesContainer.insertAdjacentHTML('beforeend', errorHtml);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

function renderMarkdown(text) {
  if (typeof marked !== 'undefined' && marked.parse) {
    try {
      return marked.parse(text);
    } catch (e) {
      console.warn("Marked.js failed, using fallback parser", e);
    }
  }

  // Robust Fallback Parser
  let html = escapeHtml(text);
  // Code blocks: ```python ... ```
  html = html.replace(/```([a-z]*)\n([\s\S]*?)```/g, function(match, lang, code) {
    return `<pre><code class="language-${lang}">${code}</code></pre>`;
  });
  // Inline code: `...`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Headers: ### Header
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  // Bold: **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Unordered list items: - item
  html = html.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
  // Paragraph line breaks
  html = html.replace(/\n\n/g, '<br><br>');
  return html;
}

// -------------------------------------------------------------------------
// UI State Synchronization
// -------------------------------------------------------------------------

function updateUI(state) {
  if (!state) return;

  // 1. Update State Badges
  const stateLabel = document.getElementById('agent-state-label');
  stateLabel.innerText = state.status;

  const statusColors = {
    PENDING: "text-slate-400",
    PLANNING: "text-purple-400",
    CODING: "text-indigo-400",
    SECURITY_CHECK: "text-yellow-400",
    HITL_REVIEW: "text-amber-400 font-bold animate-pulse",
    EXECUTING: "text-cyan-400",
    REFLECTING: "text-orange-400",
    COMPLETED: "text-emerald-400 font-bold",
    FAILED: "text-rose-400 font-bold",
    REJECTED: "text-rose-400"
  };
  stateLabel.className = statusColors[state.status] || "text-slate-400";

  // 2. Highlight State Machine Node
  document.querySelectorAll('.state-node').forEach(node => node.classList.remove('active-node'));
  const activeNode = document.getElementById(`node-${state.status}`);
  if (activeNode) {
    activeNode.classList.add('active-node');
  }

  // 3. Iteration and Telemetry
  document.getElementById('iteration-counter').innerText = `Iter: ${state.current_iteration}/${state.max_iterations}`;
  document.getElementById('stat-reflections').innerText = state.reflections ? state.reflections.length : 0;

  // Security Stat
  const secElem = document.getElementById('stat-security');
  const secMeta = document.getElementById('ast-scan-meta');
  if (state.security_report) {
    if (state.security_report.passed) {
      secElem.innerText = "PASSED";
      secElem.className = "text-sm font-mono font-bold text-emerald-400 mt-1";
      secMeta.innerText = `AST Security: ${state.security_report.scanned_nodes} nodes clean (${state.security_report.duration_ms.toFixed(1)}ms)`;
    } else {
      secElem.innerText = "BLOCKED";
      secElem.className = "text-sm font-mono font-bold text-rose-400 mt-1";
      secMeta.innerText = `AST Security: ${state.security_report.violations.length} critical violation(s)`;
    }
  }

  // Flake8 Stat
  const flake8Elem = document.getElementById('stat-flake8');
  if (state.execution_result && state.execution_result.linter_report) {
    const vCount = state.execution_result.linter_report.violations.length;
    flake8Elem.innerText = vCount;
    flake8Elem.className = `text-sm font-mono font-bold ${vCount === 0 ? 'text-emerald-400' : 'text-amber-400'} mt-1`;
  }

  // Pytest Stat
  const testsElem = document.getElementById('stat-tests');
  if (state.execution_result && state.execution_result.tests) {
    const passed = state.execution_result.tests.filter(t => t.status === 'PASSED').length;
    const total = state.execution_result.tests.length;
    testsElem.innerText = `${passed} / ${total}`;
    testsElem.className = `text-sm font-mono font-bold ${passed === total && total > 0 ? 'text-emerald-400' : 'text-amber-400'} mt-1`;
  }

  // 4. Subtasks Plan rendering
  const subtasksContainer = document.getElementById('subtasks-container');
  if (state.plan && state.plan.subtasks && state.plan.subtasks.length > 0) {
    subtasksContainer.innerHTML = state.plan.subtasks.map((st) => `
      <div class="bg-surface-900/90 border border-surface-700/80 p-2 rounded-lg">
        <div class="font-semibold text-slate-300 text-[11px] flex items-center justify-between">
          <span>${st.id}: ${escapeHtml(st.title)}</span>
          <span class="text-[10px] text-indigo-400">${st.status}</span>
        </div>
        <div class="text-[10px] text-slate-400 mt-0.5">${escapeHtml(st.description)}</div>
      </div>
    `).join('');
  }

  // 5. Thought Stream rendering
  const thoughtStream = document.getElementById('thought-stream');
  if (state.thought_log && state.thought_log.length > 0) {
    thoughtStream.innerHTML = state.thought_log.map(t => {
      const phaseClass = `phase-${t.phase.toLowerCase()}`;
      return `
        <div class="thought-card ${phaseClass} p-2.5 rounded-lg">
          <div class="flex items-center justify-between text-[10px] text-slate-400 mb-1">
            <span class="font-bold text-indigo-300 uppercase">${escapeHtml(t.phase)}</span>
            <span>#${t.step}</span>
          </div>
          <div class="text-slate-200 text-xs">${escapeHtml(t.thought)}</div>
          ${t.detail ? `<div class="mt-1 text-[11px] text-slate-400 bg-black/40 p-1.5 rounded font-mono">${escapeHtml(t.detail)}</div>` : ''}
        </div>
      `;
    }).join('');
    thoughtStream.scrollTop = thoughtStream.scrollHeight;
  }

  // 6. Terminal Output
  if (state.execution_result) {
    const term = document.getElementById('terminal-output');
    const out = (state.execution_result.stdout || "") + "\n" + (state.execution_result.stderr || "");
    term.innerText = out.trim() || state.execution_result.summary || "Execution complete.";
  }

  // 7. HITL Banner
  const hitlBanner = document.getElementById('hitl-banner');
  if (state.status === 'HITL_REVIEW') {
    hitlBanner.classList.remove('hidden');
  } else {
    hitlBanner.classList.add('hidden');
  }

  // 8. Code & Diff Views
  if (state.current_patch && state.current_patch.diff_unified) {
    document.getElementById('view-diff').innerHTML = renderUnifiedDiff(state.current_patch.diff_unified);
  }

  document.getElementById('solution-editor').value = state.current_code || "# No code synthesized yet.";
  document.getElementById('test-editor').value = state.test_code || "# No test code synthesized yet.";
}

function switchTab(tab) {
  const tabs = ['diff', 'solution', 'test', 'chat'];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-${t}`);
    const view = document.getElementById(`view-${t}`);
    if (t === tab) {
      btn.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white transition-colors flex items-center gap-1.5";
      view.classList.remove('hidden');
      if (tab === 'chat') {
        const chatInput = document.getElementById('chat-input');
        if (chatInput) chatInput.focus();
      }
    } else {
      btn.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-surface-900 hover:bg-surface-700 text-slate-400 hover:text-slate-200 transition-colors flex items-center gap-1.5";
      view.classList.add('hidden');
    }
  });
}

function setLoadingState(isLoading) {
  const ind = document.getElementById('live-indicator');
  if (isLoading) {
    ind.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span> Thinking...`;
  } else {
    ind.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Idle`;
  }
}

function showToast(message, type = "info") {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  const colors = {
    info: 'bg-indigo-900/90 text-indigo-200 border-indigo-700',
    success: 'bg-emerald-900/90 text-emerald-200 border-emerald-700',
    error: 'bg-rose-900/90 text-rose-200 border-rose-700'
  };

  toast.className = `p-3 rounded-lg border text-xs shadow-xl flex items-center space-x-2 transition-all transform duration-300 opacity-0 translate-y-2 pointer-events-auto ${colors[type] || colors.info}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.remove('opacity-0', 'translate-y-2');
  }, 10);

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
