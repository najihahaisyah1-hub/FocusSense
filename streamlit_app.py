import streamlit as st
import pandas as pd
from pathlib import Path

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title='FocusSense',
    page_icon=':dart:',
    layout='wide',
)

# -----------------------------
# DATA LOADING
# -----------------------------
@st.cache_data
def load_focus_data():
    try:
        path = Path(__file__).parent / 'data' / 'focus_data.csv'

        if not path.exists():
            st.error(f"CSV file not found at: {path}")
            return pd.DataFrame()

        # Load CSV safely
        df = pd.read_csv(
            path,
            parse_dates=['session_date'],
            on_bad_lines='skip',   # skips malformed rows
            encoding='utf-8'
        )

        # Required columns
        required_cols = [
            'session_date', 'session_id', 'student_name',
            'class_name', 'focus_percentage', 'threshold', 'guardian_name'
        ]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            st.error(f"Missing columns in CSV: {missing}")
            return pd.DataFrame()

        # Preprocess
        df['session_date'] = df['session_date'].dt.date
        df['below_threshold'] = df['focus_percentage'] < df['threshold']
        df['session_label'] = df['session_date'].astype(str) + ' • ' + df['session_id']

        return df

    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return pd.DataFrame()


focus_df = load_focus_data()
if focus_df.empty:
    st.stop()

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_student_summary(df):
    sorted_df = df.sort_values('session_date')
    latest = sorted_df.iloc[-1]
    avg_focus = sorted_df['focus_percentage'].mean()
    return sorted_df, latest, avg_focus

def render_focus_history(sorted_df):
    history_graph = sorted_df.set_index('session_date')[['focus_percentage']]
    st.line_chart(history_graph.rename(columns={'focus_percentage': 'Focus %'}), height=340)

def render_below_threshold(sorted_df):
    below = sorted_df[sorted_df['below_threshold']]
    if below.empty:
        st.success('All sessions are above the focus threshold.')
    else:
        st.markdown('### Sessions below threshold')
        st.write(
            'Focus dropped below threshold in these sessions. '
            'Try clearer instructions, shorter tasks, or quick check-ins.'
        )
        for _, row in below.iterrows():
            st.markdown(f'- **{row.session_date}** — {row.class_name}: {row.focus_percentage}%')

def render_table(sorted_df):
    table = sorted_df[['session_date', 'class_name', 'focus_percentage', 'threshold', 'below_threshold']].rename(columns={
        'session_date': 'Date',
        'class_name': 'Class',
        'focus_percentage': 'Focus %',
        'threshold': 'Threshold',
        'below_threshold': 'Below threshold',
    })
    st.dataframe(table, use_container_width=True)

# -----------------------------
# LOGIN STATE
# -----------------------------
if 'logged_in' not in st.session_state:
    st.session_state.update({
        'logged_in': False,
        'role': None,
        'username': None,
        'class_name': None
    })

# -----------------------------
# USER LISTS AND PASSWORDS
# -----------------------------
classes = sorted(focus_df['class_name'].unique())
students = sorted(focus_df['student_name'].unique())
guardians = sorted(focus_df['guardian_name'].unique())

PASSWORDS = {
    'Teacher': {c: 'teach123' for c in classes},
    'Student': {s: 'student123' for s in students},
    'Parent': {g: 'parent123' for g in guardians},
}

# -----------------------------
# LOGIN PAGE
# -----------------------------
st.title('FocusSense — Classroom focus dashboard')

if not st.session_state.logged_in:
    with st.form('login'):
        role = st.selectbox('Login as', ['Teacher', 'Student', 'Parent'])
        if role == 'Teacher':
            user = st.selectbox('Class', classes)
        elif role == 'Student':
            user = st.selectbox('Student', students)
        else:
            user = st.selectbox('Guardian', guardians)

        pw = st.text_input('Password', type='password')
        submit = st.form_submit_button('Login')

        if submit:
            if PASSWORDS[role].get(user) == pw:
                st.session_state.update({
                    'logged_in': True,
                    'role': role,
                    'username': user,
                    'class_name': user if role == 'Teacher' else None
                })
                st.success(f'Logged in as {user}')
                st.rerun()
            else:
                st.error('Invalid credentials')

    st.markdown('### Demo credentials')
    st.markdown('- Teacher: `teach123`')
    st.markdown('- Student: `student123`')
    st.markdown('- Parent: `parent123`')
    st.stop()

