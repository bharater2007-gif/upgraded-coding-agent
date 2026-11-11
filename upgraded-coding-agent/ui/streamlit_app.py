"""Streamlit Control Dashboard for the Upgraded Coding Agent.

Provides an alternative interactive Streamlit UI for task input,
visual state machine monitoring, side-by-side diff review, and HITL approval.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    import streamlit as st
except ImportError:
    st = None


def run_streamlit_app():
    if st is None:
        print("Streamlit is not installed in the current environment.")
        print("Please use the web dashboard at http://localhost:8000 instead.")
        return

    from agent.models import TaskStatus
    from agent.orchestrator import AgentOrchestrator

    st.set_page_config(
        page_title="Upgraded Coding Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🤖 Upgraded Coding Agent: Authentic Intelligence & Self-Healing")
    st.markdown(
        "*Foundations of AI and Authentic Intelligence • Autonomous Task Decomposition & Reflection Loop*"
    )

    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = AgentOrchestrator()
    if "task_id" not in st.session_state:
        st.session_state.task_id = None

    orch: AgentOrchestrator = st.session_state.orchestrator

    # Sidebar: Objectives & Controls
    with st.sidebar:
        st.header("🎯 Coding Objective")
        scenario = st.selectbox(
            "Academic Benchmark Scenario:",
            [
                "LRU Cache (Eviction & Access Bug)",
                "Token Bucket Rate Limiter",
                "Fibonacci Memoization & Bounds",
                "Custom Objective",
            ],
        )

        preset_map = {
            "LRU Cache (Eviction & Access Bug)": "Design and implement an LRU Cache with capacity limit, O(1) get/put, and eviction verification.",
            "Token Bucket Rate Limiter": "Implement a thread-safe token bucket rate limiter with continuous refills.",
            "Fibonacci Memoization & Bounds": "Implement an optimized Fibonacci generator with negative input exception guards.",
        }

        default_text = preset_map.get(scenario, "")
        objective = st.text_area("Objective Specification:", value=default_text, height=120)

        st.subheader("⚙️ Agent Settings")
        require_hitl = st.checkbox("Authentic HITL Review Gate", value=True)
        max_iter = st.slider("Max Self-Healing Retries", min_value=1, max_value=6, value=4)

        if st.button("🚀 Initialize & Launch Agent", use_container_width=True, type="primary"):
            state = orch.create_task(
                objective=objective,
                require_hitl=require_hitl,
                max_iterations=max_iter,
            )
            st.session_state.task_id = state.task_id
            # Perform first step
            orch.step(state.task_id)
            st.rerun()

    task_id = st.session_state.task_id
    if not task_id:
        st.info("👈 Select a scenario or enter an objective in the sidebar to initialize the agent.")
        return

    state = orch.get_task(task_id)
    if not state:
        st.warning("Task not found.")
        return

    # Top Status Bar
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Task ID", state.task_id)
    col2.metric("Agent State", state.status.value)
    col3.metric("Healing Iteration", f"{state.current_iteration} / {state.max_iterations}")
    col4.metric("Reflections Recorded", len(state.reflections))

    # HITL Review Gate Prompt
    if state.status == TaskStatus.HITL_REVIEW:
        st.warning("⚠️ **HITL Review Gate**: The agent requires operator verification before code execution.")
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            if st.button("✅ Approve & Run Tests", use_container_width=True, type="primary"):
                orch.process_hitl_decision(task_id, action="APPROVE")
                orch.run_until_stop(task_id)
                st.rerun()
        with h_col2:
            feedback = st.text_input("Guidance Feedback:", key="hitl_fb")
            if st.button("🔄 Request Re-Plan", use_container_width=True):
                orch.process_hitl_decision(task_id, action="REPLAN", feedback=feedback)
                st.rerun()
        with h_col3:
            if st.button("❌ Reject Patch", use_container_width=True):
                orch.process_hitl_decision(task_id, action="REJECT", feedback=feedback)
                st.rerun()

    # Stepping Controls
    col_step, col_auto = st.columns(2)
    with col_step:
        if st.button("▶️ Step Transition", use_container_width=True):
            orch.step(task_id)
            st.rerun()
    with col_auto:
        if st.button("⏩ Auto Run to Gate / Finish", use_container_width=True):
            orch.run_until_stop(task_id)
            st.rerun()

    # Tabs: Code & Diff, Thought Trace, Terminal
    tab_diff, tab_thoughts, tab_terminal, tab_telemetry = st.tabs([
        "🔍 Code & Diff Inspector",
        "🧠 Reasoning & Reflection Log",
        "💻 Sandbox Terminal",
        "📊 Verification Metrics",
    ])

    with tab_diff:
        if state.current_patch:
            st.markdown(f"**Explanation:** {state.current_patch.explanation}")
            st.subheader("Unified Code Diff")
            st.code(state.current_patch.diff_unified or "# No changes", language="diff")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**`solution.py`**")
            st.code(state.current_code or "# No code synthesized yet.", language="python")
        with c2:
            st.markdown("**`test_solution.py`**")
            st.code(state.test_code or "# No test code synthesized yet.", language="python")

    with tab_thoughts:
        st.subheader("Step-by-Step Cognitive Trace")
        for entry in state.thought_log:
            with st.expander(f"Step {entry.step}: [{entry.phase}] {entry.thought}"):
                if entry.detail:
                    st.code(entry.detail)

    with tab_terminal:
        st.subheader("Subprocess Execution Output")
        if state.execution_result:
            st.text(f"Exit code: {state.execution_result.exit_code} | Duration: {state.execution_result.duration:.2f}s")
            st.text(state.execution_result.stdout)
            if state.execution_result.stderr:
                st.error(state.execution_result.stderr)
        else:
            st.info("Execution has not yet run.")

    with tab_telemetry:
        st.subheader("Quality & Security Audit")
        if state.security_report:
            st.write(f"**AST Security Audit:** {'PASSED' if state.security_report.passed else 'FAILED'}")
            st.write(f"Nodes Scanned: {state.security_report.scanned_nodes}")
            if state.security_report.violations:
                st.error(f"Violations: {state.security_report.violations}")

        if state.execution_result and state.execution_result.linter_report:
            linter = state.execution_result.linter_report
            st.write(f"**Flake8 Compliance:** {'PASSED' if linter.passed else 'VIOLATIONS FOUND'}")
            for v in linter.violations:
                st.warning(f"Line {v.line}, Col {v.column}: [{v.code}] {v.message}")


if __name__ == "__main__":
    run_streamlit_app()
