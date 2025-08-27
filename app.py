import streamlit as st
import pandas as pd
from simple_salesforce import Salesforce
import requests
import io
from io import StringIO
from datetime import datetime

APP_TITLE = "GERMANY IS ACCOUNTS"

@st.cache_data(show_spinner="Downloading accounts from SFDC...")
def get_data(IS_name):
    Bricks = pd.read_excel("./Bricks_IS.xlsx", sheet_name="Bricks")

    sf = Salesforce(
        username='nmatyash@lifescan.com', 
        password='KLbq57fa31!',
        security_token='')

    sf_org = 'https://jjds-sunrise.my.salesforce.com/'
    report_id_accounts = '00OQv00000CHJiTMAX'
    report_id_visits = '00OQv00000CHPPhMAP'
    export_params = '?isdtp=p1&export=1&enc=UTF-8&xf=csv'

    sf_report_url_accounts = sf_org + report_id_accounts + export_params
    response_accounts = requests.get(sf_report_url_accounts, headers=sf.headers, cookies={'sid': sf.session_id})
    report_accounts = response_accounts.content.decode('utf-8')
    All_Accounts = pd.read_csv(StringIO(report_accounts))
    All_Accounts = All_Accounts[All_Accounts['Account ID'].map(lambda x: str(x)[0]) == '0']
    All_Accounts = All_Accounts.rename(columns={'Target Call Frequency / Cycle (Account)': 'IS Target', 'Preferred Communication Channel': 'Channel'})

    sf_report_url_visits = sf_org + report_id_visits + export_params
    response_visits = requests.get(sf_report_url_visits, headers=sf.headers, cookies={'sid': sf.session_id})
    report_visits = response_visits.content.decode('utf-8')
    visits = pd.read_csv(StringIO(report_visits))
    visits = visits[visits['Account ID'].map(lambda x: str(x)[0]) == '0']
    
    visits = visits[visits['Assigned'] == IS_name]
    visits['Date'] = visits['Date'].map(lambda x: pd.to_datetime(x))
    visits_count = visits.groupby('Account ID').agg({'Date': 'nunique'}).reset_index()
    visits_count = visits_count.rename(columns={'Date': '# Calls'})
    visits_last = visits.groupby('Account ID').agg({'Date': 'max'}).reset_index()
    visits_last = visits_last.rename(columns={'Date': 'Last Call'})

    All_Accounts = All_Accounts[All_Accounts['Brick Code'].notna()]
    All_Accounts['Brick Code'] = All_Accounts['Brick Code'].astype('int64')
    Bricks['Brick Code'] = Bricks['Brick Code'].astype('int64')
    All_Accounts = All_Accounts.merge(Bricks[['Brick Code','IS']], on = 'Brick Code', how = 'left')
    All_Accounts = All_Accounts[All_Accounts['IS'] == IS_name]
    Bricks['Brick Code'] = Bricks['Brick Code'].astype('str')

    All_Accounts = All_Accounts.merge(visits_count[['Account ID','# Calls']], on = 'Account ID', how = 'left') 
    All_Accounts['# Calls'] = All_Accounts['# Calls'].fillna(0)
    All_Accounts = All_Accounts.merge(visits_last[['Account ID','Last Call']], on = 'Account ID', how = 'left') 
    All_Accounts['Last Call'] = All_Accounts['Last Call'].map(lambda x: pd.to_datetime(x))
    All_Accounts['Last Call'] = All_Accounts['Last Call'].dt.date
    All_Accounts['Last Call'] = All_Accounts['Last Call'].fillna(0)

    All_Accounts['Call Rate'] = All_Accounts['# Calls'].map(lambda x: str(int(x))) + "/" + All_Accounts['IS Target'].map(lambda x: str(int(x)))
    All_Accounts['Coverage'] = All_Accounts['# Calls'] / All_Accounts['IS Target']
    All_Accounts['Called'] = All_Accounts['# Calls'].map(lambda x: "Yes" if x > 0 else "No")

    return All_Accounts

