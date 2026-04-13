import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title='FocusSense',
    page_icon=':dart:',
    layout='wide',
)

@st.cache_data
def load_focus_data():
    path = Path(__file__).parent / 'data' / 'focus_data.csv'
    df = pd.read_csv(path, parse_dates=['session_date'])
    df['session_date'] = df['session_date'].dt.date
    df['below_threshold'] = df['focus_percentage'] < df['threshold']
    df['session_label'] = df['session_date'].astype(str) + ' • ' + df['session_id']
    return df

focus_df = load_focus_data()

classes = sorted(focus_df['class_name'].unique())
students = sorted(focus_df['student_name'].unique())
guardians = sorted(focus_df['guardian_name'].unique())

PASSWORDS = {
    'Teacher': {class_name: 'teach123' for class_name in classes},
    'Student': {student: 'student123' for student in students},
    'Parent': {guardian: 'parent123' for guardian in guardians},
}

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None
    st.session_state.class_name = None

st.title('FocusSense — Classroom focus dashboard')
st.markdown(
    'A secure login page gives teachers, students, and parents access to the dashboard.'
)

if not st.session_state.logged_in:
    with st.form('login_form'):
        login_role = st.selectbox('Login as', ['Teacher', 'Student', 'Parent'])
        if login_role == 'Teacher':
            login_user = st.selectbox('Class', classes)
        elif login_role == 'Student':
            login_user = st.selectbox('Student', students)
        else:
            login_user = st.selectbox('Guardian', guardians)
        password = st.text_input('Password', type='password')
        login_button = st.form_submit_button('Login')

        if login_button:
            expected = PASSWORDS[login_role].get(login_user)
            if expected and password == expected:
                st.session_state.logged_in = True
                st.session_state.role = login_role
                st.session_state.username = login_user
                st.session_state.class_name = login_user if login_role == 'Teacher' else None
                st.success(f'Logged in successfully as {login_user}.')
                st.experimental_rerun()
            else:
                st.error('Login failed. Check your role, username, and password.')

    st.markdown('### Demo credentials')
    st.markdown('- Teacher password: `teach123`')
    st.markdown('- Student password: `student123`')
    st.markdown('- Parent password: `parent123`')
    st.stop()

if st.sidebar.button('Logout'):
    for key in ['logged_in', 'role', 'username', 'class_name']:
        st.session_state.pop(key, None)
    st.experimental_rerun()

role = st.session_state.role
if role == 'Teacher':
    st.sidebar.subheader('Teacher dashboard')
    selected_class = st.session_state.class_name or st.sidebar.selectbox('Class', classes)
    class_df = focus_df[focus_df['class_name'] == selected_class]

    session_options = (
        class_df[['session_id', 'session_date']]
        .drop_duplicates()
        .sort_values(['session_date', 'session_id'], ascending=[False, True])
    )
    session_label_map = {
        f'{row.session_date} • {row.session_id}': row.session_id
        for _, row in session_options.iterrows()
    }
    selected_session_label = st.sidebar.selectbox('Session', list(session_label_map.keys()))
    selected_session = session_label_map[selected_session_label]
    session_df = class_df[class_df['session_id'] == selected_session]

    st.header(f'Teacher view — {selected_class}')
    st.subheader('Live session overview')

    avg_focus = session_df['focus_percentage'].mean()
    low_count = session_df['below_threshold'].sum()
    total_count = len(session_df)
    on_target = total_count - low_count

    c1, c2, c3 = st.columns(3)
    c1.metric('Average focus', f'{avg_focus:.0f}%')
    c2.metric('Students on target', on_target)
    c3.metric('Below threshold', low_count)

    st.markdown('### Session focus graph')
    graph_df = session_df.set_index('student_name')[['focus_percentage']]
    st.bar_chart(graph_df, height=360)

    st.markdown('### Class focus trend')
    trend_df = (
        class_df.groupby('session_id', as_index=False)
        .agg(session_date=('session_date', 'first'), avg_focus=('focus_percentage', 'mean'))
        .sort_values('session_date')
    )
    trend_display = trend_df.set_index('session_date')[['avg_focus']].rename(columns={'avg_focus': 'Average focus'})
    st.line_chart(trend_display, height=320)

    st.markdown('### Students below threshold in this session')
    below_df = session_df[session_df['below_threshold']].sort_values('focus_percentage')
    if below_df.empty:
        st.success('All students are meeting the focus threshold for this session.')
    else:
        st.markdown('**General suggestions:** ')
        st.write(
            'Focus is below the desired level for one or more students. '
            'Try general strategies such as a quick attention check, a short movement or brain break, '
            'a clear transition to the next task, or a brief recap of expectations before continuing.'
        )
        for _, row in below_df.iterrows():
            row_cols = st.columns([1, 2])
            with row_cols[0]:
                st.image(row['student_image'], width=100)
            with row_cols[1]:
                st.markdown(f'**{row.student_name}**')
                st.markdown(f'- Focus: **{row.focus_percentage}%**')
                st.markdown(f'- Threshold: {row.threshold}%')
                st.markdown(f'- Guardian: {row.guardian_name}')

    st.markdown('---')
    st.subheader('Session summary by class')
    summary = (
        class_df.groupby(['session_id', 'session_date'], as_index=False)
        .agg(
            avg_focus=('focus_percentage', 'mean'),
            below_count=('below_threshold', 'sum'),
            student_count=('student_id', 'nunique'),
        )
        .sort_values(['session_date', 'session_id'], ascending=[False, True])
    )
    summary['avg_focus'] = summary['avg_focus'].round(0)
    summary = summary.rename(columns={
        'session_id': 'Session',
        'session_date': 'Date',
        'avg_focus': 'Avg Focus',
        'below_count': 'Below Threshold',
        'student_count': 'Student Count',
    })
    st.dataframe(summary, use_container_width=True)

