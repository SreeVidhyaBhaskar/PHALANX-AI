import json
import streamlit as st

# ---------------------------------------------------------
# PHALANX-AI: CIVILIAN ENVIRONMENTAL ENGINEERING AGENT
# ---------------------------------------------------------

st.set_page_config(
    page_title="PHALANX-AI | Engineering Agent",
    page_icon="🌐",
    layout="wide"
)

st.markdown("""
<style>
/* Main application */
.stApp {
    background-color: #080D17;
    color: #E8EDF5;
}

/* Main content */
section.main > div {
    background-color: #080D17;
}

/* Headings */
h1, h2, h3, h4 {
    color: #F1F5FC !important;
}

/* All ordinary text and labels */
p, label, span, div,
.stMarkdown, .stCaption,
[data-testid="stWidgetLabel"],
[data-testid="stMarkdownContainer"] {
    color: #D5DEEA;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #101827;
}

section[data-testid="stSidebar"] * {
    color: #DCE6F2 !important;
}

/* Text areas */
.stTextArea textarea,
textarea {
    background-color: #162235 !important;
    color: #F1F5FC !important;
    border: 1px solid #40536D !important;
    caret-color: #FFFFFF !important;
}

.stTextArea textarea::placeholder {
    color: #AAB8CA !important;
}

/* Number inputs and other input fields */
.stNumberInput input,
.stTextInput input {
    background-color: #162235 !important;
    color: #FFFFFF !important;
    border: 1px solid #40536D !important;
}

/* Sliders and select boxes */
.stSelectbox div[data-baseweb="select"] {
    background-color: #162235;
    color: #FFFFFF;
}

/* Buttons */
.stButton button {
    background-color: #FF454D;
    color: #FFFFFF !important;
    border: none;
    font-weight: 700;
    border-radius: 7px;
}

.stButton button:hover {
    background-color: #E93640;
    color: #FFFFFF !important;
}

/* Metric cards */
.metric-card {
    background-color: #111D2D;
    border: 1px solid #40536D;
    padding: 16px;
    border-radius: 10px;
    color: #F1F5FC;
}

/* Expanders */
[data-testid="stExpander"] {
    background-color: #111D2D;
    border: 1px solid #34465E;
}

/* Code and JSON output */
.stCode, pre, code {
    background-color: #111D2D !important;
    color: #DCEBFF !important;
}

/* Dividers */
hr {
    border-color: #34465E;
}
</style>
""", unsafe_allow_html=True)

# Import the actual agent, without preventing the UI
# from opening if configuration is unavailable.
try:
    from agent import run_agent
    AGENT_AVAILABLE = True
    AGENT_ERROR = None
except Exception as error:
    AGENT_AVAILABLE = False
    AGENT_ERROR = str(error)


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("PHALANX-AI")
st.caption(
    "AGENTIC ENVIRONMENTAL ENGINEERING "
    "| LLM-DRIVEN TOOL ORCHESTRATION"
)

st.markdown("""
PHALANX-AI is an engineering assessment agent that uses
a large language model to select environmental data tools,
execute engineering calculations and inspect validation
results before producing an assessment.
""")

st.divider()


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:
    st.header("Assessment Configuration")

    latitude = st.number_input(
        "Latitude",
        min_value=-90.0,
        max_value=90.0,
        value=13.0827,
        format="%.4f"
    )

    longitude = st.number_input(
        "Longitude",
        min_value=-180.0,
        max_value=180.0,
        value=80.2707,
        format="%.4f"
    )

    max_steps = st.slider(
        "Maximum orchestration rounds",
        min_value=1,
        max_value=10,
        value=5
    )

    st.divider()

    st.subheader("Registered Engineering Tools")

    st.markdown("""
    - **get_weather** — model-based atmospheric data
    - **get_elevation** — static terrain elevation
    - **calculate_air_density** — moist-air engineering calculation
    """)

    st.divider()

    st.caption("Model: Gemini 3.6 Flash")
    st.caption("Execution: Bounded tool-calling loop")
    st.caption("Validation: Independent Python checks")


# ---------------------------------------------------------
# REQUEST INTERFACE
# ---------------------------------------------------------

st.subheader("Environmental Engineering Assessment")

