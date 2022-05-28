import streamlit as st
import pandas as pd

df = pd.read_csv('./all.csv')
df['0歳'] = df['0歳'].str.normalize("NFKC")
df['1歳'] = df['1歳'].str.normalize("NFKC")
df['2歳'] = df['2歳'].str.normalize("NFKC")
df['3歳'] = df['3歳'].str.normalize("NFKC")
df['4歳'] = df['4歳'].str.normalize("NFKC")
df['5歳'] = df['5歳'].str.normalize("NFKC")
selected_item_list = st.multiselect('施設名を選んでね', df['施設名'].unique())
ok_css = "background-color: #fde"
may_css = "background-color: #ffe"

for item in selected_item_list:
    st.write(item)
    st.table(df.query('施設名 == "{}"'.format(item))[[
        '年', '月', '0歳', '1歳', '2歳', '3歳', '4歳', '5歳']].sort_values(by=["年", "月"]).reset_index(drop=True).style.where(lambda x: x == '○', ok_css, "").where(lambda x: x == '△', may_css, ""))