elif role == 'Student':
    selected_student = st.session_state.username
    st.sidebar.subheader('Student access')
    st.sidebar.markdown(f'Logged in as: {selected_student}')
    student_df = focus_df[focus_df['student_name'] == selected_student]

    st.header(f'Private focus report — {selected_student}')
    if student_df.empty:
        st.warning('No focus data is available for this student yet.')
    else:
        sorted_df = student_df.sort_values('session_date')
        latest = sorted_df.iloc[-1]
        avg_focus = sorted_df['focus_percentage'].mean()

        c1, c2 = st.columns(2)
        c1.metric('Latest focus', f'{latest.focus_percentage}%')
        c2.metric('Average focus', f'{avg_focus:.0f}%')

        st.markdown(f'**Class:** {latest.class_name}')
        st.markdown(f'**Latest session:** {latest.session_date}')
        st.markdown(f'**Threshold:** {latest.threshold}%')

        st.markdown('### Focus history graph')
        history_graph = sorted_df.set_index('session_date')[['focus_percentage']]
        st.line_chart(history_graph.rename(columns={'focus_percentage': 'Focus %'}), height=340)

        below_history = sorted_df[sorted_df['below_threshold']]
        if below_history.empty:
            st.success('All recorded sessions are above the focus threshold.')
        else:
            st.markdown('### Sessions below threshold')
            st.write(
                'The student fell below the focus threshold in these sessions. '
                'Since the exact cause is unknown, try broad support like clearer instructions, '
                'shorter tasks, or a quick check-in to help them regain attention.'
            )
            for _, row in below_history.iterrows():
                st.markdown(f'- **{row.session_date}** — {row.class_name}: {row.focus_percentage}%')

        st.markdown('### Session details')
        detail_table = sorted_df[['session_date', 'class_name', 'focus_percentage', 'threshold', 'below_threshold']]
        detail_table = detail_table.rename(columns={
            'session_date': 'Date',
            'class_name': 'Class',
            'focus_percentage': 'Focus %',
            'threshold': 'Threshold',
            'below_threshold': 'Below threshold',
        })
        st.dataframe(detail_table, use_container_width=True)