default_request = f"""
Perform a civilian environmental engineering assessment
for the following coordinates:

Latitude: {latitude}
Longitude: {longitude}

Determine the relevant atmospheric conditions.

Retrieve model-based weather data and terrain elevation
where appropriate.

Use the actual retrieved temperature, absolute surface
pressure and relative humidity to calculate moist-air
density.

Compare moist-air density with dry-air density.

Explain:
1. Retrieved environmental conditions.
2. Engineering calculations and assumptions.
3. Validation results.
4. Environmental significance.
5. Data sources and limitations.

Do not invent measurements or substitute missing data.
Clearly distinguish retrieved data, calculated values
and engineering interpretation.
"""

request = st.text_area(
    "Assessment instructions",
    value=default_request,
    height=230
)

run_button = st.button(
    "RUN PHALANX ENGINEERING ASSESSMENT",
    type="primary",
    use_container_width=True
)


# ---------------------------------------------------------
# EXECUTION
# ---------------------------------------------------------

if run_button:

    if not AGENT_AVAILABLE:
        st.error("The engineering agent could not be loaded.")
        st.code(AGENT_ERROR)

    elif not request.strip():
        st.warning("Enter an assessment request.")

    else:
        with st.spinner(
            "PHALANX is planning and executing its assessment..."
        ):
            try:
                result = run_agent(
                    request,
                    max_steps=max_steps
                )

                st.session_state["phalanx_result"] = result

            except Exception as error:
                st.session_state["phalanx_error"] = str(error)
                st.session_state.pop("phalanx_result", None)


# ---------------------------------------------------------
# RESULTS
# ---------------------------------------------------------

if "phalanx_error" in st.session_state:

    st.error("Agent execution failed.")
    st.code(st.session_state["phalanx_error"])

    st.info(
        "Check API availability, quota, credentials and "
        "network connectivity. An API failure is not a "
        "successful engineering assessment."
    )

    if st.button("Clear error"):
        del st.session_state["phalanx_error"]
        st.rerun()


if "phalanx_result" in st.session_state:

    result = st.session_state["phalanx_result"]

    st.divider()
    st.subheader("Assessment Results")

    status = result.get("status", "UNKNOWN")

    if status == "COMPLETED":
        st.success("Assessment completed.")

    elif status == "VALIDATION_REJECTED":
        st.error("Engineering validation rejected a result.")

    else:
        st.warning(f"Agent status: {status}")

    st.markdown("### Engineering Assessment")

    st.markdown(
        result.get("answer", "No final assessment returned.")
    )

    # ---------------------------------------------
    # EXECUTION TRACE
    # ---------------------------------------------

    st.divider()
    st.subheader("Agent Execution Trace")

    steps = result.get("steps", [])

    if steps:

        for index, step in enumerate(steps, start=1):

            with st.expander(
                f"Round {step.get('step', index)} | "
                f"{step.get('tool', 'Unknown tool')}"
            ):

                st.markdown("**Tool arguments**")
                st.json(step.get("arguments", {}))

                st.markdown("**Execution status**")
                st.write(step.get("result_status", "Unknown"))

                validation_status = step.get(
                    "validation_status",
                    "NOT_CHECKED"
                )

                if validation_status == "PASSED":
                    st.success("Validation: PASSED")

                elif validation_status == "REJECTED":
                    st.error("Validation: REJECTED")

                else:
                    st.info(
                        f"Validation: {validation_status}"
                    )

                if "validation" in step:
                    st.json(step["validation"])

                if "tool_result" in step:
                    st.markdown("**Tool result**")
                    st.json(step["tool_result"])

    else:
        st.info("No tools were executed.")

    # ---------------------------------------------
    # REJECTION RECORDS
    # ---------------------------------------------

    rejected = result.get("rejected_validations", [])

    if rejected:
        st.divider()
        st.subheader("Rejected Engineering Results")
        st.json(rejected)

    # ---------------------------------------------
    # SUMMARY
    # ---------------------------------------------

    st.divider()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Agent status",
        status
    )

    col2.metric(
        "Tool calls",
        result.get("tool_calls", len(steps))
    )

    col3.metric(
        "Execution rounds",
        len(set(s.get("step") for s in steps))
    )

    st.download_button(
        "Download execution record (JSON)",
        data=json.dumps(result, indent=4, default=str),
        file_name="phalanx_execution_record.json",
        mime="application/json",
        use_container_width=True
    )


# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.divider()

st.caption(
    "PHALANX-AI | Environmental Engineering Agent | "
    "Model-based weather data is not direct sensor telemetry. "
    "Engineering outputs require appropriate domain review."
)