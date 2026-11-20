import os
from datetime import date

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def setting(name, default=""):
    if name in os.environ:
        return os.environ[name]
    try:
        return st.secrets.get(name, default)
    except (AttributeError, FileNotFoundError, KeyError):
        return default


API_URL = setting("TASKFLOW_API_URL", "http://localhost:8000").rstrip("/")
SUPABASE_URL = setting("SUPABASE_URL").rstrip("/")
SUPABASE_ANON_KEY = setting("SUPABASE_ANON_KEY")
PAGE_SIZE = 10

st.set_page_config(page_title="TaskFlow", page_icon="✅", layout="wide")

# -------------------------
# Styling
# -------------------------

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1050px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        h1 {
            font-weight: 700;
            letter-spacing: -1px;
        }

        .subtitle {
            color: #808495;
            margin-top: -12px;
            margin-bottom: 25px;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
        }

        div[data-testid="stExpander"] {
            border-radius: 10px;
        }

        .task-meta {
            color: #808495;
            font-size: 13px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------
# Helpers
# -------------------------


def reset_page():
    st.session_state.page = 0


def api_request(method, endpoint, **kwargs):
    headers = kwargs.pop("headers", {})
    if st.session_state.get("access_token"):
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    timeout = kwargs.pop("timeout", 30)
    response = requests.request(
        method, f"{API_URL}{endpoint}", headers=headers, timeout=timeout, **kwargs
    )
    response.raise_for_status()
    return response


if "page" not in st.session_state:
    st.session_state.page = 0

if not st.session_state.get("access_token"):
    st.title("TaskFlow sign in")
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error("Configure SUPABASE_URL and SUPABASE_ANON_KEY for the frontend.")
        st.stop()
    auth_mode = st.radio("Account", ["Sign in", "Create account"], horizontal=True)
    with st.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit_auth = st.form_submit_button(auth_mode, type="primary")
    if submit_auth:
        auth_path = (
            "/auth/v1/token?grant_type=password"
            if auth_mode == "Sign in"
            else "/auth/v1/signup"
        )
        try:
            auth_response = requests.post(
                f"{SUPABASE_URL}{auth_path}",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
                json={"email": email.strip(), "password": password},
                timeout=15,
            )
            auth_response.raise_for_status()
            auth_data = auth_response.json()
            if not auth_data.get("access_token"):
                st.success("Check your email to confirm your account, then sign in.")
            else:
                st.session_state.access_token = auth_data["access_token"]
                st.rerun()
        except requests.RequestException as error:
            error_code = None
            if error.response is not None:
                try:
                    error_code = error.response.json().get("error_code")
                except ValueError:
                    pass
            if error_code == "invalid_credentials":
                st.error(
                    "Supabase did not accept that email and password. If this is a "
                    "new account, choose Create account and confirm the email before "
                    "signing in. Otherwise, check the email address and password."
                )
            elif error_code == "email_not_confirmed":
                st.error(
                    "Confirm your account using the link sent to your email, "
                    "then sign in."
                )
            elif error_code == "over_email_send_rate_limit":
                st.error(
                    "Supabase temporarily blocked signup email delivery because "
                    "the project's email quota was reached. Stop retrying for now "
                    "and check your inbox and spam folder for the first confirmation "
                    "email. If none arrived, wait for the quota window to reset, then "
                    "try Create account once. For ongoing use, configure custom SMTP "
                    "in Supabase Auth."
                )
            else:
                detail = (
                    error.response.text
                    if error.response is not None
                    else str(error)
                )
                st.error(f"Authentication failed: {detail}")
    st.stop()

if st.sidebar.button("Sign out"):
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
    st.session_state.pop("access_token", None)
    st.session_state.pop("conversation_id", None)
    st.session_state.pop("selected_conversation_id", None)
    st.rerun()


# -------------------------
# Header
# -------------------------

st.title("TaskFlow")

st.markdown(
    '<p class="subtitle">Organize your work. Focus on what matters.</p>',
    unsafe_allow_html=True,
)


# -------------------------
# Create task
# -------------------------

with st.expander("＋ Create a new task"):
    with st.form("create_task_form", clear_on_submit=True):
        title = st.text_input("Task title")
        description = st.text_area("Description")

        col1, col2 = st.columns(2)

        with col1:
            priority = st.selectbox("Priority", ["medium", "high", "low"])

        with col2:
            due_date = st.date_input("Due date", value=None, format="YYYY-MM-DD")

        submitted = st.form_submit_button(
            "Create task", type="primary", use_container_width=True
        )

        if submitted:
            if not title.strip():
                st.warning("Please enter a task title.")

            else:
                try:
                    api_request(
                        "POST",
                        "/tasks",
                        json={
                            "title": title.strip(),
                            "description": description,
                            "priority": priority,
                            "due_date": (due_date.isoformat() if due_date else None),
                        },
                    )

                    st.success("Task created!")
                    reset_page()
                    st.rerun()

                except requests.RequestException as error:
                    st.error(f"Could not create task: {error}")


st.divider()


# -------------------------
# Filters
# -------------------------

st.subheader("Your tasks")

col1, col2, col3 = st.columns(3)

with col1:
    status_filter = st.selectbox(
        "Status",
        ["All", "pending", "in_progress", "completed"],
        key="status_filter",
        on_change=reset_page,
    )

with col2:
    priority_filter = st.selectbox(
        "Priority",
        ["All", "high", "medium", "low"],
        key="priority_filter",
        on_change=reset_page,
    )

with col3:
    sort_by = st.selectbox(
        "Sort by", ["id", "priority"], key="sort_by", on_change=reset_page
    )


# -------------------------
# Fetch tasks
# -------------------------

params = {
    "sort_by": sort_by,
    "skip": st.session_state.page * PAGE_SIZE,
    "limit": PAGE_SIZE + 1,
}

if status_filter != "All":
    params["status_filter"] = status_filter

if priority_filter != "All":
    params["priority"] = priority_filter


try:
    response = api_request("GET", "/tasks", params=params)

    tasks = response.json()

    has_next = len(tasks) > PAGE_SIZE
    tasks = tasks[:PAGE_SIZE]

    if not tasks:
        st.info("No tasks found. Create a task or change your filters.")

    else:
        # -------------------------
        # Compact task cards
        # -------------------------

        for task in tasks:
            with st.container(border=True):
                col1, col2 = st.columns([10, 2])

                with col1:
                    # Title
                    st.write(task["title"])

                    # Compact metadata
                    st.caption(
                        f"{task['status'].replace('_', ' ').title()}"
                        f"  ·  {task['priority'].title()}"
                        f"  ·  Due: {task['due_date'] or 'Not set'}"
                    )

                with col2:
                    st.markdown(
                        f'<div style="text-align:right; color:#808495;'
                        f'font-size:12px;">'
                        f"{task['status'].replace('_', ' ').title()}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                # -------------------------
                # Expandable task details
                # -------------------------

                with st.expander("View details and edit"):
                    st.markdown("**Description**")

                    st.write(
                        task["description"]
                        if task["description"]
                        else "No description provided."
                    )

                    st.divider()

                    st.markdown("**Task information**")

                    st.caption(f"Created: {task['created_at']}")

                    st.caption(f"Last updated: {task['updated_at']}")

                    # -------------------------
                    # Edit task
                    # -------------------------

                    st.markdown("**Edit task**")

                    task_due_date = (
                        date.fromisoformat(task["due_date"])
                        if task["due_date"]
                        else None
                    )

                    with st.form(f"update_form_{task['id']}"):
                        new_title = st.text_input(
                            "Title", value=task["title"], key=f"title_{task['id']}"
                        )

                        new_description = st.text_area(
                            "Description",
                            value=task["description"] or "",
                            key=f"description_{task['id']}",
                        )

                        col1, col2 = st.columns(2)

                        with col1:
                            new_status = st.selectbox(
                                "Status",
                                ["pending", "in_progress", "completed"],
                                index=["pending", "in_progress", "completed"].index(
                                    task["status"]
                                ),
                                key=f"status_{task['id']}",
                            )

                        with col2:
                            new_priority = st.selectbox(
                                "Priority",
                                ["low", "medium", "high"],
                                index=["low", "medium", "high"].index(task["priority"]),
                                key=f"priority_{task['id']}",
                            )

                        new_due_date = st.date_input(
                            "Due date",
                            value=task_due_date,
                            format="YYYY-MM-DD",
                            key=f"due_date_{task['id']}",
                        )

                        save = st.form_submit_button(
                            "Save changes", type="primary", use_container_width=True
                        )

                        if save:
                            if not new_title.strip():
                                st.warning("Task title cannot be empty.")

                            else:
                                try:
                                    api_request(
                                        "PUT",
                                        f"/tasks/{task['id']}",
                                        json={
                                            "title": new_title.strip(),
                                            "description": new_description,
                                            "status": new_status,
                                            "priority": new_priority,
                                            "due_date": (
                                                new_due_date.isoformat()
                                                if new_due_date
                                                else None
                                            ),
                                        },
                                    )

                                    st.success("Task updated!")
                                    st.rerun()

                                except requests.RequestException as error:
                                    st.error(f"Could not update task: {error}")

                    # -------------------------
                    # Delete task
                    # -------------------------

                    st.divider()

                    confirm_delete = st.checkbox(
                        "I want to delete this task", key=f"confirm_delete_{task['id']}"
                    )

                    if st.button(
                        "Delete task",
                        key=f"delete_{task['id']}",
                        disabled=not confirm_delete,
                        use_container_width=True,
                    ):
                        try:
                            api_request("DELETE", f"/tasks/{task['id']}")

                            st.success("Task deleted!")
                            st.rerun()

                        except requests.RequestException as error:
                            st.error(f"Could not delete task: {error}")

    # -------------------------
    # Pagination
    # -------------------------

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button(
            "← Previous", disabled=st.session_state.page == 0, use_container_width=True
        ):
            st.session_state.page -= 1
            st.rerun()

    with col2:
        st.markdown(
            f"<p style='text-align:center; padding-top:5px;'>"
            f"Page {st.session_state.page + 1}</p>",
            unsafe_allow_html=True,
        )

    with col3:
        if st.button("Next →", disabled=not has_next, use_container_width=True):
            st.session_state.page += 1
            st.rerun()


except requests.RequestException as error:
    st.error(
        "Unable to connect to TaskFlow backend. "
        "Make sure FastAPI is running. "
        f"Details: {error}"
    )


# -------------------------
# AI Assistant
# -------------------------

st.divider()

st.subheader("TaskFlow AI Assistant")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "selected_conversation_id" not in st.session_state:
    st.session_state.selected_conversation_id = None


# -------------------------
# Conversation Sidebar
# -------------------------

response = api_request("GET", "/chat/conversations")
conversations = response.json()

if st.sidebar.button("New Chat"):
    st.session_state.conversation_id = None
    st.session_state.selected_conversation_id = None
    st.session_state.chat_history = []
    st.rerun()

conversation_options = [None] + [conversation["id"] for conversation in conversations]

selected_id = st.sidebar.selectbox(
    "Previous Conversations",
    options=conversation_options,
    format_func=lambda conversation_id: (
        "New conversation"
        if conversation_id is None
        else f"Conversation {conversation_id}"
    ),
    key="selected_conversation_id",
)


# Load selected conversation when selection changes
if selected_id != st.session_state.conversation_id:
    if selected_id is None:
        st.session_state.conversation_id = None
        st.session_state.chat_history = []

    else:
        response = api_request(
            "GET",
            f"/chat/conversations/{selected_id}",
        )

        conversation = response.json()

        st.session_state.conversation_id = conversation["id"]
        st.session_state.chat_history = conversation["messages"]


# -------------------------
# Display Previous Messages
# -------------------------

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])


# -------------------------
# Receive a New Message
# -------------------------

if prompt := st.chat_input("Ask TaskFlow something..."):
    # Display and save user message
    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    with st.chat_message("user"):
        st.write(prompt)

    # Prepare request with conversation ID
    payload = {
        "message": prompt,
        "conversation_id": st.session_state.conversation_id,
    }

    # Ask the backend
    with st.chat_message("assistant"), st.spinner("Thinking..."):
        try:
            response = api_request(
                "POST",
                "/chat/",
                timeout=300,
                json=payload,
            )

            result = response.json()

            # Store the conversation ID returned by the backend
            st.session_state.conversation_id = result["conversation_id"]

            answer = result["answer"]

            st.write(answer)

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

        except requests.HTTPError as error:
            st.error(f"Backend returned an error: {error.response.text}")

        except requests.RequestException as error:
            st.error(f"Could not connect to the AI backend: {error}")

    st.rerun()