else:
    selected_guardian = st.session_state.username
    st.sidebar.subheader('Parent access')
    st.sidebar.markdown(f'Logged in as: {selected_guardian}')
    guardian_df = focus_df[focus_df['guardian_name'] == selected_guardian]
    student_options = sorted(guardian_df['student_name'].unique())
    selected_student = student_options[0] if student_options else None
    student_df = focus_df[focus_df['student_name'] == selected_student]

    st.header(f'Private focus report — {selected_student}')
    if student_df.empty:
        st.warning('No focus data is available for this student yet.')
    else:
        sorted_df = student_df.sort_values('session_date')
        latest = sorted_df.iloc[-1]
        avg_focus = sorted_df['focus_percentage'].mean()

        c1, c2 = st.columns(2)
        c1.metric('Latest focus', f'{latest.focus_percentage}%')
        c2.metric('Average focus', f'{avg_focus:.0f}%')

        st.markdown(f'**Class:** {latest.class_name}')
        st.markdown(f'**Latest session:** {latest.session_date}')
        st.markdown(f'**Threshold:** {latest.threshold}%')

        st.markdown('### Focus history graph')
        history_graph = sorted_df.set_index('session_date')[['focus_percentage']]
        st.line_chart(history_graph.rename(columns={'focus_percentage': 'Focus %'}), height=340)

        below_history = sorted_df[sorted_df['below_threshold']]
        if below_history.empty:
            st.success('All recorded sessions are above the focus threshold.')
        else:
            st.markdown('### Sessions below threshold')
            st.write(
                'The student fell below the focus threshold in these sessions. '
                'Since the exact cause is unknown, try broad support like clearer instructions, '
                'shorter tasks, or a quick check-in to help them regain attention.'
            )
            for _, row in below_history.iterrows():
                st.markdown(f'- **{row.session_date}** — {row.class_name}: {row.focus_percentage}%')

        st.markdown('### Session details')
        detail_table = sorted_df[['session_date', 'class_name', 'focus_percentage', 'threshold', 'below_threshold']]
        detail_table = detail_table.rename(columns={
            'session_date': 'Date',
            'class_name': 'Class',
            'focus_percentage': 'Focus %',
            'threshold': 'Threshold',
            'below_threshold': 'Below threshold',
        })
        st.dataframe(detail_table, use_container_width=True)
    if role == 'Student':
        st.sidebar.subheader('Student access')
        selected_student = st.sidebar.selectbox('Student', students)
        student_df = focus_df[focus_df['student_name'] == selected_student]
    else:
        st.sidebar.subheader('Parent access')
        selected_guardian = st.sidebar.selectbox('Guardian', guardians)
        guardian_df = focus_df[focus_df['guardian_name'] == selected_guardian]
        student_options = sorted(guardian_df['student_name'].unique())
        selected_student = st.sidebar.selectbox('Student', student_options)
        student_df = focus_df[focus_df['student_name'] == selected_student]

    st.header(f'Private focus report — {selected_student}')
    if student_df.empty:
        st.warning('No focus data is available for this student yet.')
    else:
        sorted_df = student_df.sort_values('session_date')
        latest = sorted_df.iloc[-1]
        avg_focus = sorted_df['focus_percentage'].mean()

        c1, c2 = st.columns(2)
        c1.metric('Latest focus', f'{latest.focus_percentage}%')
        c2.metric('Average focus', f'{avg_focus:.0f}%')

        st.markdown(f'**Class:** {latest.class_name}')
        st.markdown(f'**Latest session:** {latest.session_date}')
        st.markdown(f'**Threshold:** {latest.threshold}%')

        st.markdown('### Focus history graph')
        history_graph = sorted_df.set_index('session_date')[['focus_percentage']]
        st.line_chart(history_graph.rename(columns={'focus_percentage': 'Focus %'}), height=340)

        below_history = sorted_df[sorted_df['below_threshold']]
        if below_history.empty:
            st.success('All recorded sessions are above the focus threshold.')
        else:
            st.markdown('### Sessions below threshold')
            st.write(
                'The student fell below the focus threshold in these sessions. ' 
                'Since the exact cause is unknown, try broad support like clearer instructions, ' 
                'shorter tasks, or a quick check-in to help them regain attention.'
            )
            for _, row in below_history.iterrows():
                st.markdown(f'- **{row.session_date}** — {row.class_name}: {row.focus_percentage}%')

        st.markdown('### Session details')
        detail_table = sorted_df[['session_date', 'class_name', 'focus_percentage', 'threshold', 'below_threshold']]
        detail_table = detail_table.rename(columns={
            'session_date': 'Date',
            'class_name': 'Class',
            'focus_percentage': 'Focus %',
            'threshold': 'Threshold',
            'below_threshold': 'Below threshold',
        })
        st.dataframe(detail_table, use_container_width=True)
