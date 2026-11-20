import os
from datetime import date

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def setting(name: str, default: str = "") -> str:
    if name in os.environ:
        return os.environ[name]
    try:
        return st.secrets.get(name, default)
    except (AttributeError, FileNotFoundError, KeyError):
        return default


API_URL = setting("TASKFLOW_API_URL", "http://localhost:8000").rstrip("/")
SUPABASE_URL = setting("SUPABASE_URL").rstrip("/")
SUPABASE_ANON_KEY = setting("SUPABASE_ANON_KEY")
PAGE_SIZE = 100
STATUSES = {
    "pending": "To do",
    "in_progress": "In progress",
    "completed": "Completed",
}

st.set_page_config(page_title="TaskFlow", page_icon="✓", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --ink: #20242c;
        --muted: #737b88;
        --line: #e7e9ed;
        --surface: #ffffff;
        --canvas: #f7f8fa;
        --accent: #4257a5;
        --accent-soft: #eef1fb;
    }
    .stApp { background: var(--canvas); color: var(--ink); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: var(--surface);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.3rem; }
    .block-container { max-width: 1320px; padding: 2rem 2.6rem 4rem; }
    h1, h2, h3 { color: var(--ink); letter-spacing: -0.035em; }
    h1 { font-size: 2rem; font-weight: 650; }
    h2 { font-size: 1.38rem; font-weight: 620; }
    h3 { font-size: 1.04rem; font-weight: 620; }
    p, label, .stCaption { color: var(--muted); }
    [data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--line);
        border-radius: 12px; padding: 1rem 1.1rem;
    }
    [data-testid="stMetricLabel"] p { color: var(--muted); font-size: .82rem; }
    [data-testid="stMetricValue"] { color: var(--ink); font-size: 1.75rem; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--line); border-radius: 12px; background: var(--surface);
    }
    .stButton > button, .stFormSubmitButton > button {
        border-radius: 8px; min-height: 2.55rem; font-weight: 560;
        border-color: var(--line);
        transition: border-color .15s ease, background .15s ease;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        border-color: #aeb8dc; color: var(--accent);
    }
    button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
    button[kind="primary"]:hover { background: #35488f; color: white; }
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] [role="combobox"] {
        border-radius: 8px; border-color: var(--line);
    }
    [data-testid="stRadio"] label { color: var(--ink); }
    [data-testid="stChatMessage"] {
        border: 1px solid var(--line); border-radius: 12px;
        background: var(--surface); padding: .75rem 1rem;
    }
    [data-testid="stChatInput"] textarea { border-radius: 12px; }
    .brand-mark {
        display: flex; align-items: center; gap: .7rem; margin: .2rem 0 1.8rem;
        color: var(--ink); font-weight: 700; font-size: 1.12rem;
    }
    .brand-icon {
        width: 30px; height: 30px; display: grid; place-items: center;
        border-radius: 9px; background: var(--accent); color: white; font-size: .95rem;
    }
    .eyebrow { color: var(--muted); font-size: .74rem; font-weight: 650;
        letter-spacing: .09em; text-transform: uppercase; }
    .page-subtitle { color: var(--muted); margin-top: -.7rem; }
    .pill { display: inline-block; padding: .22rem .55rem; border-radius: 999px;
        font-size: .74rem; font-weight: 600; white-space: nowrap; }
    .status-pending { color: #606b7a; background: #eef0f3; }
    .status-in_progress { color: #755414; background: #fbf2dc; }
    .status-completed { color: #287054; background: #e6f4ed; }
    .priority-high { color: #a33f43; background: #fae9e9; }
    .priority-medium { color: #755414; background: #fbf2dc; }
    .priority-low { color: #606b7a; background: #eef0f3; }
    .auth-wrap { max-width: 520px; margin: 5vh auto 0; }
    @media (max-width: 760px) {
        .block-container { padding: 1.2rem 1rem 3rem; }
        h1 { font-size: 1.65rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_request(method: str, endpoint: str, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    timeout = kwargs.pop("timeout", 30)
    token = st.session_state.get("access_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.request(
        method, f"{API_URL}{endpoint}", headers=headers, timeout=timeout, **kwargs
    )
    if response.status_code == 401 and st.session_state.get("refresh_token"):
        try:
            refreshed = requests.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": SUPABASE_ANON_KEY},
                json={"refresh_token": st.session_state.refresh_token},
                timeout=15,
            )
            refreshed.raise_for_status()
            session = refreshed.json()
            st.session_state.access_token = session["access_token"]
            st.session_state.refresh_token = session.get(
                "refresh_token", st.session_state.refresh_token
            )
            headers["Authorization"] = f"Bearer {st.session_state.access_token}"
            response = requests.request(
                method,
                f"{API_URL}{endpoint}",
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        except (requests.RequestException, KeyError):
            st.session_state.pop("access_token", None)
            st.session_state.pop("refresh_token", None)
            st.rerun()
    response.raise_for_status()
    return response


def save_session(session: dict) -> None:
    st.session_state.access_token = session["access_token"]
    st.session_state.refresh_token = session.get("refresh_token", "")
    st.session_state.user_email = (session.get("user") or {}).get("email", "")


def show_authentication() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 560px !important; padding-top: 6vh !important; }
        [data-testid="stAppViewContainer"] { background: #f5f6f8 !important; }
        [data-testid="stTextInput"] input {
            background: #fff !important; color: #20242c !important;
            border-color: #d9dde5 !important;
        }
        [data-testid="stTextInput"] input::placeholder { color: #737b88 !important; }
        [data-testid="stBaseButton-primary"] {
            background: #4257a5 !important; color: #fff !important;
            border-color: #4257a5 !important;
        }
        [data-testid="stBaseButton-secondary"] {
            background: #fff !important; color: #303642 !important;
            border-color: #d9dde5 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="brand-mark"><span class="brand-icon">✓</span>TaskFlow</div>',
        unsafe_allow_html=True,
    )
    st.title("A clearer way to manage your work")
    st.markdown(
        '<p class="page-subtitle">Sign in to organize tasks and work with your '
        "AI assistant.</p>",
        unsafe_allow_html=True,
    )
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error("Configure SUPABASE_URL and SUPABASE_ANON_KEY for the frontend.")
        st.stop()

    callback_code = st.query_params.get("code")
    callback_state = st.query_params.get("auth_state")
    if st.query_params.get("error"):
        st.error("Google sign-in was cancelled or could not be completed.")
        st.query_params.clear()
    if callback_code and callback_state:
        try:
            response = requests.post(
                f"{API_URL}/auth/google/exchange",
                json={"code": callback_code, "state": callback_state},
                timeout=20,
            )
            response.raise_for_status()
            save_session(response.json())
            st.query_params.clear()
            st.rerun()
        except requests.RequestException as error:
            st.error(f"Google sign-in could not be completed: {error}")

    with st.container(border=True):
        auth_mode = st.radio("Account", ["Sign in", "Create account"], horizontal=True)
        with st.form("auth_form"):
            email = st.text_input("Email address", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button(
                auth_mode, type="primary", use_container_width=True
            )
        if submit:
            endpoint = (
                "/auth/v1/token?grant_type=password"
                if auth_mode == "Sign in"
                else "/auth/v1/signup"
            )
            try:
                response = requests.post(
                    f"{SUPABASE_URL}{endpoint}",
                    headers={
                        "apikey": SUPABASE_ANON_KEY,
                        "Content-Type": "application/json",
                    },
                    json={"email": email.strip(), "password": password},
                    timeout=15,
                )
                response.raise_for_status()
                session = response.json()
                if not session.get("access_token"):
                    st.success(
                        "Check your email to confirm your account, then sign in."
                    )
                else:
                    save_session(session)
                    st.rerun()
            except requests.RequestException as error:
                code = None
                if error.response is not None:
                    try:
                        code = error.response.json().get("error_code")
                    except ValueError:
                        pass
                messages = {
                    "invalid_credentials": "Email or password was not accepted.",
                    "email_not_confirmed": (
                        "Confirm your account using the email link, then sign in."
                    ),
                    "over_email_send_rate_limit": (
                        "Supabase email delivery is rate-limited. "
                        "Check your inbox or try again later."
                    ),
                }
                st.error(messages.get(code, f"Authentication failed: {error}"))

        st.divider()
        if st.button("Continue with Google", use_container_width=True):
            try:
                response = requests.post(f"{API_URL}/auth/google/start", timeout=10)
                response.raise_for_status()
                st.link_button("Open Google sign-in", response.json()["url"])
            except requests.RequestException:
                st.info("Google sign-in is not enabled for this TaskFlow instance.")


def fetch_tasks() -> list[dict]:
    tasks = []
    for offset in range(0, 10_000, PAGE_SIZE):
        page = api_request(
            "GET",
            "/tasks",
            params={"sort_by": "id", "skip": offset, "limit": PAGE_SIZE},
        ).json()
        tasks.extend(page)
        if len(page) < PAGE_SIZE:
            break
    return tasks


def status_pill(status: str) -> str:
    label = STATUSES.get(status, status.replace("_", " ").title())
    return f'<span class="pill status-{status}">{label}</span>'


def priority_pill(priority: str) -> str:
    label = priority.title()
    return f'<span class="pill priority-{priority}">{label} priority</span>'


def due_label(value: str | None) -> str:
    if not value:
        return "No due date"
    parsed = date.fromisoformat(value)
    if parsed < date.today():
        return f"Overdue · {parsed.strftime('%b')} {parsed.day}"
    return f"Due {parsed.strftime('%b')} {parsed.day}"


def render_task_row(task: dict, *, compact: bool = False) -> None:
    with st.container(border=True):
        columns = st.columns([5, 2, 2] if compact else [4.5, 2, 2, 1.5])
        with columns[0]:
            st.markdown(f"**{task['title']}**")
            if task.get("description"):
                st.caption(task["description"])
            else:
                st.caption("No description")
        with columns[1]:
            st.markdown(status_pill(task["status"]), unsafe_allow_html=True)
        with columns[2]:
            st.markdown(priority_pill(task["priority"]), unsafe_allow_html=True)
        if not compact:
            with columns[3]:
                st.caption(due_label(task.get("due_date")))


def create_task_form(key: str = "create_task") -> None:
    with st.expander("＋  Add a task", expanded=False):
        with st.form(key, clear_on_submit=True):
            title = st.text_input("Task name", max_chars=200)
            description = st.text_area("Description", height=90)
            left, middle, right = st.columns(3)
            with left:
                priority = st.selectbox("Priority", ["medium", "high", "low"])
            with middle:
                due_date = st.date_input("Due date", value=None, format="YYYY-MM-DD")
            with right:
                st.write("")
                st.write("")
                submit = st.form_submit_button("Create task", type="primary")
            if submit:
                if not title.strip():
                    st.warning("Add a task name to continue.")
                else:
                    try:
                        api_request(
                            "POST",
                            "/tasks",
                            json={
                                "title": title.strip(),
                                "description": description.strip() or None,
                                "priority": priority,
                                "due_date": due_date.isoformat() if due_date else None,
                            },
                        )
                        st.toast("Task created")
                        st.rerun()
                    except requests.RequestException as error:
                        st.error(f"Could not create task: {error}")


def render_task_editor(task: dict) -> None:
    with st.expander("Edit details"):
        due_value = (
            date.fromisoformat(task["due_date"]) if task.get("due_date") else None
        )
        with st.form(f"edit_{task['id']}"):
            title = st.text_input("Task name", value=task["title"], max_chars=200)
            description = st.text_area(
                "Description", value=task.get("description") or "", height=85
            )
            left, middle, right = st.columns(3)
            with left:
                status = st.selectbox(
                    "Status",
                    list(STATUSES),
                    index=list(STATUSES).index(task["status"]),
                    format_func=lambda value: STATUSES[value],
                )
            with middle:
                priority = st.selectbox(
                    "Priority",
                    ["high", "medium", "low"],
                    index=["high", "medium", "low"].index(task["priority"]),
                )
            with right:
                due_date = st.date_input(
                    "Due date", value=due_value, format="YYYY-MM-DD"
                )
            save = st.form_submit_button("Save changes", type="primary")
            if save:
                if not title.strip():
                    st.warning("Task name cannot be empty.")
                else:
                    try:
                        api_request(
                            "PUT",
                            f"/tasks/{task['id']}",
                            json={
                                "title": title.strip(),
                                "description": description.strip() or None,
                                "status": status,
                                "priority": priority,
                                "due_date": due_date.isoformat() if due_date else None,
                            },
                        )
                        st.toast("Changes saved")
                        st.rerun()
                    except requests.RequestException as error:
                        st.error(f"Could not update task: {error}")


def render_dashboard(tasks: list[dict]) -> None:
    email = st.session_state.get("user_email", "")
    name = (
        email.split("@", maxsplit=1)[0].replace(".", " ").title() if email else "there"
    )
    st.markdown('<p class="eyebrow">Overview</p>', unsafe_allow_html=True)
    st.title(f"Welcome back, {name}")
    st.markdown(
        '<p class="page-subtitle">A calm place to see what is moving and what '
        "needs your attention.</p>",
        unsafe_allow_html=True,
    )

    today = date.today()
    completed = sum(task["status"] == "completed" for task in tasks)
    pending = sum(task["status"] == "pending" for task in tasks)
    overdue = sum(
        1
        for task in tasks
        if task.get("due_date")
        and date.fromisoformat(task["due_date"]) < today
        and task["status"] != "completed"
    )
    metrics = st.columns(4)
    for column, label, value in zip(
        metrics,
        ("All tasks", "To do", "Completed", "Overdue"),
        (len(tasks), pending, completed, overdue),
    ):
        with column:
            st.metric(label, value)

    if tasks:
        progress = completed / len(tasks)
        st.write("")
        st.markdown("**Completion**")
        st.progress(progress, text=f"{completed} of {len(tasks)} tasks complete")

    st.write("")
    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("Recently updated")
        recent = sorted(
            tasks, key=lambda task: task.get("updated_at") or "", reverse=True
        )[:5]
        if recent:
            for task in recent:
                render_task_row(task, compact=True)
        else:
            with st.container(border=True):
                st.markdown("**Your workspace is ready**")
                st.caption("Create a task to give your day a starting point.")
                if st.button("Go to My Tasks", type="primary"):
                    st.session_state.page = "My Tasks"
                    st.rerun()
    with right:
        st.subheader("Upcoming deadlines")
        upcoming = sorted(
            [
                task
                for task in tasks
                if task.get("due_date")
                and date.fromisoformat(task["due_date"]) >= today
                and task["status"] != "completed"
            ],
            key=lambda task: task["due_date"],
        )[:5]
        if upcoming:
            for task in upcoming:
                with st.container(border=True):
                    st.markdown(f"**{task['title']}**")
                due_date = date.fromisoformat(task["due_date"])
                st.caption(f"{due_date.strftime('%A, %b')} {due_date.day}")
        else:
            with st.container(border=True):
                st.markdown("**No upcoming deadlines**")
                st.caption("Tasks with due dates will appear here.")


def render_tasks(tasks: list[dict]) -> None:
    st.markdown('<p class="eyebrow">Workspace</p>', unsafe_allow_html=True)
    st.title("My tasks")
    st.markdown(
        '<p class="page-subtitle">Capture the work, set a priority, and keep '
        "things moving.</p>",
        unsafe_allow_html=True,
    )
    create_task_form()

    search_col, status_col, priority_col, sort_col = st.columns([2.4, 1.2, 1.2, 1.2])
    with search_col:
        query = st.text_input(
            "Search", placeholder="Find a task…", label_visibility="collapsed"
        )
    with status_col:
        status_filter = st.selectbox(
            "Status",
            ["All statuses", *STATUSES],
            format_func=lambda value: (
                "Status" if value == "All statuses" else STATUSES[value]
            ),
        )
    with priority_col:
        priority_filter = st.selectbox(
            "Priority",
            ["All priorities", "high", "medium", "low"],
            format_func=lambda value: (
                "Priority" if value == "All priorities" else value.title()
            ),
        )
    with sort_col:
        sort_by = st.selectbox("Sort", ["Recently updated", "Due date", "Priority"])

    visible = tasks
    if query.strip():
        needle = query.casefold().strip()
        visible = [
            task
            for task in visible
            if needle in task["title"].casefold()
            or needle in (task.get("description") or "").casefold()
        ]
    if status_filter != "All statuses":
        visible = [task for task in visible if task["status"] == status_filter]
    if priority_filter != "All priorities":
        visible = [task for task in visible if task["priority"] == priority_filter]
    if sort_by == "Due date":
        visible = sorted(visible, key=lambda task: task.get("due_date") or "9999-12-31")
    elif sort_by == "Priority":
        visible = sorted(
            visible, key=lambda task: ["high", "medium", "low"].index(task["priority"])
        )
    else:
        visible = sorted(
            visible, key=lambda task: task.get("updated_at") or "", reverse=True
        )

    st.caption(f"{len(visible)} {('task' if len(visible) == 1 else 'tasks')}")
    if not visible:
        with st.container(border=True):
            st.markdown("**Nothing matches this view**")
            st.caption("Try a different search or filter, or add a new task above.")
        return

    for task in visible:
        with st.container(border=True):
            heading, actions = st.columns([5, 1.4])
            with heading:
                st.markdown(f"**{task['title']}**")
                if task.get("description"):
                    st.caption(task["description"])
                badges = (
                    f"{status_pill(task['status'])} &nbsp; "
                    f"{priority_pill(task['priority'])} &nbsp; "
                    f"<span class='pill'>{due_label(task.get('due_date'))}</span>"
                )
                st.markdown(badges, unsafe_allow_html=True)
            with actions:
                complete = task["status"] != "completed"
                label = "Mark complete" if complete else "Reopen"
                if st.button(
                    label, key=f"toggle_{task['id']}", use_container_width=True
                ):
                    next_status = "completed" if complete else "pending"
                    try:
                        api_request(
                            "PUT", f"/tasks/{task['id']}", json={"status": next_status}
                        )
                        st.rerun()
                    except requests.RequestException as error:
                        st.error(f"Could not update task: {error}")
            render_task_editor(task)
            with st.expander("More actions"):
                confirm = st.checkbox("Confirm deletion", key=f"confirm_{task['id']}")
                if st.button(
                    "Delete task", key=f"delete_{task['id']}", disabled=not confirm
                ):
                    try:
                        api_request("DELETE", f"/tasks/{task['id']}")
                        st.toast("Task deleted")
                        st.rerun()
                    except requests.RequestException as error:
                        st.error(f"Could not delete task: {error}")


def load_conversations() -> list[dict]:
    return api_request("GET", "/chat/conversations").json()


def render_assistant() -> None:
    st.markdown('<p class="eyebrow">AI assistant</p>', unsafe_allow_html=True)
    title_col, new_col = st.columns([5, 1])
    with title_col:
        st.title("Ask TaskFlow")
        st.markdown(
            '<p class="page-subtitle">Plan, find, and update your tasks in a '
            "conversation.</p>",
            unsafe_allow_html=True,
        )
    with new_col:
        if st.button("＋ New chat", use_container_width=True):
            st.session_state.active_conversation_id = None
            st.session_state.chat_history = []
            st.rerun()

    try:
        conversations = load_conversations()
    except requests.RequestException as error:
        st.error(f"Could not load conversations: {error}")
        conversations = []

    conversation_by_id = {item["id"]: item for item in conversations}
    options = [None, *conversation_by_id]
    current = st.session_state.get("active_conversation_id")
    if current not in options:
        current = None
        st.session_state.active_conversation_id = None

    if conversations:
        if st.session_state.get("conversation_picker") != current:
            st.session_state.conversation_picker = current
        selected = st.selectbox(
            "Conversation history",
            options,
            index=options.index(current),
            format_func=lambda item_id: (
                "New conversation"
                if item_id is None
                else conversation_by_id[item_id].get("title")
                or f"Conversation {item_id}"
            ),
            key="conversation_picker",
        )
        if selected != st.session_state.get("active_conversation_id"):
            st.session_state.active_conversation_id = selected
            if selected is None:
                st.session_state.chat_history = []
            else:
                try:
                    detail = api_request(
                        "GET", f"/chat/conversations/{selected}"
                    ).json()
                    st.session_state.chat_history = detail["messages"]
                except requests.RequestException as error:
                    st.error(f"Could not load this conversation: {error}")
                    st.session_state.chat_history = []

    history = st.session_state.get("chat_history", [])
    if not history:
        with st.container(border=True):
            st.markdown("**Your assistant is ready when you are**")
            st.caption(
                "Ask about your tasks, or ask TaskFlow to create, update, "
                "complete, or find one."
            )
            st.write("Try: *What should I work on next?*")

    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Message TaskFlow…")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"), st.spinner("Working through your request…"):
            try:
                result = api_request(
                    "POST",
                    "/chat/",
                    timeout=300,
                    json={
                        "message": prompt,
                        "conversation_id": st.session_state.get(
                            "active_conversation_id"
                        ),
                    },
                ).json()
                st.session_state.active_conversation_id = result["conversation_id"]
                st.markdown(result["answer"])
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": result["answer"]}
                )
            except requests.HTTPError as error:
                detail = (
                    error.response.text if error.response is not None else str(error)
                )
                st.error(f"The backend could not answer this request: {detail}")
            except requests.RequestException as error:
                st.error(f"Could not connect to the AI assistant: {error}")
        st.rerun()


def main() -> None:
    if not st.session_state.get("access_token"):
        show_authentication()
        return

    with st.sidebar:
        st.markdown(
            '<div class="brand-mark"><span class="brand-icon">✓</span>TaskFlow</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<p class="eyebrow">Workspace</p>', unsafe_allow_html=True)
        page = st.radio(
            "Navigate",
            ["Dashboard", "My Tasks", "AI Assistant"],
            label_visibility="collapsed",
            key="page",
        )
        st.sidebar.divider()
        email = st.session_state.get("user_email")
        if email:
            st.caption(email)
        if st.button("Sign out", use_container_width=True):
            try:
                requests.post(
                    f"{SUPABASE_URL}/auth/v1/logout",
                    headers={
                        "apikey": SUPABASE_ANON_KEY,
                        "Authorization": f"Bearer {st.session_state.access_token}",
                    },
                    timeout=10,
                )
            except requests.RequestException:
                pass
            for key in (
                "access_token",
                "refresh_token",
                "user_email",
                "active_conversation_id",
                "chat_history",
            ):
                st.session_state.pop(key, None)
            st.rerun()

    try:
        tasks = fetch_tasks()
    except requests.RequestException as error:
        st.title("TaskFlow")
        st.error(
            "The TaskFlow API could not be reached. Check that FastAPI is running. "
            f"Details: {error}"
        )
        return

    if page == "Dashboard":
        render_dashboard(tasks)
    elif page == "My Tasks":
        render_tasks(tasks)
    else:
        render_assistant()


if __name__ == "__main__":
    main()
