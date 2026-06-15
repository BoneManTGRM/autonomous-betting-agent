from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.export_templates import empty_template, example_template, schema_dictionary

st.set_page_config(page_title='Export Templates', layout='wide')
st.title('Export Templates')
st.caption('Download clean CSV templates so future exports include the fields needed for locking, grading, stats, ROI, CLV, and proof tracking.')

rows = st.number_input('Blank template rows', min_value=1, max_value=500, value=25, step=1)
blank = empty_template(int(rows))
example = example_template()
schema = schema_dictionary()

cols = st.columns(3)
cols[0].metric('Template Columns', len(blank.columns))
cols[1].metric('Before-start Required', int(schema['timing'].eq('required_before_start').sum()))
cols[2].metric('After-result Required', int(schema['timing'].eq('required_after_result').sum()))

st.subheader('Schema dictionary')
st.dataframe(schema, use_container_width=True, hide_index=True)

st.subheader('Example row')
st.dataframe(example, use_container_width=True, hide_index=True)

st.subheader('Blank template preview')
st.dataframe(blank.head(25), use_container_width=True, hide_index=True)

st.download_button('Download blank official-pick template CSV', blank.to_csv(index=False), file_name='official_pick_template.csv', mime='text/csv')
st.download_button('Download example official-pick CSV', example.to_csv(index=False), file_name='official_pick_template_example.csv', mime='text/csv')
st.download_button('Download schema dictionary CSV', schema.to_csv(index=False), file_name='official_pick_schema_dictionary.csv', mime='text/csv')

st.warning('Best future export rule: every official pre-event row should include event, prediction, model_probability, decimal_price, bookmaker/source, and prediction_timestamp before the event starts.')