def main():
    #Page settings
    st.set_page_config(layout='wide')
    st.title(APP_TITLE)
    IS = pd.read_excel("./Bricks_IS.xlsx", sheet_name="IS")
    placeholder = st.empty()
    placeholder.header('Choose IS Name')
    
    uploaded_name = st.selectbox("IS Name", IS.sort_values(by = 'IS', ignore_index=True)['IS'].to_list(), index=None, placeholder="Choose your Name...")
    if uploaded_name is None:
        st.stop()
    else:
        placeholder.empty()
        if "Rep_name" not in st.session_state:
            st.session_state.IS_name = uploaded_name
        else:
            st.session_state.IS_name = uploaded_name
        df = get_data(st.session_state.IS_name)

    #Display filters
    col1, col2, col3 = st.columns(3)
    with col1:
        channel_list = df['Channel'].map(lambda x: str(x)).unique()
        for i, n in enumerate(channel_list):
            if n == "nan":
                channel_list[i] = "-"
        channel_list.sort()
        channel = st.multiselect('Preferred Communication Channel', channel_list)

    with col2:
        account_segment_list = df['Account Segment'].map(lambda x: str(x)).unique()
        for i, n in enumerate(account_segment_list):
            if n == "nan":
                account_segment_list[i] = "-"
        account_segment_list.sort()
        account_segment = st.multiselect('Account Segment', account_segment_list)

    with col3:
        called_list = df['Called'].map(lambda x: str(x)).unique()
        for i, n in enumerate(called_list):
            if n == "nan":
                called_list[i] = "-"
        called_list.sort()
        called = st.multiselect('Called', called_list)
    
    col4, col5 = st.columns(2)
    with col4:
        start_coverage, end_coverage = st.select_slider(
            "Select a range of coverage",
            options=['0%', '10%', '20%', '30%', '40%', '50%', '60%', '70%', '80%', '90%', '100%'],
            value=('0%', '100%'))
    
    with col5:
        target = st.slider("Call Target", 0, int(df['IS Target'].max()), (0, int(df['IS Target'].max())))
    
    if channel == []:
        channel_filter = channel_list
    else:
        channel_filter = channel
    if account_segment == []:
        account_segment_filter = account_segment_list
    else:
        account_segment_filter = account_segment
    if called == []:
        called_filter = called_list
    else:
        called_filter = called
    
    df_filtered = df[(df['Channel'].isin(channel_filter ))
                     &(df['Account Segment'].isin(account_segment_filter))
                     &(df['Called'].isin(called_filter))
                     &(df['Coverage'] >= int(start_coverage[:-1]) / 100)
                     &(df['Coverage'] <= int(end_coverage[:-1]) / 100)
                     &(df['IS Target'] >= target[0])
                     &(df['IS Target'] <= target[1])]
    df_filtered['Coverage'] = df_filtered['Coverage'] * 100
    df_filtered = df_filtered[['Account ID', 'Account Owner', 'IS', 'Account Name', 'Account Segment', 
                               'Channel', 'IS Target', '# Calls', 'Last Call', 'Call Rate', 'Coverage', 'Called',
                                'Account Status', 'Call Status (Account)', 'Brick Code',
                                'Brick Description', 'Primary State/Province', 'Primary City', 'Primary Street']]
    
    st.dataframe(df_filtered,
                column_config={
                'Coverage': st.column_config.NumberColumn(
                     "Coverage",
                     help="The percentage value",
                     format="%.0f%%")},
                hide_index=True)
    
    #Download
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_filtered.to_excel(writer, sheet_name='Sheet1', index=False)
    st.download_button(label='📥 Download Current Account List',
                                data=buffer,
                                file_name= 'Accounts.xlsx',
                                mime='application/vnd.ms-excel')

if __name__ == "__main__":
    main()