# -----------------------------
# LOGOUT
# -----------------------------
if st.sidebar.button('Logout'):
    st.session_state.clear()
    st.rerun()

role = st.session_state.role

# =============================
# TEACHER VIEW
# =============================
if role == 'Teacher':
    st.sidebar.subheader('Teacher dashboard')
    selected_class = st.session_state.class_name
    class_df = focus_df[focus_df['class_name'] == selected_class]

    session_options = class_df[['session_id', 'session_date']].drop_duplicates().sort_values(['session_date'], ascending=False)
    session_map = {f"{row.session_date} • {row.session_id}": row.session_id for _, row in session_options.iterrows()}
    selected_label = st.sidebar.selectbox('Session', list(session_map.keys()))
    session_df = class_df[class_df['session_id'] == session_map[selected_label]]

    st.header(f'Teacher view — {selected_class}')

    avg_focus = session_df['focus_percentage'].mean()
    low = session_df['below_threshold'].sum()
    total = len(session_df)
    c1, c2, c3 = st.columns(3)
    c1.metric('Average focus', f'{avg_focus:.0f}%')
    c2.metric('On target', total - low)
    c3.metric('Below threshold', low)

    st.markdown('### Session focus')
    st.bar_chart(session_df.set_index('student_name')['focus_percentage'])

    st.markdown('### Class trend')
    trend = class_df.groupby('session_date')['focus_percentage'].mean().reset_index()
    st.line_chart(trend.set_index('session_date'))

    st.markdown('### Students below threshold')
    below_df = session_df[session_df['below_threshold']]
    if below_df.empty:
        st.success('All students are on track.')
    else:
        for _, row in below_df.iterrows():
            st.markdown(f"**{row.student_name}** — {row.focus_percentage}% (Threshold: {row.threshold}%)")

# =============================
# STUDENT VIEW
# =============================
elif role == 'Student':
    student_df = focus_df[focus_df['student_name'] == st.session_state.username]
    st.header(f"Student report — {st.session_state.username}")
    if student_df.empty:
        st.warning('No data available.')
    else:
        sorted_df, latest, avg = get_student_summary(student_df)
        c1, c2 = st.columns(2)
        c1.metric('Latest focus', f'{latest.focus_percentage}%')
        c2.metric('Average focus', f'{avg:.0f}%')
        st.markdown(f'**Class:** {latest.class_name}')
        st.markdown(f'**Latest session:** {latest.session_date}')
        render_focus_history(sorted_df)
        render_below_threshold(sorted_df)
        render_table(sorted_df)

# =============================
# PARENT VIEW
# =============================
else:
    st.sidebar.subheader('Parent dashboard')
    guardian_df = focus_df[focus_df['guardian_name'] == st.session_state.username]
    student_options = sorted(guardian_df['student_name'].unique())
    selected_student = st.sidebar.selectbox('Student', student_options)
    student_df = focus_df[focus_df['student_name'] == selected_student]
    st.header(f'Parent report — {selected_student}')
    if student_df.empty:
        st.warning('No data available.')
    else:
        sorted_df, latest, avg = get_student_summary(student_df)
        c1, c2 = st.columns(2)
        c1.metric('Latest focus', f'{latest.focus_percentage}%')
        c2.metric('Average focus', f'{avg:.0f}%')
        st.markdown(f'**Class:** {latest.class_name}')
        st.markdown(f'**Latest session:** {latest.session_date}')
        render_focus_history(sorted_df)
        render_below_threshold(sorted_df)
        render_table(sorted_df)
        st.download_button(
            "Download report",
            data=student_df.to_csv(index=False),
            file_name=f"{selected_student}_focus.csv"
        )
